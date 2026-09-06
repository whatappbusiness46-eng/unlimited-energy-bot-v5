# ============================================================
# handlers.py
# Unlimited Energy Bot V2
# FINAL USER HANDLERS
# ============================================================

import time
import logging

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import ContextTypes

from config import ADMIN_USERNAME

from database import (
    create_user,
    get_user,
    update_user,
    leaderboard,
    add_activity as db_add_activity,
)

from config import (
    GROUPS,
    DAILY_BONUS,
    DAILY_XP,
    REFERRAL_REWARD,
    REFERRAL_XP,
    GROUP_JOIN_REWARD,
    XP_PER_LEVEL,
    BRONZE_REQUIRED,
    SILVER_REQUIRED,
    GOLD_REQUIRED,
    DIAMOND_REQUIRED,
    MAX_ENERGY,
    ACTIVITY_LIMIT,
)


logger = logging.getLogger(__name__)


# ============================================================
# HELPERS
# ============================================================

def calculate_level(xp):
    return max(
        (int(xp) // XP_PER_LEVEL) + 1,
        1,
    )


def calculate_rank(balance):
    balance = int(balance or 0)

    if balance >= DIAMOND_REQUIRED:
        return "💎 Diamond"

    if balance >= GOLD_REQUIRED:
        return "🥇 Gold"

    if balance >= SILVER_REQUIRED:
        return "🥈 Silver"

    if balance >= BRONZE_REQUIRED:
        return "🥉 Bronze"

    return "🔰 Beginner"


def add_activity(user_id, action, amount=0):
    """Compatibility wrapper around database.add_activity."""
    try:
        return db_add_activity(user_id, action, amount)
    except Exception:
        logger.exception(
            "Failed to record activity | user=%s | action=%s",
            user_id,
            action,
        )
        return None

# ============================================================
# MAIN MENU
# ============================================================

def main_menu():

    keyboard = [
        [
            InlineKeyboardButton(
                "💰 Earn",
                callback_data="earn",
            )
        ],
        [
            InlineKeyboardButton(
                "💳 Balance",
                callback_data="balance",
            ),
            InlineKeyboardButton(
                "👤 Profile",
                callback_data="profile",
            ),
        ],
        [
            InlineKeyboardButton(
                "👥 Referral",
                callback_data="refer",
            ),
            InlineKeyboardButton(
                "🏆 Rank",
                callback_data="rank",
            ),
        ],
        [
            InlineKeyboardButton(
                "💸 Withdraw",
                callback_data="withdraw",
            )
        ],
        [
            InlineKeyboardButton(
                "👑 Premium",
                callback_data="premium",
            ),
        ],
        [
            InlineKeyboardButton(
                "💎 VIP",
                callback_data="vip",
            ),
        ],
        [
            InlineKeyboardButton(
                "📊 Statistics",
                callback_data="user_stats",
            ),
            InlineKeyboardButton(
                "📜 Activity",
                callback_data="user_activity",
            ),
        ],
        [
            InlineKeyboardButton(
                "❓ Help",
                callback_data="help",
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# ============================================================
# FORCE JOIN MENU
# ============================================================

def force_join_menu():

    keyboard = []

    for index, group in enumerate(
        GROUPS,
        start=1,
    ):

        keyboard.append(
            [
                InlineKeyboardButton(
                    f"📢 Join Group {index}",
                    url=(
                        "https://t.me/"
                        f"{str(group).replace('@', '')}"
                    ),
                )
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                "✅ Verify Join",
                callback_data="verify_join",
            )
        ]
    )

    return InlineKeyboardMarkup(keyboard)


# ============================================================
# FORCE JOIN CHECK
# ============================================================

async def check_force_join(
    user_id,
    context,
):

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
                not_joined.append(group)

        except Exception as error:

            logger.warning(
                "Force join check failed | "
                "group=%s | user=%s | error=%s",
                group,
                user_id,
                error,
            )

            not_joined.append(group)

    return not_joined


# ============================================================
# START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    telegram_user = update.effective_user

    if not telegram_user:
        return

    user_id = telegram_user.id

    create_user(user_id)

    user = get_user(user_id)

    if not user:
        await update.message.reply_text(
            "⚠️ Unable to create your account. "
            "Please try again."
        )
        return

    # --------------------------------------------------------
    # BAN CHECK
    # --------------------------------------------------------

    if user.get("banned", False):

        await update.message.reply_text(
            "🚫 Your account has been banned."
        )

        return

    # --------------------------------------------------------
    # Update Telegram profile information
    # --------------------------------------------------------

    update_user(
        user_id,
        {
            "username": telegram_user.username,
            "first_name": telegram_user.first_name,
            "last_name": telegram_user.last_name,
            "last_login": int(time.time()),
            "last_active": int(time.time()),
        },
    )

    # --------------------------------------------------------
    # Referral
    # --------------------------------------------------------

    referral_id = None
    if context.args:
        referral_arg = str(context.args[0]).strip()
        if referral_arg.startswith("ref_"):
            try:
                referral_id = int(referral_arg[4:])
            except ValueError:
                referral_id = None

    if referral_id and referral_id != user_id:
        try:
            from referral import process_referral
            process_referral(user_id, referral_id)
        except Exception:
            logger.exception("Referral attribution failed")

    # --------------------------------------------------------
    # Force Join
    # --------------------------------------------------------

    not_joined = await check_force_join(
        user_id,
        context,
    )

    if not_joined:

        await update.message.reply_text(

            "🔒 **JOIN REQUIRED**\n\n"
            "Before using Unlimited Energy Bot, "
            "please join all of our official groups.\n\n"
            "After joining all groups, press "
            "✅ Verify Join.",

            reply_markup=force_join_menu(),

            parse_mode="Markdown",
        )

        return

    # --------------------------------------------------------
    # Home
    # --------------------------------------------------------

    await update.message.reply_text(

        f"👋 Welcome {telegram_user.first_name}!\n\n"

        "🚀 **Unlimited Energy Bot V2**\n\n"

        "💰 Earn Points\n"
        "🎁 Complete Tasks\n"
        "👥 Invite Friends\n"
        "🎡 Play Reward Games\n"
        "👑 Premium & VIP\n"
        "💸 Withdraw Rewards\n\n"

        "👇 Choose an option below.",

        reply_markup=main_menu(),

        parse_mode="Markdown",
    )

    add_activity(
        user_id,
        "Opened bot",
    )


# ============================================================
# PROFILE
# ============================================================

async def profile(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    telegram_user = update.effective_user

    if not telegram_user:
        return

    user_id = telegram_user.id

    user = get_user(user_id)

    if not user:

        await update.message.reply_text(
            "⚠️ User account not found."
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

    level = calculate_level(xp)

    rank = calculate_rank(balance)

    premium = user.get(
        "premium",
        False,
    )

    vip = user.get(
        "vip",
        False,
    )

    update_user(
        user_id,
        {
            "level": level,
            "rank": rank,
        },
    )

    await update.message.reply_text(

        "👤 **YOUR PROFILE**\n\n"

        f"🆔 ID: `{user_id}`\n\n"

        f"💰 Balance: {balance} Points\n"
        f"🎁 Bonus: {bonus} Points\n"
        f"💎 Premium Balance: "
        f"{premium_balance} Points\n\n"

        f"👥 Referrals: {referrals}\n"
        f"⭐ XP: {xp}\n"
        f"🏆 Level: {level}\n"
        f"🎖 Rank: {rank}\n\n"

        f"👑 Premium: "
        f"{'✅ Active' if premium else '❌ Inactive'}\n"

        f"💎 VIP: "
        f"{'✅ Active' if vip else '❌ Inactive'}",

        parse_mode="Markdown",
    )


# ============================================================
# BALANCE
# ============================================================

async def balance(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    telegram_user = update.effective_user

    if not telegram_user:
        return

    user_id = telegram_user.id

    user = get_user(user_id)

    if not user:

        await update.message.reply_text(
            "⚠️ User account not found."
        )

        return

    earn_balance = user.get(
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
        earn_balance
        + bonus
        + premium_balance
    )

    await update.message.reply_text(

        "💰 **YOUR WALLET**\n\n"

        f"💰 Earn Balance: "
        f"{earn_balance} Points\n"

        f"🎁 Bonus Balance: "
        f"{bonus} Points\n"

        f"💎 Premium Balance: "
        f"{premium_balance} Points\n\n"

        f"💵 **Total Balance: "
        f"{total} Points**",

        parse_mode="Markdown",
    )


# ============================================================
# RANK
# ============================================================

async def rank(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    telegram_user = update.effective_user

    if not telegram_user:
        return

    user_id = telegram_user.id

    user = get_user(user_id)

    if not user:

        await update.message.reply_text(
            "⚠️ User account not found."
        )

        return

    balance_value = user.get(
        "balance",
        0,
    )

    xp = user.get(
        "xp",
        0,
    )

    level = calculate_level(xp)

    user_rank = calculate_rank(
        balance_value
    )

    update_user(
        user_id,
        {
            "rank": user_rank,
            "level": level,
        },
    )

    await update.message.reply_text(

        "🏆 **YOUR RANK**\n\n"

        f"💰 Balance: "
        f"{balance_value} Points\n"

        f"🎖 Rank: {user_rank}\n"
        f"🏆 Level: {level}\n"
        f"⭐ XP: {xp}\n\n"

        "🚀 Keep earning to reach "
        "the next rank!",

        parse_mode="Markdown",
    )


# ============================================================
# HELP
# ============================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(

        "❓ **HELP CENTER**\n\n"

        "💰 Earn — Complete available tasks\n"
        "💳 Balance — Check your wallet\n"
        "👤 Profile — View your account\n"
        "👥 Referral — Invite friends\n"
        "🏆 Rank — Check your progress\n"
        "🎁 Daily — Claim daily reward\n"
        "🎡 Games — Spin, Scratch & Lucky Box\n"
        "💸 Withdraw — Request withdrawal\n"
        "👑 Premium — Premium features\n"
        "💎 VIP — VIP features\n"
        "📊 Statistics — View your statistics\n"
        "📜 Activity — View recent activity\n\n"

        "🆘 Need help?\n"
        f"Contact the Admin: @mdrifatowner05",

        parse_mode="Markdown",
    )


# ============================================================
# USER STATISTICS
# ============================================================

async def stats(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    telegram_user = update.effective_user

    if not telegram_user:
        return

    user_id = telegram_user.id

    user = get_user(user_id)

    if not user:

        await update.message.reply_text(
            "⚠️ User account not found."
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

    offers = user.get(
        "offer_completed",
        0,
    )

    shortlinks = user.get(
        "shortlink_completed",
        0,
    )

    streak = user.get(
        "daily_streak",
        0,
    )

    spins = user.get(
        "wheel_data",
        {},
    )

    if isinstance(spins, dict):
        wheel_spins = spins.get(
            "spins",
            0,
        )
    else:
        wheel_spins = 0

    await update.message.reply_text(

        "📊 **YOUR STATISTICS**\n\n"

        f"💰 Total Earned: "
        f"{total_earned} Points\n"

        f"💸 Total Withdrawn: "
        f"{total_withdraw} Points\n"

        f"👥 Referrals: {referrals}\n"

        f"🎯 Offers Completed: "
        f"{offers}\n"

        f"🔗 Shortlinks Completed: "
        f"{shortlinks}\n"

        f"🎡 Wheel Spins: "
        f"{wheel_spins}\n"

        f"🔥 Daily Streak: "
        f"{streak} Days",

        parse_mode="Markdown",
    )


# ============================================================
# LEADERBOARD
# ============================================================

async def leaderboard_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    top_users = leaderboard()

    if not top_users:

        await update.message.reply_text(
            "🏆 Leaderboard is empty."
        )

        return

    text = (
        "🏆 **TOP 10 USERS**\n\n"
    )

    medals = [
        "🥇",
        "🥈",
        "🥉",
    ]

    for position, user in enumerate(
        top_users,
        start=1,
    ):

        user_id = user.get(
            "user_id",
            "Unknown",
        )

        balance_value = user.get(
            "balance",
            0,
        )

        if position <= 3:

            icon = medals[
                position - 1
            ]

        else:

            icon = f"{position}."

        text += (
            f"{icon} `{user_id}`\n"
            f"   💰 {balance_value} Points\n\n"
        )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
    )


# ============================================================
# ACTIVITY
# ============================================================

async def activity(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    telegram_user = update.effective_user

    if not telegram_user:
        return

    user_id = telegram_user.id

    user = get_user(user_id)

    if not user:

        await update.message.reply_text(
            "⚠️ User account not found."
        )

        return

    activities = user.get(
        "activity",
        [],
    )

    if not activities:

        await update.message.reply_text(
            "📜 **YOUR ACTIVITY**\n\n"
            "No activity recorded yet.",
            parse_mode="Markdown",
        )

        return

    text = (
        "📜 **YOUR RECENT ACTIVITY**\n\n"
    )

    for item in activities[
        -ACTIVITY_LIMIT:
    ]:

        action = item.get(
            "action",
            "Unknown Action",
        )

        activity_time = item.get(
            "time",
            "Unknown Time",
        )

        text += (
            f"• {action}\n"
            f"  🕒 {activity_time}\n\n"
        )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
    )
# ============================================================
# DAILY STATUS
# ============================================================

async def dailystatus(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    telegram_user = update.effective_user

    if not telegram_user:
        return

    user_id = telegram_user.id

    user = get_user(user_id)

    if not user:

        await update.message.reply_text(
            "⚠️ User account not found."
        )

        return

    last_daily = user.get(
        "last_daily",
        0,
    )

    if not last_daily:

        await update.message.reply_text(

            "🎁 **DAILY BONUS**\n\n"

            "✅ Your daily bonus is ready!\n\n"

            f"🎁 Reward: "
            f"{DAILY_BONUS} Points",

            parse_mode="Markdown",
        )

        return

    now = int(time.time())

    remaining = (
        86400
        - (now - int(last_daily))
    )

    if remaining <= 0:

        await update.message.reply_text(

            "🎁 **DAILY BONUS**\n\n"

            "✅ Your bonus is ready!\n\n"

            f"🎁 Reward: "
            f"{DAILY_BONUS} Points",

            parse_mode="Markdown",
        )

        return

    hours = remaining // 3600

    minutes = (
        remaining % 3600
    ) // 60

    await update.message.reply_text(

        "⏳ **DAILY BONUS**\n\n"

        "Your bonus has already been claimed.\n\n"

        "🕐 Try again after:\n"

        f"{hours} Hours "
        f"{minutes} Minutes",

        parse_mode="Markdown",
    )


# ============================================================
# MY ID
# ============================================================

async def myid(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    telegram_user = update.effective_user

    if not telegram_user:
        return

    user_id = telegram_user.id

    await update.message.reply_text(

        "🆔 **YOUR TELEGRAM ID**\n\n"
        f"`{user_id}`",

        parse_mode="Markdown",
    )


# ============================================================
# VERIFY JOIN
# ============================================================

async def verify_join(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    if not query:
        return

    await query.answer()

    user_id = query.from_user.id

    user = get_user(user_id)

    if not user:

        await query.edit_message_text(
            "⚠️ User account not found."
        )

        return

    if user.get(
        "banned",
        False,
    ):

        await query.edit_message_text(
            "🚫 Your account has been banned."
        )

        return

    not_joined = await check_force_join(
        user_id,
        context,
    )

    if not_joined:

        await query.edit_message_text(

            "❌ **JOIN NOT COMPLETED**\n\n"

            "You still haven't joined all "
            "required groups.\n\n"

            "Join all groups and press "
            "✅ Verify Join again.",

            reply_markup=force_join_menu(),

            parse_mode="Markdown",
        )

        return

    # --------------------------------------------------------
    # One-time group reward
    # --------------------------------------------------------

    group_reward_given = user.get(
        "group_reward",
        False,
    )

    reward_text = ""

    if not group_reward_given:

        current_balance = user.get(
            "balance",
            0,
        )

        current_xp = user.get(
            "xp",
            0,
        )

        new_balance = (
            current_balance
            + GROUP_JOIN_REWARD
        )

        new_xp = (
            current_xp
            + DAILY_XP
        )

        update_user(
            user_id,
            {
                "balance": new_balance,
                "total_earned": (
                    user.get(
                        "total_earned",
                        0,
                    )
                    + GROUP_JOIN_REWARD
                ),
                "xp": new_xp,
                "level": calculate_level(
                    new_xp
                ),
                "rank": calculate_rank(
                    new_balance
                ),
                "group_reward": True,
            },
        )

        add_activity(
            user_id,
            (
                "Group join reward "
                f"+{GROUP_JOIN_REWARD} Points"
            ),
        )

        reward_text = (
            "\n\n🎁 Group Reward: "
            f"+{GROUP_JOIN_REWARD} Points"
        )

    await query.edit_message_text(

        "✅ **VERIFICATION SUCCESSFUL!**\n\n"

        "🎉 You can now use "
        "Unlimited Energy Bot."

        f"{reward_text}",

        reply_markup=main_menu(),

        parse_mode="Markdown",
    )


# ============================================================
# EXPORTS
# ============================================================

HANDLER_FUNCTIONS = {

    "start":
        start,

    "profile":
        profile,

    "balance":
        balance,

    "rank":
        rank,

    "stats":
        stats,

    "leaderboard":
        leaderboard_command,

    "activity":
        activity,

    "dailystatus":
        dailystatus,

    "help":
        help_command,

    "myid":
        myid,

    "verify_join":
        verify_join,
        }
