import logging
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import MIN_WITHDRAW
from database import get_user, reserve_withdrawal, get_withdrawals

logger = logging.getLogger(__name__)

METHODS = {
    "bkash": "bKash",
    "nagad": "Nagad",
    "bybit": "Bybit",
}


def withdraw_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 bKash", callback_data="withdraw_method_bkash")],
        [InlineKeyboardButton("📱 Nagad", callback_data="withdraw_method_nagad")],
        [InlineKeyboardButton("💎 Bybit", callback_data="withdraw_method_bybit")],
        [InlineKeyboardButton("📜 Withdrawal History", callback_data="withdraw_history")],
        [InlineKeyboardButton("🏠 Home", callback_data="home")],
    ])


def cancel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="withdraw_cancel")]
    ])


def confirm_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirm", callback_data="withdraw_confirm"),
        InlineKeyboardButton("❌ Cancel", callback_data="withdraw_cancel"),
    ]])


def after_withdraw_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💸 Withdraw", callback_data="withdraw")],
        [InlineKeyboardButton("🏠 Home", callback_data="home")],
    ])


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_user(user_id):
    try:
        return get_user(user_id, create=False)
    except TypeError:
        return get_user(user_id)


def _blocked(user):
    return bool(
        not user or
        user.get("banned", False) or
        user.get("blacklisted", False)
    )


def _clear_session(context):
    for key in (
        "withdraw_method",
        "withdraw_amount",
        "withdraw_account",
        "withdraw_step",
    ):
        context.user_data.pop(key, None)


def _method_from_callback(data):
    prefix = "withdraw_method_"
    if not isinstance(data, str) or not data.startswith(prefix):
        return None
    method = data[len(prefix):].strip().lower()
    return method if method in METHODS else None


def _valid_account(method, account):
    account = str(account or "").strip()
    if not 3 <= len(account) <= 100:
        return False

    if method in {"bkash", "nagad"}:
        digits = re.sub(r"[\s\-+]", "", account)
        return (
            (len(digits) == 11 and digits.startswith("01") and digits.isdigit())
            or
            (len(digits) == 13 and digits.startswith("8801") and digits.isdigit())
        )

    if method == "bybit":
        return account.isdigit() and 4 <= len(account) <= 20

    return False


def _history_for_user(user_id, limit=50):
    try:
        records = get_withdrawals(limit=limit)
    except TypeError:
        records = get_withdrawals(limit)

    return [
        item for item in (records or [])
        if isinstance(item, dict)
        and str(item.get("user_id")) == str(user_id)
    ]


async def withdraw_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    user = _get_user(query.from_user.id)

    if not user:
        await query.answer("⚠️ Account not found.", show_alert=True)
        return

    if user.get("banned", False):
        await query.answer("🚫 Your account is banned.", show_alert=True)
        return

    if user.get("blacklisted", False):
        await query.answer("🚫 Your account is restricted.", show_alert=True)
        return

    balance = max(0, _safe_int(user.get("balance", 0)))
    pending = max(0, _safe_int(user.get("withdraw_pending", 0)))

    await query.answer()
    await query.edit_message_text(
        "💸 **WITHDRAWAL CENTER**\n\n"
        f"💰 Available: {balance} Points\n"
        f"🟡 Pending: {pending} Points\n"
        f"📌 Minimum: {MIN_WITHDRAW} Points\n\n"
        "Select your payment method:",
        reply_markup=withdraw_keyboard(),
        parse_mode="Markdown",
    )


async def select_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    method = _method_from_callback(query.data)
    if not method:
        await query.answer("❌ Invalid payment method.", show_alert=True)
        return

    user = _get_user(query.from_user.id)
    if _blocked(user):
        await query.answer("🚫 Your account is restricted.", show_alert=True)
        return

    balance = max(0, _safe_int(user.get("balance", 0)))
    if balance < MIN_WITHDRAW:
        await query.answer(
            f"Minimum withdrawal is {MIN_WITHDRAW} points.",
            show_alert=True,
        )
        return

    _clear_session(context)
    context.user_data["withdraw_method"] = method
    context.user_data["withdraw_step"] = "amount"

    await query.answer()
    await query.edit_message_text(
        "💸 **WITHDRAWAL AMOUNT**\n\n"
        f"💰 Available: {balance} Points\n"
        f"📌 Minimum: {MIN_WITHDRAW} Points\n\n"
        "Send the amount you want to withdraw.\n\n"
        "Example: `1000`",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown",
    )


async def withdraw_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return False

    step = context.user_data.get("withdraw_step")
    if not step:
        return False

    user_id = message.from_user.id
    user = _get_user(user_id)

    if _blocked(user):
        _clear_session(context)
        await message.reply_text("🚫 Your account is not allowed to withdraw.")
        return True

    text = (message.text or "").strip()

    if step == "amount":
        try:
            amount = int(text)
        except (TypeError, ValueError):
            await message.reply_text(
                "❌ Please send a valid whole number.",
                reply_markup=cancel_keyboard(),
            )
            return True

        if amount < MIN_WITHDRAW:
            await message.reply_text(
                f"❌ Minimum withdrawal is {MIN_WITHDRAW} points.",
                reply_markup=cancel_keyboard(),
            )
            return True

        balance = max(0, _safe_int(user.get("balance", 0)))
        if amount > balance:
            await message.reply_text(
                f"❌ Insufficient balance.\n\nYour balance: {balance} Points",
                reply_markup=cancel_keyboard(),
            )
            return True

        context.user_data["withdraw_amount"] = amount
        context.user_data["withdraw_step"] = "account"

        method = context.user_data.get("withdraw_method", "")
        name = METHODS.get(method, method)
        example = "`017XXXXXXXX`" if method in {"bkash", "nagad"} else "`123456789`"

        await message.reply_text(
            f"💳 **{name} ACCOUNT**\n\n"
            "Send your payment account/number.\n\n"
            f"Example:\n{example}",
            reply_markup=cancel_keyboard(),
            parse_mode="Markdown",
        )
        return True

    if step == "account":
        method = context.user_data.get("withdraw_method")
        account = text

        if not _valid_account(method, account):
            error = (
                "❌ Invalid account. Use an 11-digit Bangladesh mobile number "
                "such as `017XXXXXXXX`."
                if method in {"bkash", "nagad"}
                else "❌ Invalid Bybit UID. Please send your numeric Bybit UID."
                if method == "bybit"
                else "❌ Invalid payment account."
            )
            await message.reply_text(
                error,
                reply_markup=cancel_keyboard(),
                parse_mode="Markdown",
            )
            return True

        amount = _safe_int(context.user_data.get("withdraw_amount", 0))
        if amount < MIN_WITHDRAW:
            _clear_session(context)
            await message.reply_text("⚠️ Withdrawal session expired. Please start again.")
            return True

        context.user_data["withdraw_account"] = account
        context.user_data["withdraw_step"] = "confirm"

        name = METHODS.get(method, method)
        await message.reply_text(
            "🧾 **CONFIRM WITHDRAWAL**\n\n"
            f"💰 Amount: {amount} Points\n"
            f"💳 Method: {name}\n"
            f"👤 Account: `{account}`\n\n"
            "Please confirm your withdrawal.",
            reply_markup=confirm_keyboard(),
            parse_mode="Markdown",
        )
        return True

    return False


async def confirm_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    user_id = query.from_user.id
    method = context.user_data.get("withdraw_method")
    amount = _safe_int(context.user_data.get("withdraw_amount", 0))
    account = str(context.user_data.get("withdraw_account", "")).strip()

    if (
        method not in METHODS
        or amount <= 0
        or amount < MIN_WITHDRAW
        or not _valid_account(method, account)
    ):
        _clear_session(context)
        await query.answer("⚠️ Withdrawal session expired.", show_alert=True)
        return

    user = _get_user(user_id)
    if _blocked(user):
        _clear_session(context)
        await query.answer("🚫 Your account is restricted.", show_alert=True)
        return

    balance = max(0, _safe_int(user.get("balance", 0)))
    if amount > balance:
        _clear_session(context)
        await query.answer("❌ Insufficient balance.", show_alert=True)
        return

    try:
        withdrawal = reserve_withdrawal(
            user_id=user_id,
            amount=amount,
            method=method,
            payment_account=account,
        )
    except Exception:
        logger.exception("reserve_withdrawal failed | user=%s", user_id)
        withdrawal = None

    if not withdrawal:
        await query.answer(
            "❌ Withdrawal could not be created.",
            show_alert=True,
        )
        return

    _clear_session(context)

    await query.answer("✅ Withdrawal submitted.", show_alert=True)
    await query.edit_message_text(
        "✅ **WITHDRAWAL SUBMITTED**\n\n"
        f"🆔 ID: `{withdrawal.get('withdrawal_id', 'N/A')}`\n"
        f"💰 Amount: {_safe_int(withdrawal.get('amount', amount), amount)} Points\n"
        f"💳 Method: {withdrawal.get('method', method)}\n"
        f"👤 Account: `{withdrawal.get('payment_account', account)}`\n"
        f"🟡 Status: {withdrawal.get('status', 'pending')}\n\n"
        "Admin will review your request.",
        parse_mode="Markdown",
        reply_markup=after_withdraw_keyboard(),
    )


async def cancel_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _clear_session(context)

    if not query:
        return

    await query.answer("Withdrawal cancelled.")
    await query.edit_message_text(
        "❌ **WITHDRAWAL CANCELLED**",
        reply_markup=after_withdraw_keyboard(),
        parse_mode="Markdown",
    )


async def withdrawal_history_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    user_id = query.from_user.id
    user = _get_user(user_id)

    if _blocked(user):
        await query.answer("🚫 Your account is restricted.", show_alert=True)
        return

    records = _history_for_user(user_id, 50)

    if not records:
        await query.answer()
        await query.edit_message_text(
            "📜 **WITHDRAWAL HISTORY**\n\nNo withdrawal history found.",
            reply_markup=withdraw_keyboard(),
            parse_mode="Markdown",
        )
        return

    lines = ["📜 **WITHDRAWAL HISTORY**", ""]

    for item in records[:10]:
        lines.extend([
            f"🆔 `{item.get('withdrawal_id', 'N/A')}`",
            f"💰 {_safe_int(item.get('amount', 0))} Points",
            f"💳 {item.get('method', 'N/A')}",
            f"📌 {item.get('status', 'unknown')}",
            "",
        ])

    await query.answer()
    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=withdraw_keyboard(),
        parse_mode="Markdown",
    )


HANDLER_FUNCTIONS = {
    "withdraw": withdraw_page,
    "withdraw_page": withdraw_page,
    "withdraw_method": select_method,
    "select_method": select_method,
    "withdraw_text_handler": withdraw_text_handler,
    "withdraw_confirm": confirm_withdrawal,
    "confirm_withdrawal": confirm_withdrawal,
    "withdraw_cancel": cancel_withdrawal,
    "cancel_withdrawal": cancel_withdrawal,
    "withdraw_history": withdrawal_history_page,
    "withdrawal_history": withdrawal_history_page,
}


__all__ = [
    "METHODS",
    "withdraw_keyboard",
    "cancel_keyboard",
    "confirm_keyboard",
    "withdraw_page",
    "select_method",
    "withdraw_text_handler",
    "confirm_withdrawal",
    "cancel_withdrawal",
    "withdrawal_history_page",
    "HANDLER_FUNCTIONS",
]
