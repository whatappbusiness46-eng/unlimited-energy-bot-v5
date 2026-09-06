from telegram.error import BadRequest
# ============================================================
# callbacks.py
# Unlimited Energy Bot V2
# PART 4 - FINAL CALLBACK ROUTER
# ============================================================

import logging
import time

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import ContextTypes

from config import (
    ADMIN_USERNAME,
    GROUPS,
    VIP_PRICE,
    VIP_DAYS,
)

from database import (
    get_user,
    remove_balance,
    add_balance,
    add_activity,
    convert_bonus_to_balance,
    record_transaction,
 # existing imports...
    is_vip_purchase_enabled,
    set_vip_purchase_enabled,

)

from withdraw import (
    withdraw_page,
    select_method,
    confirm_withdrawal,
    cancel_withdrawal,
    withdrawal_history_page,
)

from handlers import (
    main_menu,
    force_join_menu,
)

from premium import (
    premium_page,
    premium_buy,
    premium_renew,
)

from vip import (
    vip_page,
    vip_level_callback,
    vip_purchase_callback,
    vip_confirm_purchase_callback,
)

from referral import (
    referral_link_callback,
    referral_stats_callback,
    get_milestones,
)

from offers import (
    offers_page,
    offer_callback,
    offer_claim_callback,
    provider_offer_callback,
)

from earn import (
    earn_page,
    daily_bonus,
    shortlinks,
    spin_wheel,
    lucky_box,
    scratch_card,
    energy_page,
    claim_test_task,
)

from tasks import tasks_page as task_menu_page, task_callback, task_complete_callback

from payments import method_keyboard, payment_instructions, create_payment, submit_reference, get_payment
from config import PREMIUM_CASH_PRICE, VIP1_CASH_PRICE, VIP2_CASH_PRICE, VIP3_CASH_PRICE, VIP4_CASH_PRICE, VIP5_CASH_PRICE

from shortlinks import (
    shortlinks_page,
    shortlink_callback,
    shortlink_verify_callback,
)


logger = logging.getLogger(__name__)


# ============================================================
# COMMON KEYBOARDS
# ============================================================

def home_keyboard():

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


def back_earn_keyboard():

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💰 Earn",
                    callback_data="earn",
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


def back_profile_keyboard():

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "👤 Profile",
                    callback_data="profile",
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


# ============================================================
# BALANCE
# ============================================================





async def _fast_callback_answer(query, *args, **kwargs):
    try:
        return await query.answer(*args, **kwargs)
    except Exception:
        return None

async def _safe_edit_message_text(query, text, **kwargs):
    try:
        return await query.edit_message_text(text, **kwargs)
    except BadRequest as exc:
        if "Message is not modified" in str(exc):
            return None
        raise


async def _safe_edit_message_reply_markup(query, **kwargs):
    try:
        return await query.edit_message_reply_markup(**kwargs)
    except BadRequest as exc:
        if "Message is not modified" in str(exc):
            return None
        raise

async def show_balance(
    query,
    user_id,
):

    user = get_user(user_id)

    if not user:

        await _safe_edit_message_text(query, 
            "⚠️ User account not found.",
            reply_markup=home_keyboard(),
        )

        return

    balance = user.get(
        "balance",
        0,
    )

    bonus = user.get(
        "bonus_balance",
        0,
    )

    premium_balance = user.get(
        "premium_balance",
        0,
    )

    total = (
        balance
        + bonus
        + premium_balance
    )

    await _safe_edit_message_text(query, 

        "💰 **YOUR WALLET**\n\n"

        f"💰 Earn Balance: "
        f"{balance} Points\n"

        f"🎁 Bonus Balance: "
        f"{bonus} Points\n"

        f"💎 Premium Balance: "
        f"{premium_balance} Points\n\n"

        f"💵 **Total Balance: "
        f"{total} Points**",

        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Convert Bonus → Balance", callback_data="bonus_convert")],
            [InlineKeyboardButton("🏠 Home", callback_data="home")],
        ]) if int(bonus or 0) > 0 else home_keyboard(),

        parse_mode="Markdown",
    )


# ============================================================
# PROFILE
# ============================================================

async def show_profile(
    query,
    user_id,
):

    user = get_user(user_id)

    if not user:

        await _safe_edit_message_text(query, 
            "⚠️ User account not found.",
            reply_markup=home_keyboard(),
        )

        return

    balance = user.get(
        "balance",
        0,
    )

    bonus = user.get(
        "bonus_balance",
        0,
    )

    premium_balance = user.get(
        "premium_balance",
        0,
    )

    referrals = user.get(
        "referrals",
        0,
    )

    xp = user.get(
        "xp",
        0,
    )

    level = user.get(
        "level",
        1,
    )

    rank = user.get(
        "rank",
        "🔰 Beginner",
    )

    premium = user.get(
        "premium",
        False,
    )

    vip = user.get(
        "vip",
        False,
    )

    premium_status = (
        "✅ Active"
        if premium
        else "❌ Inactive"
    )

    vip_status = (
        "✅ Active"
        if vip
        else "❌ Inactive"
    )

    keyboard = [

        [
            InlineKeyboardButton(
                "💰 Balance",
                callback_data="balance",
            )
        ],

        [
            InlineKeyboardButton(
                "👥 Referral",
                callback_data="refer",
            )
        ],

        [
            InlineKeyboardButton(
                "🏆 Rank",
                callback_data="rank",
            )
        ],

        [
            InlineKeyboardButton(
                "📊 Statistics",
                callback_data="user_stats",
            )
        ],

        [
            InlineKeyboardButton(
                "📜 Activity",
                callback_data="user_activity",
            )
        ],

        [
            InlineKeyboardButton(
                "🏠 Home",
                callback_data="home",
            )
        ],

    ]

    await _safe_edit_message_text(query, 

        "👤 **YOUR PROFILE**\n\n"

        f"🆔 ID: `{user_id}`\n\n"

        f"💰 Balance: "
        f"{balance} Points\n"

        f"🎁 Bonus: "
        f"{bonus} Points\n"

        f"💎 Premium Balance: "
        f"{premium_balance} Points\n\n"

        f"👥 Referrals: "
        f"{referrals}\n"

        f"⭐ XP: "
        f"{xp}\n"

        f"🏆 Level: "
        f"{level}\n"

        f"🎖 Rank: "
        f"{rank}\n\n"

        f"👑 Premium: "
        f"{premium_status}\n"

        f"💎 VIP: "
        f"{vip_status}",

        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),

        parse_mode="Markdown",
    )


# ============================================================
# REFERRAL
# ============================================================

async def show_referral(
    query,
    context,
    user_id,
):

    user = get_user(user_id)

    if not user:

        await _safe_edit_message_text(query, 
            "⚠️ User account not found.",
            reply_markup=home_keyboard(),
        )

        return

    referrals = user.get(
        "referrals",
        0,
    )

    referral_earn = user.get(
        "referral_earn",
        0,
    )

    referral_xp = user.get(
        "referral_xp",
        0,
    )

    try:

        bot_info = await context.bot.get_me()

        bot_username = bot_info.username

    except Exception as error:

        logger.exception(
            "Could not get bot info: %s",
            error,
        )

        await _safe_edit_message_text(query, 
            "⚠️ Unable to generate referral link.",
            reply_markup=home_keyboard(),
        )

        return

    referral_link = (
        f"https://t.me/{bot_username}"
        f"?start=ref_{user_id}"
    )

    share_url = (
        "https://t.me/share/url"
        f"?url={referral_link}"
        "&text=Join%20Unlimited%20Energy%20Bot%20and%20earn%20rewards!"
    )

    keyboard = [

        [
            InlineKeyboardButton(
                "📤 Share Referral Link",
                url=share_url,
            )
        ],

        [
            InlineKeyboardButton(
                "👤 Profile",
                callback_data="profile",
            )
        ],

        [
            InlineKeyboardButton(
                "🏠 Home",
                callback_data="home",
            )
        ],

    ]

    await _safe_edit_message_text(query, 

        "👥 **REFERRAL CENTER**\n\n"

        "🎁 Invite friends and earn rewards!\n\n"

        f"👥 Valid Referrals: "
        f"{referrals}\n"

        f"⏳ Pending Referrals: "
        f"{int(user.get("pending_referrals", 0) or 0)}\n"

        f"💰 Referral Earnings: "
        f"{referral_earn} Points\n"

        f"⭐ Referral XP: "
        f"{referral_xp}\n\n"

        "🔗 **Your Referral Link:**\n"

        f"`{referral_link}`\n\n"

        "🏆 **REFERRAL MILESTONES**\n\n"
        + ("\n".join(
            f"• {count} referrals → +{reward} Points"
            for count, reward in get_milestones().items()
        ) or "No milestones configured.")
        + "\n\n"
        + (
            f"🎯 Next Milestone: {next_ms[0]} referrals → +{next_ms[1]} Points"
            if (next_ms := next(((count, reward) for count, reward in get_milestones().items() if count > int(referrals or 0)), None))
            else "🎯 All configured milestones reached!"
        )
        + "\n\n"
        + "📢 Share your link with your friends.\n"
        + "🎁 Referral rewards are released after qualifying activity.",

        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),

        parse_mode="Markdown",
    )


# ============================================================
# RANK
# ============================================================

async def show_rank(
    query,
    user_id,
):

    user = get_user(user_id)

    if not user:

        await _safe_edit_message_text(query, 
            "⚠️ User account not found.",
            reply_markup=home_keyboard(),
        )

        return

    rank = user.get(
        "rank",
        "🔰 Beginner",
    )

    level = user.get(
        "level",
        1,
    )

    xp = user.get(
        "xp",
        0,
    )

    await _safe_edit_message_text(query, 

        "🏆 **YOUR RANK**\n\n"

        f"🎖 Rank: "
        f"{rank}\n"

        f"🏆 Level: "
        f"{level}\n"

        f"⭐ XP: "
        f"{xp}\n\n"

        "🚀 Keep earning to reach "
        "the next rank!",

        reply_markup=InlineKeyboardMarkup(

            [

                [
                    InlineKeyboardButton(
                        "👤 Profile",
                        callback_data="profile",
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
# USER STATISTICS
# ============================================================

async def show_user_stats(
    query,
    user_id,
):

    user = get_user(user_id)

    if not user:

        await _safe_edit_message_text(query, 
            "⚠️ User account not found.",
            reply_markup=home_keyboard(),
        )

        return

    total_earned = user.get(
        "total_earned",
        0,
    )

    total_withdraw = user.get(
        "total_withdraw",
        0,
    )

    referrals = user.get(
        "referrals",
        0,
    )

    referral_earn = user.get(
        "referral_earn",
        0,
    )

    xp = user.get(
        "xp",
        0,
    )

    level = user.get(
        "level",
        1,
    )

    daily_streak = user.get(
        "daily_streak",
        0,
    )

    wheel_data = user.get(
        "wheel_data",
        {},
    )

    lucky_box_data = user.get(
        "lucky_box_data",
        {},
    )

    task_data = user.get(
        "task_data",
        {},
    )

    if not isinstance(
        wheel_data,
        dict,
    ):
        wheel_data = {}

    if not isinstance(
        lucky_box_data,
        dict,
    ):
        lucky_box_data = {}

    if not isinstance(
        task_data,
        dict,
    ):
        task_data = {}

    wheel_spins = wheel_data.get(
        "spins",
        0,
    )

    lucky_boxes = lucky_box_data.get(
        "opened",
        0,
    )

    tasks_completed = task_data.get(
        "completed",
        0,
    )

    await _safe_edit_message_text(query, 

        "📊 **YOUR STATISTICS**\n\n"

        f"💰 Total Earned: "
        f"{total_earned} Points\n"

        f"💸 Total Withdrawn: "
        f"{total_withdraw} Points\n"

        f"👥 Referrals: "
        f"{referrals}\n"

        f"🎁 Referral Earnings: "
        f"{referral_earn} Points\n\n"

        f"🎯 Tasks Completed: "
        f"{tasks_completed}\n"

        f"🎡 Wheel Spins: "
        f"{wheel_spins}\n"

        f"🎁 Lucky Boxes: "
        f"{lucky_boxes}\n\n"

        f"🔥 Daily Streak: "
        f"{daily_streak}\n"

        f"⭐ XP: "
        f"{xp}\n"

        f"🏆 Level: "
        f"{level}",

        reply_markup=back_profile_keyboard(),

        parse_mode="Markdown",
    )


# ============================================================
# USER ACTIVITY
# ============================================================

async def show_user_activity(
    query,
    user_id,
):

    user = get_user(user_id)

    if not user:

        await _safe_edit_message_text(query, 
            "⚠️ User account not found.",
            reply_markup=home_keyboard(),
        )

        return

    activities = user.get(
        "activity",
        [],
    )

    if not isinstance(
        activities,
        list,
    ):
        activities = []

    activities = activities[-10:]

    if not activities:

        await _safe_edit_message_text(query, 

            "📜 **RECENT ACTIVITY**\n\n"
            "No activity recorded yet.",

            reply_markup=back_profile_keyboard(),

            parse_mode="Markdown",
        )

        return

    text = (
        "📜 **RECENT ACTIVITY**\n\n"
    )

    for item in reversed(
        activities
    ):

        if not isinstance(
            item,
            dict,
        ):
            continue

        action = item.get(
            "action",
            "Unknown action",
        )

        timestamp = item.get(
            "time",
            "",
        )

        text += (
            f"• {action}\n"
            f"  🕒 {timestamp}\n\n"
        )

    await _safe_edit_message_text(query, 

        text,

        reply_markup=back_profile_keyboard(),

        parse_mode="Markdown",
    )


# ============================================================
# HELP
# ============================================================

async def show_help(
    query,
):

    await _safe_edit_message_text(query, 

        "❓ **HELP CENTER**\n\n"

        "💰 Earn — Complete available tasks\n"
        "💳 Balance — Check your wallet\n"
        "👤 Profile — View your account\n"
        "👥 Referral — Invite friends\n"
        "🏆 Rank — Check your progress\n"
        "🎁 Daily — Claim daily reward\n"
        "🎡 Games — Spin, Lucky Box & Scratch\n"
        "💸 Withdraw — Request withdrawal\n"
        "👑 Premium — Premium features\n"
        "💎 VIP — VIP features\n"
        "📊 Statistics — View your progress\n"
        "📜 Activity — View recent activity\n\n"

        "🆘 Need help?\n"
        "Contact the Admin: @mdrifatowner05",

        reply_markup=home_keyboard(),

        parse_mode="Markdown",
    )


# ============================================================
# FORCE JOIN VERIFICATION
# ============================================================

async def verify_join_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    if not query:
        return

    user_id = query.from_user.id

    user = get_user(user_id)

    if not user:

        await query.answer(
            "⚠️ User account not found.",
            show_alert=True,
        )

        return

    if user.get(
        "banned",
        False,
    ):

        await query.answer(
            "🚫 Your account has been banned.",
            show_alert=True,
        )

        return

    not_joined = []

    for group in GROUPS:

        try:

            member = await context.bot.get_chat_member(
                group,
                user_id,
            )

            if member.status in (
                "left",
                "kicked",
            ):

                not_joined.append(
                    group
                )

        except Exception as error:

            logger.warning(
                "Force join check failed | "
                "group=%s | user=%s | error=%s",
                group,
                user_id,
                error,
            )

            not_joined.append(
                group
            )

    if not_joined:

        await query.answer(
            "❌ Join all required groups first.",
            show_alert=True,
        )

        await _safe_edit_message_text(query, 

            "❌ **JOIN NOT COMPLETED**\n\n"

            "You still haven't joined all "
            "required groups.\n\n"

            "Join all groups and press "
            "✅ Verify Join again.",

            reply_markup=force_join_menu(),

            parse_mode="Markdown",
        )

        return

    await query.answer(
        "✅ Verification successful!"
    )

    await _safe_edit_message_text(query, 

        "✅ **VERIFICATION SUCCESSFUL!**\n\n"

        "🎉 You can now use "
        "Unlimited Energy Bot.",

        reply_markup=main_menu(),

        parse_mode="Markdown",
    )


# ============================================================
# OPTIONAL FEATURE ROUTER
# ============================================================

async def optional_feature_callback(
    update,
    context,
    module_name,
    function_name,
    unavailable_text,
):

    query = update.callback_query

    try:

        module = __import__(
            module_name
        )

        function = getattr(
            module,
            function_name,
        )

        await function(
            update,
            context,
        )

    except ImportError:

        logger.warning(
            "Optional module unavailable: %s",
            module_name,
        )

        await query.answer(
            unavailable_text,
            show_alert=True,
        )

    except AttributeError:

        logger.exception(
            "Function %s missing in %s",
            function_name,
            module_name,
        )

        await query.answer(
            "⚠️ This feature is not configured yet.",
            show_alert=True,
        )

    except Exception:

        logger.exception(
            "Optional feature error: %s.%s",
            module_name,
            function_name,
        )

        await query.answer(
            "⚠️ Unable to open this feature.",
            show_alert=True,
        )
async def earn_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data: str,
):
    earn_handlers = {
        "earn": earn_page,
        "daily_bonus": daily_bonus,
        "tasks": task_menu_page,
        "shortlinks": shortlinks_page,
        "spin": spin_wheel,
        "spin_wheel": spin_wheel,
        "lucky_box": lucky_box,
        "scratch": scratch_card,
        "energy": energy_page,
        "claim_test_task": claim_test_task,
    }

    handler = earn_handlers.get(data)

    if handler is None:
        return False

    await handler(
        update,
        context,
    )

    return True
# ============================================================
# MAIN CALLBACK ROUTER
# ============================================================

async def button_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query:
        return

    user = query.from_user

    if not user:
        return

    user_id = user.id
    raw_data = query.data

    # --------------------------------------------------------
    # INVALID CALLBACK PROTECTION
    # --------------------------------------------------------

    if raw_data is None:
        try:
            await query.answer(
                "⚠️ Invalid button.",
                show_alert=True,
            )
        except Exception:
            pass
        return

    data = str(raw_data).strip()

    if not data or len(data) > 64:
        try:
            await query.answer(
                "⚠️ Invalid button.",
                show_alert=True,
            )
        except Exception:
            pass
        return

    logger.info(
        "CALLBACK | user=%s | data=%s",
        user_id,
        data,
    )


    # --------------------------------------------------------
    # ANSWER CALLBACK
    # --------------------------------------------------------

    try:
        await query.answer()
    except Exception:
        pass

    # --------------------------------------------------------
    # USER CHECK
    # --------------------------------------------------------

    user_data = get_user(user_id)

    if not user_data:
        await _safe_edit_message_text(query, 
            "⚠️ User account not found.\n\n"
            "Please use /start first.",
            reply_markup=home_keyboard(),
        )
        return

    # --------------------------------------------------------
    # BAN
    # --------------------------------------------------------

    if user_data.get("banned", False):
        await _safe_edit_message_text(query, 
            "🚫 Your account has been banned.",
            reply_markup=home_keyboard(),
        )
        return

    # --------------------------------------------------------
    # BLACKLIST
    # --------------------------------------------------------

    if user_data.get("blacklisted", False):
        await _safe_edit_message_text(query, 
            "🚫 Your account is restricted.",
            reply_markup=home_keyboard(),
        )
        return

    # ========================================================
    # HOME
    # ========================================================

    if data == "home":
        try:
            await _safe_edit_message_text(query, 
                "🏠 **MAIN MENU**\n\n"
                "🚀 Unlimited Energy Bot\n\n"
                "👇 Choose an option:",
                reply_markup=main_menu(),
                parse_mode="Markdown",
            )
        except Exception:
            logger.exception(
                "Home callback failed"
            )

        return

    # ========================================================
    # EARN
    # ========================================================

    if data in (
        "earn",
        "daily_bonus",
        "tasks",
        "shortlinks",
        "spin",
        "spin_wheel",
        "lucky_box",
        "scratch",
        "energy",
        "claim_test_task",
    ):
        try:
            handled = await earn_callback(
                update,
                context,
                data,
            )

            if handled:
                return

        except Exception:
            logger.exception(
                "Earn callback failed | data=%s",
                data,
            )

            try:
                await _safe_edit_message_text(query, 
                    "⚠️ Earn feature temporarily unavailable.",
                    reply_markup=back_earn_keyboard(),
                )
            except Exception:
                pass

            return

    # ========================================================
    # BALANCE
    # ========================================================

    if data == "bonus_convert":
        amount = convert_bonus_to_balance(query.from_user.id)
        if amount:
            await query.answer(f"✅ {amount} bonus points converted.", show_alert=True)
        else:
            await query.answer("❌ No convertible bonus balance.", show_alert=True)
        await show_balance(query, query.from_user.id)
        return

    if data == "balance":
        await show_balance(
            query,
            user_id,
        )
        return

    # ========================================================
    # PROFILE
    # ========================================================

    if data == "profile":
        await show_profile(
            query,
            user_id,
        )
        return

    # ========================================================
    # REFERRAL
    # ========================================================

    if data in (
        "refer",
        "referral",
    ):
        await show_referral(
            query,
            context,
            user_id,
        )
        return

    if data == "referral_link":
        await referral_link_callback(update, context)
        return

    if data == "referral_stats":
        await referral_stats_callback(update, context)
        return

    # ========================================================
    # RANK
    # ========================================================

    if data == "rank":
        await show_rank(
            query,
            user_id,
        )
        return

    # ========================================================
    # STATISTICS
    # ========================================================

    if data in (
        "user_stats",
        "stats",
    ):
        await show_user_stats(
            query,
            user_id,
        )
        return

    # ========================================================
    # ACTIVITY
    # ========================================================

    if data in (
        "user_activity",
        "activity",
    ):
        await show_user_activity(
            query,
            user_id,
        )
        return

    # ========================================================
    # OFFERS
    # ========================================================

    if data == "offers":
        await offers_page(update, context)
        return

    if data.startswith("provider_offer_"):
        await provider_offer_callback(update, context)
        return

    if data.startswith("offer_claim_"):
        await offer_claim_callback(update, context)
        return

    if data.startswith("offer_"):
        await offer_callback(update, context)
        return

    # ========================================================
    # WITHDRAW
    # ========================================================

    if data == "withdraw":
        await withdraw_page(
            update,
            context,
        )
        return

    if data.startswith(
        "withdraw_method_"
    ):
        await select_method(
            update,
            context,
        )
        return

    if data == "withdraw_confirm":
        await confirm_withdrawal(
            update,
            context,
        )
        return

    if data == "withdraw_cancel":
        await cancel_withdrawal(
            update,
            context,
        )
        return

    if data == "withdraw_history":
        await withdrawal_history_page(
            update,
            context,
        )
        return

    # ========================================================
    # SHORTLINK ACTIONS
    # ========================================================

    if data.startswith("shortlink_verify_"):
        try:
            await shortlink_verify_callback(update, context)
        except Exception:
            logger.exception("Shortlink verification callback failed")
            await _safe_edit_message_text(query, 
                "⚠️ Shortlink verification failed.",
                reply_markup=back_earn_keyboard(),
            )
        return

    if data.startswith("shortlink_"):
        try:
            await shortlink_callback(update, context)
        except Exception:
            logger.exception("Shortlink callback failed")
            await _safe_edit_message_text(query, 
                "⚠️ Shortlink is temporarily unavailable.",
                reply_markup=back_earn_keyboard(),
            )
        return

    # ========================================================
    # TASKS
    # ========================================================
    if data == "tasks":
        await task_menu_page(update, context)
        return
    if data.startswith("task_complete_"):
        await task_complete_callback(update, context)
        return
    if data.startswith("task_"):
        await task_callback(update, context)
        return

    # ========================================================
    # PREMIUM
    # ========================================================

    if data == "premium":
        try:
            await premium_page(
                update,
                context,
            )
        except Exception:
            logger.exception(
                "Premium page failed"
            )

            await _safe_edit_message_text(query, 
                "⚠️ Premium system is temporarily unavailable.",
                reply_markup=home_keyboard(),
            )

        return

    # --------------------------------------------------------
    # PREMIUM PURCHASE
    # --------------------------------------------------------

    if data == "premium_renew":
        await query.answer()
        await _safe_edit_message_text(query, "💳 **PREMIUM RENEWAL**\n\nChoose a payment method:", reply_markup=method_keyboard("premium"), parse_mode="Markdown")
        return

    if data == "premium_buy":
        await query.answer()
        await _safe_edit_message_text(query, "💳 **PREMIUM PAYMENT**\n\nChoose a payment method:", reply_markup=method_keyboard("premium"), parse_mode="Markdown")
        return

    if data.startswith("pay_method_"):
        await query.answer()
        try:
            _, rest = data.split("pay_method_",1); method, product = rest.split(":",1)
        except ValueError:
            await _safe_edit_message_text(query, "⚠️ Invalid payment option."); return
        if product == "premium": price = PREMIUM_CASH_PRICE
        elif product.startswith("vip:"):
            prices={1:VIP1_CASH_PRICE,2:VIP2_CASH_PRICE,3:VIP3_CASH_PRICE,4:VIP4_CASH_PRICE,5:VIP5_CASH_PRICE}
            try: price=prices[int(product.split(":",1)[1])]
            except Exception: await _safe_edit_message_text(query, "⚠️ Invalid VIP level."); return
        else: await _safe_edit_message_text(query, "⚠️ Invalid product."); return
        pay=create_payment(query.from_user.id,product,price,method)
        await _safe_edit_message_text(query, payment_instructions(method,product,price), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🧾 Submit Transaction ID",callback_data=f"pay_submit:{pay['payment_id']}")],[InlineKeyboardButton("🏠 Home",callback_data="home")]]), parse_mode="Markdown")
        return

    if data.startswith("pay_submit:"):
        await query.answer()
        pid=data.split(":",1)[1]; pay=get_payment(pid)
        if not pay or int(pay.get("user_id",0))!=query.from_user.id or pay.get("status")!="pending":
            await _safe_edit_message_text(query, "⚠️ Payment request is invalid or already processed.", reply_markup=home_keyboard()); return
        context.user_data["payment_reference_id"]=pid; context.user_data["admin_action"]="payment_reference"
        await _safe_edit_message_text(query, "🧾 Send your payment **Transaction ID / reference** now.", reply_markup=home_keyboard(), parse_mode="Markdown")
        return

    if data == "premium_buy":
        try:
            await premium_buy(
                update,
                context,
            )
        except Exception:
            logger.exception(
                "Premium purchase failed"
            )

            await _safe_edit_message_text(query, 
                "⚠️ Premium purchase failed.",
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
            )

        return

    # --------------------------------------------------------
    # PREMIUM RENEW
    # --------------------------------------------------------

    if data == "premium_renew":
        try:
            await premium_renew(
                update,
                context,
            )
        except Exception:
            logger.exception(
                "Premium renewal failed"
            )

            await _safe_edit_message_text(query, 
                "⚠️ Premium renewal failed.",
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
            )

        return

    # ========================================================
    # VIP MENU
    # ========================================================

    if data == "vip":
        try:
            await vip_page(
                update,
                context,
            )
        except Exception:
            logger.exception(
                "VIP page failed"
            )

            await _safe_edit_message_text(query, 
                "⚠️ VIP system is temporarily unavailable.",
                reply_markup=home_keyboard(),
            )

        return
# ========================================================
# VIP PURCHASE CONFIRM
# ========================================================

    if data.startswith("vip_confirm_"):
        if not is_vip_purchase_enabled():
            await _safe_edit_message_text(query, 
                "🔴 **VIP PURCHASE OFF**\n\n"
                "VIP purchases are temporarily disabled by Admin.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💎 VIP", callback_data="vip")],
                    [InlineKeyboardButton("🏠 Home", callback_data="home")],
                ]),
                parse_mode="Markdown",
            )
            return

        try:
            await vip_confirm_purchase_callback(
                update,
                context,
            )
        except Exception:
            logger.exception(
                "VIP confirmation failed"
            )

            await _safe_edit_message_text(query, 
                "⚠️ VIP purchase failed.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "💎 VIP",
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
                ),
            )

        return
# --------------------------------------------------------
# VIP ADMIN TOGGLE
# --------------------------------------------------------
    if data == "admin_vip_toggle":
        try:
            from admin import admin_callback

            await admin_callback(
                update,
                context,
            )

        except Exception:
            logger.exception(
                "Admin VIP toggle callback failed"
            )

            try:
                await query.answer(
                    "⚠️ VIP setting failed.",
                    show_alert=True,
                )
            except Exception:
                pass

        return


# --------------------------------------------------------
# ADMIN CALLBACKS
# --------------------------------------------------------
    if data == "admin" or data.startswith("admin_"):
        try:
            from admin import admin_callback

            await admin_callback(
                update,
                context,
            )

        except ImportError:
            logger.exception(
                "admin_callback unavailable"
            )

            try:
                await query.answer(
                    "⚠️ Admin system unavailable.",
                    show_alert=True,
                )
            except Exception:
                pass

        except Exception:
            logger.exception(
                "Admin callback error"
            )

            try:
                await query.answer(
                    "⚠️ Admin action failed.",
                    show_alert=True,
                )
            except Exception:
                pass

        return
    # ========================================================
    # VIP PAID PURCHASE
    # ========================================================

    if data.startswith("vip_level_"):
        try: level=int(data.rsplit("_",1)[1])
        except Exception: await _safe_edit_message_text(query, "⚠️ Invalid VIP level."); return
        prices={1:VIP1_CASH_PRICE,2:VIP2_CASH_PRICE,3:VIP3_CASH_PRICE,4:VIP4_CASH_PRICE,5:VIP5_CASH_PRICE}
        if level not in prices: await _safe_edit_message_text(query, "⚠️ Invalid VIP level."); return
        await query.answer(); product=f"vip:{level}"; price=prices[level]
        await _safe_edit_message_text(query, f"💎 **VIP {level} PAYMENT**\n\n💰 Price: **৳{price:g}**\n⏳ Duration: **30 days**\n\nChoose a payment method:", reply_markup=method_keyboard(product), parse_mode="Markdown")
        return

    if data.startswith("vip_level_"):

        # Admin-controlled VIP purchase switch
        if not is_vip_purchase_enabled():

            await _safe_edit_message_text(query, 
                "🔴 **VIP PURCHASE OFF**\n\n"
                "VIP purchases are temporarily disabled "
                "by Admin.\n\n"
                "Please try again later.",
                reply_markup=InlineKeyboardMarkup(
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
                ),
                parse_mode="Markdown",
            )
            return

        try:
            await vip_purchase_callback(
                update,
                context,
            )

        except Exception:
            logger.exception(
                "VIP purchase callback failed"
            )

            await _safe_edit_message_text(query, 
                "⚠️ VIP purchase failed.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "💎 VIP",
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
               ),
        )

        return


    # ========================================================
    # HELP
    # ========================================================

    if data == "help":
        await show_help(
            query,
        )
        return

    # ========================================================
    # FORCE JOIN
    # ========================================================

    if data in (
        "verify_join",
        "verify",
        "check_join",
    ):
        await verify_join_callback(
            update,
            context,
        )
        return

    # ========================================================
    # UNKNOWN CALLBACK
    # ========================================================

    logger.warning(
        "UNKNOWN CALLBACK | user=%s | data=%s",
        user_id,
        data,
    )

    await _safe_edit_message_text(query, 
        "⚠️ This button is not available.",
        reply_markup=home_keyboard(),
    )


# ============================================================
# EXPORTS
# ============================================================

CALLBACK_FUNCTIONS = {
    "button_callback": button_callback,
    "verify_join_callback": verify_join_callback,
    "show_balance": show_balance,
    "show_profile": show_profile,
    "show_referral": show_referral,
    "show_rank": show_rank,
    "show_user_stats": show_user_stats,
    "show_user_activity": show_user_activity,
    "vip_purchase_callback": vip_purchase_callback,
    "earn_callback": earn_callback,
}
