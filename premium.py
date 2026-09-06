# ============================================================
# PREMIUM SYSTEM
# ============================================================

import time

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes

from config import (
    PREMIUM_PRICE,
    PREMIUM_DAYS,
    PREMIUM_CASH_PRICE,
)

from database import (
    get_user,
    add_balance,
    remove_balance,
    activate_premium,
    remove_premium,
    get_premium_status,
    get_membership_status,
    get_membership_multiplier,
    add_activity,
    record_transaction,
)

DAY_SECONDS = 86400


# ============================================================
# HELPERS
# ============================================================

def _now():
    return int(time.time())


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ============================================================
# PREMIUM STATUS
# ============================================================

def premium_active(user_id):
    status = get_premium_status(user_id)

    if not isinstance(status, dict):
        return False

    return bool(status.get("active", False))


def premium_expiry(user_id):
    status = get_premium_status(user_id)

    if not isinstance(status, dict):
        return 0

    return _safe_int(
        status.get("expire", 0),
        0,
    )


def premium_status(user_id):
    status = get_premium_status(user_id)

    if not isinstance(status, dict):
        status = {}

    expire = _safe_int(
        status.get("expire", 0),
        0,
    )

    active = bool(
        status.get("active", False)
    )

    # Never report an expired membership as active.
    if expire and expire <= _now():
        active = False

    return {
        "active": active,
        "expires": expire,
        "expire": expire,
    }


# ============================================================
# PREMIUM REMAINING TIME
# ============================================================

def premium_remaining_seconds(user_id):
    expire = premium_expiry(user_id)

    if expire <= 0:
        return 0

    return max(
        0,
        expire - _now(),
    )


def premium_remaining_days(user_id):
    seconds = premium_remaining_seconds(user_id)

    if seconds <= 0:
        return 0

    return (
        seconds + DAY_SECONDS - 1
    ) // DAY_SECONDS


# ============================================================
# PREMIUM PURCHASE
# ============================================================

def purchase_premium(user_id):
    user = get_user(
        user_id,
        create=False,
    )

    if not user:
        return (
            False,
            "User not found.",
        )

    if user.get("banned", False):
        return (
            False,
            "Your account is banned.",
        )

    if user.get("blacklisted", False):
        return (
            False,
            "Your account is restricted.",
        )

    if premium_active(user_id):
        return (
            False,
            "Premium is already active.",
        )

    price = _safe_int(
        PREMIUM_PRICE,
        0,
    )

    days = _safe_int(
        PREMIUM_DAYS,
        0,
    )

    if price <= 0 or days <= 0:
        return (
            False,
            "Premium configuration is invalid.",
        )

    removed = remove_balance(
        user_id,
        price,
    )

    if not removed:
        return (
            False,
            "Insufficient balance.",
        )

    try:
        activated = activate_premium(
            user_id,
            days=days,
        )
    except Exception:
        activated = False

    if not activated:
        try:
            add_balance(
                user_id,
                price,
            )
        except Exception:
            pass

        return (
            False,
            "Premium activation failed. Your balance was refunded.",
        )

    expires = premium_expiry(
        user_id
    )

    try:
        add_activity(
            user_id,
            "premium_purchase",
            price,
        )
    except Exception:
        pass

    try:
        record_transaction(
            user_id=user_id,
            transaction_type="premium_purchase",
            amount=-price,
            source="premium_purchase",
            metadata={
                "days": days,
                "expires": expires,
                "price": price,
            },
                )
    except Exception:
        pass

    return (
        True,
        {
            "price": price,
            "days": days,
            "expires": expires,
            "remaining_days":
                premium_remaining_days(
                    user_id
                ),
        },
    )


# ============================================================
# PREMIUM RENEWAL
# ============================================================

def renew_premium(user_id):
    user = get_user(
        user_id,
        create=False,
    )

    if not user:
        return (
            False,
            "User not found.",
        )

    if user.get("banned", False):
        return (
            False,
            "Your account is banned.",
        )

    if user.get("blacklisted", False):
        return (
            False,
            "Your account is restricted.",
        )

    price = _safe_int(
        PREMIUM_PRICE,
        0,
    )

    days = _safe_int(
        PREMIUM_DAYS,
        0,
    )

    if price <= 0 or days <= 0:
        return (
            False,
            "Premium configuration is invalid.",
        )

    removed = remove_balance(
        user_id,
        price,
    )

    if not removed:
        return (
            False,
            "Insufficient balance.",
        )

    try:
        activated = activate_premium(
            user_id,
            days=days,
        )
    except Exception:
        activated = False

    if not activated:
        try:
            add_balance(
                user_id,
                price,
            )
        except Exception:
            pass

        return (
            False,
            "Premium renewal failed. Your balance was refunded.",
        )

    expires = premium_expiry(
        user_id
    )

    try:
        add_activity(
            user_id,
            "premium_renewal",
            price,
        )
    except Exception:
        pass

    try:
        record_transaction(
            user_id=user_id,
            transaction_type="premium_renewal",
            amount=-price,
            source="premium_renewal",
            metadata={
                "days": days,
                "expires": expires,
                "price": price,
            },
                )
    except Exception:
        pass

    return (
        True,
        {
            "price": price,
            "days": days,
            "expires": expires,
            "remaining_days":
                premium_remaining_days(
                    user_id
                ),
        },
    )


# ============================================================
# ADMIN GRANT
# ============================================================

def grant_premium(
    user_id,
    days=30,
):
    days = _safe_int(
        days,
        0,
    )

    if days <= 0:
        return False

    return bool(
        activate_premium(
            user_id,
            days=days,
        )
    )


# ============================================================
# ADMIN REVOKE
# ============================================================

def revoke_premium(user_id):
    return bool(
        remove_premium(
            user_id
        )
    )


# ============================================================
# PREMIUM BENEFITS
# ============================================================

def premium_daily_multiplier(user_id):
    try:
        return float(
            get_membership_multiplier(
                user_id
            )
        )
    except Exception:
        return 1.0


def premium_is_benefit_active(user_id):
    return premium_active(
        user_id
    )


# ============================================================
# MEMBERSHIP STATUS
# ============================================================

def membership_status(user_id):
    try:
        return get_membership_status(
            user_id
        )
    except Exception:
        return premium_status(
            user_id
        )


def membership_multiplier(user_id):
    try:
        return float(
            get_membership_multiplier(
                user_id
            )
        )
    except Exception:
        return 1.0


# ============================================================
# PREMIUM SUMMARY
# ============================================================

def get_premium_summary(user_id):
    status = premium_status(
        user_id
    )

    return {
        "active": status["active"],
        "expires": status["expires"],
        "remaining_seconds":
            premium_remaining_seconds(
                user_id
            ),
        "remaining_days":
            premium_remaining_days(
                user_id
            ),
        "price":
            _safe_int(
                PREMIUM_PRICE,
                0,
            ),
        "days":
            _safe_int(
                PREMIUM_DAYS,
                0,
            ),
        "daily_multiplier":
            premium_daily_multiplier(
                user_id
            ),
    }


# ============================================================
# PREMIUM PAGE
# ============================================================

async def premium_page(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user_id = query.from_user.id
    user = get_user(
        user_id,
        create=False,
    )

    if not user:
        await query.edit_message_text(
            "⚠️ User account not found."
        )
        return

    if user.get("banned", False):
        await query.edit_message_text(
            "🚫 Your account has been banned."
        )
        return

    if user.get("blacklisted", False):
        await query.edit_message_text(
            "🚫 Your account is restricted."
        )
        return

    status = get_premium_summary(
        user_id
    )

    if status["active"]:
        text = (
            "👑 **PREMIUM ACTIVE**\n\n"
            f"⏳ Remaining: "
            f"{status['remaining_days']} days\n"
            f"⚡ Multiplier: "
            f"{status['daily_multiplier']}x\n\n"
            "Premium is currently active.\n\n✨ Benefits:\n• Earning reward multiplier\n• Premium-only reward opportunities\n• Priority membership features\n• Extra membership perks."
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "🔄 Renew Premium",
                    callback_data="premium_renew",
                )
            ],
            [
                InlineKeyboardButton(
                    "🏠 Home",
                    callback_data="home",
                )
            ],
        ]

    else:
        text = (
            "👑 **PREMIUM MEMBERSHIP**\n\n"
            f"💰 Price: ৳{PREMIUM_CASH_PRICE:g}\n"
            f"⏳ Duration: "
            f"{status['days']} days\n\n"
            "✨ Premium benefits:\n"
            f"• {status['daily_multiplier']:g}x earning multiplier\n"
            "• Premium status for 30 days\n"
            "• Premium-only reward opportunities\n"
            "• Priority membership features\n\n"
            "💳 Payment: bKash / Nagad / Bybit\n"
            "👇 Choose an option:"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "💳 Buy Premium",
                    callback_data="premium_buy",
                )
            ],
            [
                InlineKeyboardButton(
                    "🏠 Home",
                    callback_data="home",
                )
            ],
        ]

    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
        parse_mode="Markdown",
    )


# ============================================================
# PREMIUM BUY CALLBACK
# ============================================================

async def premium_buy(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user_id = query.from_user.id

    success, result = purchase_premium(
        user_id
    )

    if not success:
        await query.edit_message_text(
            f"❌ **Premium Purchase Failed**\n\n"
            f"{result}",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "👑 Premium",
                            callback_data="premium",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🏠 Home",
                            callback_data="home",
                        )
                    ],
                ]
            ),
            parse_mode="Markdown",
        )
        return

    await query.edit_message_text(
        "🎉 **PREMIUM ACTIVATED!**\n\n"
        f"💰 Paid: "
        f"{result['price']} Points\n"
        f"⏳ Duration: "
        f"{result['days']} days\n"
        f"📅 Remaining: "
        f"{result['remaining_days']} days\n\n"
        "👑 Enjoy your Premium benefits!",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "👑 Premium",
                        callback_data="premium",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🏠 Home",
                        callback_data="home",
                    )
                ],
            ]
        ),
        parse_mode="Markdown",
    )


# ============================================================
# PREMIUM RENEW CALLBACK
# ============================================================

async def premium_renew(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user_id = query.from_user.id

    success, result = renew_premium(
        user_id
    )

    if not success:
        await query.edit_message_text(
            f"❌ **Premium Renewal Failed**\n\n"
            f"{result}",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "👑 Premium",
                            callback_data="premium",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🏠 Home",
                            callback_data="home",
                        )
                    ],
                ]
            ),
            parse_mode="Markdown",
        )
        return

    await query.edit_message_text(
        "🎉 **PREMIUM RENEWED!**\n\n"
        f"💰 Paid: "
        f"{result['price']} Points\n"
        f"⏳ Added: "
        f"{result['days']} days\n"
        f"📅 Remaining: "
        f"{result['remaining_days']} days\n\n"
        "👑 Premium has been extended!",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "👑 Premium",
                        callback_data="premium",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🏠 Home",
                        callback_data="home",
                    )
                ],
            ]
        ),
        parse_mode="Markdown",
    )


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "premium_active",
    "premium_expiry",
    "premium_status",
    "premium_remaining_seconds",
    "premium_remaining_days",
    "purchase_premium",
    "renew_premium",
    "grant_premium",
    "revoke_premium",
    "premium_daily_multiplier",
    "premium_is_benefit_active",
    "membership_status",
    "membership_multiplier",
    "get_premium_summary",
    "premium_page",
    "premium_buy",
    "premium_renew",
            ]
            
