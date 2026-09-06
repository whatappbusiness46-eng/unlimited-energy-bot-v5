# ============================================================
# vip.py
# COMPLETE VIP SYSTEM
# ============================================================

import logging
import time

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes

from config import VIP1_CASH_PRICE, VIP2_CASH_PRICE, VIP3_CASH_PRICE, VIP4_CASH_PRICE, VIP5_CASH_PRICE

from database import (
    get_user,
    get_vip_status,
    get_membership_status,
    get_membership_multiplier,
    get_extra_spins,
    activate_vip,
    remove_vip,
    add_activity,
    remove_balance,
    add_balance,
    record_transaction,
    is_vip_purchase_enabled,
)


logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTS
# ============================================================

DAY_SECONDS = 86400

VIP_LEVELS = {
    1: {
        "daily_multiplier": 1.30,
        "extra_spins": 1,
    },
    2: {
        "daily_multiplier": 1.40,
        "extra_spins": 2,
    },
    3: {
        "daily_multiplier": 1.50,
        "extra_spins": 3,
    },
    4: {
        "daily_multiplier": 1.75,
        "extra_spins": 4,
    },
    5: {
        "daily_multiplier": 2.00,
        "extra_spins": 5,
    },
}


# ============================================================
# VIP PRICES
# ============================================================
# Change these values if you want different prices.

VIP_PRICES = {
    1: 100,
    2: 200,
    3: 300,
    4: 450,
    5: 600,
}

VIP_DAYS = 30


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


def _safe_float(value, default=1.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _get_user(user_id):
    try:
        return get_user(
            user_id,
            create=False,
        )
    except TypeError:
        return get_user(user_id)


def _get_vip_status(user_id):
    try:
        status = get_vip_status(user_id)
    except Exception:
        logger.exception(
            "Failed to read VIP status | user=%s",
            user_id,
        )
        return {}

    return status if isinstance(status, dict) else {}


def _home_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🏠 Home",
                    callback_data="home",
                )
            ]
        ]
    )


def _vip_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💎 VIP Menu",
                    callback_data="vip",
                )
            ],
            [
                InlineKeyboardButton(
                    "🏠 Home",
                    callback_data="home",
                )
            ],
        ]
    )


def get_vip_price(level):
    level = _safe_int(level, 0)

    if level not in VIP_LEVELS:
        return 0

    return int(VIP_PRICES.get(level, 0))


# ============================================================
# VALIDATION
# ============================================================

def is_valid_vip_level(level):
    level = _safe_int(level, 0)
    return level in VIP_LEVELS


# ============================================================
# VIP STATUS
# ============================================================

def vip_active(user_id):
    status = _get_vip_status(user_id)

    active = bool(
        status.get(
            "active",
            False,
        )
    )

    expire = _safe_int(
        status.get(
            "expire",
            0,
        ),
        0,
    )

    if expire > 0 and expire <= _now():
        return False

    return active


def vip_level(user_id):
    if not vip_active(user_id):
        return 0

    status = _get_vip_status(user_id)

    level = _safe_int(
        status.get(
            "level",
            0,
        ),
        0,
    )

    return (
        level
        if is_valid_vip_level(level)
        else 0
    )


def vip_expiry(user_id):
    status = _get_vip_status(user_id)

    return _safe_int(
        status.get(
            "expire",
            0,
        ),
        0,
    )


# ============================================================
# REMAINING TIME
# ============================================================

def vip_remaining_seconds(user_id):
    expire = vip_expiry(user_id)

    if expire <= 0:
        return 0

    return max(
        0,
        expire - _now(),
    )


def vip_remaining_days(user_id):
    seconds = vip_remaining_seconds(user_id)

    if seconds <= 0:
        return 0

    return (
        seconds + DAY_SECONDS - 1
    ) // DAY_SECONDS


# ============================================================
# BENEFITS
# ============================================================

def get_vip_benefits(level):
    level = _safe_int(level, 0)

    benefits = VIP_LEVELS.get(level)

    if not benefits:
        return {
            "daily_multiplier": 1.0,
            "extra_spins": 0,
        }

    return dict(benefits)


def vip_multiplier(user_id):
    try:
        return _safe_float(
            get_membership_multiplier(
                user_id
            ),
            1.0,
        )
    except Exception:
        logger.exception(
            "Failed to get membership multiplier | user=%s",
            user_id,
        )
        return 1.0


def vip_extra_spins(user_id):
    try:
        return max(
            0,
            _safe_int(
                get_extra_spins(
                    user_id
                ),
                0,
            ),
        )
    except Exception:
        logger.exception(
            "Failed to get extra spins | user=%s",
            user_id,
        )
        return 0


# ============================================================
# VIP SUMMARY
# ============================================================

def get_vip_summary(user_id):
    status = _get_vip_status(user_id)

    level = _safe_int(
        status.get(
            "level",
            0,
        ),
        0,
    )

    expire = _safe_int(
        status.get(
            "expire",
            0,
        ),
        0,
    )

    active = bool(
        status.get(
            "active",
            False,
        )
    )

    if expire > 0 and expire <= _now():
        active = False

    if not is_valid_vip_level(level):
        level = 0

    benefits = get_vip_benefits(level)

    multiplier = _safe_float(
        status.get(
            "daily_multiplier",
            benefits["daily_multiplier"],
        ),
        benefits["daily_multiplier"],
    )

    extra_spins = max(
        0,
        _safe_int(
            status.get(
                "extra_spins",
                benefits["extra_spins"],
            ),
            benefits["extra_spins"],
        ),
    )

    if not active:
        level = 0
        multiplier = 1.0
        extra_spins = 0

    return {
        "active": active,
        "level": level,
        "expire": expire,
        "remaining_seconds": (
            vip_remaining_seconds(user_id)
        ),
        "remaining_days": (
            vip_remaining_days(user_id)
        ),
        "daily_multiplier": multiplier,
        "extra_spins": extra_spins,
    }


# ============================================================
# GRANT VIP
# ============================================================

def grant_vip(
    user_id,
    level=1,
    days=30,
):
    level = _safe_int(level, 0)
    days = _safe_int(days, 0)

    if not is_valid_vip_level(level):
        return False

    if days <= 0:
        return False

    user = _get_user(user_id)

    if not user:
        return False

    if (
        user.get("banned", False)
        or user.get("blacklisted", False)
    ):
        return False

    try:
        success = activate_vip(
            user_id,
            level=level,
            days=days,
        )
    except Exception:
        logger.exception(
            "VIP grant failed | user=%s",
            user_id,
        )
        return False

    if not success:
        return False

    try:
        add_activity(
            user_id,
            "vip_granted",
            0,
        )
    except Exception:
        logger.exception(
            "VIP grant activity failed | user=%s",
            user_id,
        )

    return True


# ============================================================
# EXTEND / UPGRADE VIP
# ============================================================

def extend_vip(
    user_id,
    level=None,
    days=30,
):
    days = _safe_int(days, 0)

    if days <= 0:
        return False

    current_level = vip_level(user_id)

    if level is None:
        level = (
            current_level
            if current_level > 0
            else 1
        )

    level = _safe_int(level, 0)

    if not is_valid_vip_level(level):
        return False

    user = _get_user(user_id)

    if not user:
        return False

    if (
        user.get("banned", False)
        or user.get("blacklisted", False)
    ):
        return False

    try:
        success = activate_vip(
            user_id,
            level=level,
            days=days,
        )
    except Exception:
        logger.exception(
            "VIP extension failed | user=%s",
            user_id,
        )
        return False

    if not success:
        return False

    try:
        add_activity(
            user_id,
            "vip_extended",
            0,
        )
    except Exception:
        logger.exception(
            "VIP extension activity failed | user=%s",
            user_id,
        )

    return True


# ============================================================
# REVOKE VIP
# ============================================================

def revoke_vip(user_id):
    user = _get_user(user_id)

    if not user:
        return False

    try:
        success = remove_vip(user_id)
    except Exception:
        logger.exception(
            "VIP revoke failed | user=%s",
            user_id,
        )
        return False

    if success:
        try:
            add_activity(
                user_id,
                "vip_revoked",
                0,
            )
        except Exception:
            logger.exception(
                "VIP revoke activity failed | user=%s",
                user_id,
            )

    return bool(success)


# ============================================================
# MEMBERSHIP SUMMARY
# ============================================================

def membership_summary(user_id):
    try:
        status = get_membership_status(
            user_id
        )
    except Exception:
        logger.exception(
            "Membership status failed | user=%s",
            user_id,
        )
        status = {}

    if not isinstance(status, dict):
        status = {}

    premium_expire = _safe_int(
        status.get(
            "premium_expire",
            0,
        ),
        0,
    )

    vip_expire = _safe_int(
        status.get(
            "vip_expire",
            0,
        ),
        0,
    )

    premium = bool(
        status.get(
            "premium",
            False,
        )
    )

    vip = bool(
        status.get(
            "vip",
            False,
        )
    )

    now = _now()

    if (
        premium_expire > 0
        and premium_expire <= now
    ):
        premium = False

    if (
        vip_expire > 0
        and vip_expire <= now
    ):
        vip = False

    return {
        "premium": premium,
        "premium_expire": premium_expire,
        "vip": vip,
        "vip_level": (
            vip_level(user_id)
            if vip
            else 0
        ),
        "vip_expire": vip_expire,
        "multiplier": (
            vip_multiplier(user_id)
        ),
        "extra_spins": (
            vip_extra_spins(user_id)
        ),
    }


# ============================================================
# VIP PAGE
# ============================================================

async def vip_page(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = query.from_user

    if not user:
        return

    user_id = user.id

    db_user = _get_user(user_id)

    if not db_user:
        await query.edit_message_text(
            "⚠️ User account not found.",
            reply_markup=_home_keyboard(),
        )
        return

    if (
        db_user.get("banned", False)
        or db_user.get("blacklisted", False)
    ):
        await query.edit_message_text(
            "🚫 Your account is restricted.",
            reply_markup=_home_keyboard(),
        )
        return

    summary = get_vip_summary(user_id)

    if summary["active"]:
        text = (
            "💎 **VIP MEMBERSHIP**\n\n"
            f"🏆 Current Level: "
            f"**VIP {summary['level']}**\n"
            f"⏳ Remaining: "
            f"**{summary['remaining_days']} days**\n"
            f"⚡ Multiplier: "
            f"**{summary['daily_multiplier']}x**\n"
            f"🎡 Extra Spins: "
            f"**{summary['extra_spins']}**\n\n"
            "Choose a level below to renew "
            "or upgrade your VIP."
        )
    else:
        text = (
            "💎 **VIP MEMBERSHIP**\n\n"
            "Choose your VIP level:\n\n"
            "🥉 VIP 1 — 1.30x + 1 Spin\n"
            "🥈 VIP 2 — 1.40x + 2 Spins\n"
            "🥇 VIP 3 — 1.50x + 3 Spins\n"
            "💎 VIP 4 — 1.75x + 4 Spins\n"
            "👑 VIP 5 — 2.00x + 5 Spins\n\n"
            "💰 **Cash Prices:**\n"
            f"VIP 1 — ৳{VIP1_CASH_PRICE:g}\n"
            f"VIP 2 — ৳{VIP2_CASH_PRICE:g}\n"
            f"VIP 3 — ৳{VIP3_CASH_PRICE:g}\n"
            f"VIP 4 — ৳{VIP4_CASH_PRICE:g}\n"
            f"VIP 5 — ৳{VIP5_CASH_PRICE:g}\n\n"
            "💳 Payment: bKash / Nagad / Bybit\n"
            "Select a level to purchase."
        )

    keyboard = [
        [
            InlineKeyboardButton(
                f"VIP 1 — ৳{VIP1_CASH_PRICE:g}",
                callback_data="vip_level_1",
            ),
            InlineKeyboardButton(
                f"VIP 2 — ৳{VIP2_CASH_PRICE:g}",
                callback_data="vip_level_2",
            ),
        ],
        [
            InlineKeyboardButton(
                f"VIP 3 — ৳{VIP3_CASH_PRICE:g}",
                callback_data="vip_level_3",
            ),
            InlineKeyboardButton(
                f"VIP 4 — ৳{VIP4_CASH_PRICE:g}",
                callback_data="vip_level_4",
            ),
        ],
        [
            InlineKeyboardButton(
                f"VIP 5 — ৳{VIP5_CASH_PRICE:g}",
                callback_data="vip_level_5",
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
# VIP PURCHASE
# ============================================================

async def vip_purchase_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = query.from_user

    if not user:
        return

    user_id = user.id
    data = str(query.data or "")

    # --------------------------------------------------------
    # Global VIP purchase switch
    # --------------------------------------------------------
    if not is_vip_purchase_enabled():
        await query.edit_message_text(
            "🔴 **VIP Purchase is currently OFF**\n\n"
            "Please try again later.",
            reply_markup=_vip_keyboard(),
            parse_mode="Markdown",
        )
        return

    # --------------------------------------------------------
    # Extract level
    # --------------------------------------------------------

    if not data.startswith("vip_level_"):
        await query.edit_message_text(
            "⚠️ Invalid VIP purchase.",
            reply_markup=_vip_keyboard(),
        )
        return

    try:
        level = int(
            data.rsplit("_", 1)[1]
        )
    except (
        TypeError,
        ValueError,
        IndexError,
    ):
        await query.edit_message_text(
            "⚠️ Invalid VIP level.",
            reply_markup=_vip_keyboard(),
        )
        return

    if not is_valid_vip_level(level):
        await query.edit_message_text(
            "⚠️ Invalid VIP level.",
            reply_markup=_vip_keyboard(),
        )
        return

    price = get_vip_price(level)

    if price <= 0:
        await query.edit_message_text(
            "⚠️ VIP price is not configured.",
            reply_markup=_vip_keyboard(),
        )
        return

    # --------------------------------------------------------
    # User validation
    # --------------------------------------------------------

    user_data = _get_user(user_id)

    if not user_data:
        await query.edit_message_text(
            "⚠️ User account not found.",
            reply_markup=_home_keyboard(),
        )
        return

    if (
        user_data.get("banned", False)
        or user_data.get("blacklisted", False)
    ):
        await query.edit_message_text(
            "🚫 Your account is restricted.",
            reply_markup=_home_keyboard(),
        )
        return

    # --------------------------------------------------------
    # Current VIP
    # --------------------------------------------------------

    current_level = vip_level(user_id)
    currently_active = vip_active(user_id)

    # Do not allow downgrade
    if currently_active and level < current_level:
        await query.edit_message_text(
            "⚠️ **Downgrade Not Allowed**\n\n"
            f"Current VIP: **VIP {current_level}**\n"
            f"Selected: **VIP {level}**\n\n"
            "You can renew your current VIP "
            "or upgrade to a higher level.",
            reply_markup=_vip_keyboard(),
            parse_mode="Markdown",
        )
        return

    # --------------------------------------------------------
    # Balance check
    # --------------------------------------------------------

    balance = _safe_int(
        user_data.get(
            "balance",
            0,
        ),
        0,
    )

    if balance < price:
        needed = price - balance

        await query.edit_message_text(
            "❌ **Insufficient Balance**\n\n"
            f"💎 VIP Level: **VIP {level}**\n"
            f"💰 Price: **{price}**\n"
            f"💵 Balance: **{balance}**\n"
            f"📉 Needed: **{needed}**",
            reply_markup=_vip_keyboard(),
            parse_mode="Markdown",
        )
        return

    # --------------------------------------------------------
    # Confirm purchase
    # --------------------------------------------------------

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Confirm Purchase",
                callback_data=(
                    f"vip_confirm_{level}"
                ),
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="vip",
            )
        ],
    ]

    await query.edit_message_text(
        "💎 **VIP PURCHASE**\n\n"
        f"🏆 Level: **VIP {level}**\n"
        f"💰 Price: **{price}**\n"
        f"⏳ Duration: **{VIP_DAYS} days**\n\n"
        f"💵 Your Balance: **{balance}**\n"
        f"💵 After Purchase: **{balance - price}**\n\n"
        "Confirm your purchase below.",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
        parse_mode="Markdown",
    )
# ============================================================
# CONFIRM VIP PURCHASE
# ============================================================

async def vip_confirm_purchase_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = query.from_user

    if not user:
        return

    user_id = user.id

    # Re-check at confirmation time so a purchase cannot bypass
    # the admin switch using an old confirmation message.
    if not is_vip_purchase_enabled():
        await query.edit_message_text(
            "🔴 **VIP Purchase is currently OFF**\n\n"
            "This purchase was not processed.",
            reply_markup=_vip_keyboard(),
            parse_mode="Markdown",
        )
        return
    data = str(query.data or "")

    try:
        level = int(
            data.rsplit("_", 1)[1]
        )
    except (
        TypeError,
        ValueError,
        IndexError,
    ):
        await query.edit_message_text(
            "⚠️ Invalid purchase.",
            reply_markup=_vip_keyboard(),
        )
        return

    if not is_valid_vip_level(level):
        await query.edit_message_text(
            "⚠️ Invalid VIP level.",
            reply_markup=_vip_keyboard(),
        )
        return

    price = get_vip_price(level)

    if price <= 0:
        await query.edit_message_text(
            "⚠️ VIP price is not configured.",
            reply_markup=_vip_keyboard(),
        )
        return

    user_data = _get_user(user_id)

    if not user_data:
        await query.edit_message_text(
            "⚠️ User account not found.",
            reply_markup=_home_keyboard(),
        )
        return

    if (
        user_data.get("banned", False)
        or user_data.get("blacklisted", False)
    ):
        await query.edit_message_text(
            "🚫 Your account is restricted.",
            reply_markup=_home_keyboard(),
        )
        return

    current_level = vip_level(user_id)
    currently_active = vip_active(user_id)

    if currently_active and level < current_level:
        await query.edit_message_text(
            "⚠️ You cannot downgrade your VIP.",
            reply_markup=_vip_keyboard(),
        )
        return

    # --------------------------------------------------------
    # Atomic balance deduction
    # --------------------------------------------------------

    try:
        deducted = remove_balance(
            user_id,
            price,
        )
    except Exception:
        logger.exception(
            "VIP balance deduction error | user=%s",
            user_id,
        )
        deducted = 0

    if not deducted:
        await query.edit_message_text(
            "❌ **Payment Failed**\n\n"
            "Your balance is insufficient "
            "or the purchase could not be processed.",
            reply_markup=_vip_keyboard(),
            parse_mode="Markdown",
        )
        return

    # --------------------------------------------------------
    # Activate / extend / upgrade
    # --------------------------------------------------------

    try:
        activated = activate_vip(
            user_id,
            level=level,
            days=VIP_DAYS,
        )
    except Exception:
        logger.exception(
            "VIP activation error | user=%s | level=%s",
            user_id,
            level,
        )
        activated = False

    # --------------------------------------------------------
    # Refund if activation failed
    # --------------------------------------------------------

    if not activated:
        try:
            add_balance(
                user_id,
                price,
            )
        except Exception:
            logger.exception(
                "VIP refund failed | user=%s",
                user_id,
            )

        await query.edit_message_text(
            "❌ **VIP Activation Failed**\n\n"
            "The amount has been refunded.",
            reply_markup=_vip_keyboard(),
            parse_mode="Markdown",
        )
        return

    # --------------------------------------------------------
    # Transaction record
    # --------------------------------------------------------

    try:
        record_transaction(
            user_id=user_id,
            transaction_type="vip_purchase",
            amount=price,
            source="vip_membership",
            status="completed",
            metadata={
                "vip_level": level,
                "duration_days": VIP_DAYS,
                "previous_level": current_level,
                "purchase_type": (
                    "upgrade"
                    if currently_active
                    and level > current_level
                    else (
                        "renewal"
                        if currently_active
                        else "new"
                    )
                ),
            },
        )
    except Exception:
        logger.exception(
            "VIP transaction record failed | user=%s",
            user_id,
        )

    # --------------------------------------------------------
    # Activity
    # --------------------------------------------------------

    try:
        add_activity(
            user_id,
            "vip_purchase",
            price,
        )
    except Exception:
        logger.exception(
            "VIP activity record failed | user=%s",
            user_id,
        )

    # --------------------------------------------------------
    # New status
    # --------------------------------------------------------

    summary = get_vip_summary(user_id)

    new_balance = max(
        0,
        _safe_int(
            get_user(
                user_id,
                create=False,
            ).get(
                "balance",
                0,
            ),
            0,
        ),
    )

    purchase_type = (
        "Upgrade"
        if currently_active
        and level > current_level
        else (
            "Renewal"
            if currently_active
            else "New Membership"
        )
    )

    await query.edit_message_text(
        "🎉 **VIP PURCHASE SUCCESSFUL!**\n\n"
        f"💎 VIP Level: **VIP {level}**\n"
        f"📌 Type: **{purchase_type}**\n"
        f"⏳ Duration Added: **{VIP_DAYS} days**\n"
        f"💰 Paid: **{price}**\n"
        f"💵 Remaining Balance: **{new_balance}**\n\n"
        f"⚡ Multiplier: "
        f"**{summary['daily_multiplier']}x**\n"
        f"🎡 Extra Spins: "
        f"**{summary['extra_spins']}**\n"
        f"⏳ Remaining: "
        f"**{summary['remaining_days']} days**\n\n"
        "✅ Your VIP membership is active.",
        reply_markup=_vip_keyboard(),
        parse_mode="Markdown",
    )


# ============================================================
# VIP LEVEL CALLBACK
# ============================================================
# Kept for compatibility with the old router.
# It now redirects to the paid purchase confirmation.

async def vip_level_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await vip_purchase_callback(
        update,
        context,
    )


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "DAY_SECONDS",
    "VIP_LEVELS",
    "VIP_PRICES",
    "VIP_DAYS",

    "is_valid_vip_level",
    "get_vip_price",

    "vip_active",
    "vip_level",
    "vip_expiry",

    "vip_remaining_seconds",
    "vip_remaining_days",

    "get_vip_benefits",

    "vip_multiplier",
    "vip_extra_spins",

    "get_vip_summary",

    "grant_vip",
    "extend_vip",
    "revoke_vip",

    "membership_summary",

    "vip_page",
    "vip_level_callback",

    "vip_purchase_callback",
    "vip_confirm_purchase_callback",
            ]
