# ============================================================
# earn.py
# Unlimited Energy Bot V2
# ============================================================

import random
import time
import logging

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import ContextTypes

from config import DAILY_BONUS

from database import (
    get_bot_settings,
    get_user,
    add_balance,
    add_bonus,
    update_daily_statistic,
    add_xp,
    add_activity,
    update_user,
    use_energy,
    update_energy,
    use_spin_ticket,
    use_lucky_box,
    use_scratch_card,
    get_membership_multiplier,
)


logger = logging.getLogger(__name__)

def _member_reward(user_id, reward):
    """Apply active Premium/VIP earning multiplier to point rewards."""
    try:
        mult = max(1.0, float(get_membership_multiplier(user_id)))
    except Exception:
        mult = 1.0
    return int(round(max(0, int(reward)) * mult))



# ============================================================
# SETTINGS
# ============================================================

SPIN_COOLDOWN = 60
LUCKY_BOX_COOLDOWN = 60
SCRATCH_COOLDOWN = 60

SPIN_COST_ENERGY = 1
LUCKY_BOX_COST_ENERGY = 1
SCRATCH_COST_ENERGY = 1

MAX_DAILY_TASKS = 20
DAY_7_SPECIAL_REWARD = 100


# ============================================================
# COMMON HELPERS
# ============================================================

def is_banned(user_id):
    user = get_user(
        user_id,
        create=False,
    )

    if not user:
        return True

    return (
        user.get("banned", False)
        or user.get("blacklisted", False)
    )


def back_menu():
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


def earn_menu():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🎁 Daily Bonus",
                    callback_data="daily_bonus",
                )
            ],
            [
                InlineKeyboardButton(
                    "📋 Tasks",
                    callback_data="tasks",
                ),
                InlineKeyboardButton(
                    "🔗 Shortlinks",
                    callback_data="shortlinks",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🎁 Earn Offers",
                    callback_data="offers",
                )
            ],
            [
                InlineKeyboardButton(
                    "🎡 Spin Wheel",
                    callback_data="spin",
                )
            ],
            [
                InlineKeyboardButton(
                    "🎁 Lucky Box",
                    callback_data="lucky_box",
                ),
                InlineKeyboardButton(
                    "🎫 Scratch Card",
                    callback_data="scratch",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⚡ Energy",
                    callback_data="energy",
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
# EARN PAGE
# ============================================================

async def earn_page(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user_id = query.from_user.id

    if is_banned(user_id):
        await query.edit_message_text(
            "🚫 Your account has been banned."
        )
        return

    await query.edit_message_text(
        "💰 **EARN CENTER**\n\n"
        "Choose a way to earn Points:\n\n"
        "🎁 Daily Bonus\n"
        "📋 Complete Tasks\n"
        "🔗 Complete Shortlinks\n"
        "🎁 Earn Offers\n"
        "🎡 Spin Wheel\n"
        "🎁 Lucky Box\n"
        "🎫 Scratch Card\n"
        "⚡ Energy System\n\n"
        "👇 Select an option below.",
        reply_markup=earn_menu(),
        parse_mode="Markdown",
    )


# Backward-compatible alias
earn = earn_page


# ============================================================
# DAILY BONUS
# ============================================================

async def daily_bonus(
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
            "⚠️ Account not found.",
            reply_markup=back_menu(),
        )
        return

    if user.get("banned", False):
        await query.edit_message_text(
            "🚫 Your account has been banned."
        )
        return

    now = int(time.time())

    last_daily = user.get(
        "last_daily",
        0,
    )

    # --------------------------------------------------------
    # 24 hour cooldown
    # --------------------------------------------------------

    if last_daily:
        elapsed = now - last_daily

        if elapsed < 86400:
            remaining = 86400 - elapsed

            hours = remaining // 3600
            minutes = (
                remaining % 3600
            ) // 60

            await query.edit_message_text(
                "⏳ **DAILY BONUS**\n\n"
                "You have already claimed "
                "today's bonus.\n\n"
                f"🕐 Try again in "
                f"{hours}h {minutes}m.",
                reply_markup=back_menu(),
                parse_mode="Markdown",
            )
            return

    # --------------------------------------------------------
    # Streak
    # --------------------------------------------------------

    streak = user.get(
        "daily_streak",
        0,
    )

    if last_daily:
        if now - last_daily <= 172800:
            streak += 1
        else:
            streak = 1
    else:
        streak = 1

    # --------------------------------------------------------
    # Streak reward
    # --------------------------------------------------------

    streak_bonus = min(
        max(streak - 1, 0),
        10,
    )

    settings = get_bot_settings() or {}
    daily_bonus = max(0, int(settings.get("daily_bonus", DAILY_BONUS) or DAILY_BONUS))
    reward = daily_bonus + streak_bonus

    day7_bonus = 0

    if streak == 7:
        day7_bonus = DAY_7_SPECIAL_REWARD
        reward += day7_bonus

    # --------------------------------------------------------
    # Give reward
    # --------------------------------------------------------

    reward = _member_reward(user_id, reward)
    add_bonus(
        user_id,
        reward,
    )

    update_daily_statistic(
        field="daily_rewards",
        amount=reward,
    )

    xp_result = add_xp(
        user_id,
        10,
    )

    update_user(
        user_id,
        {
            "last_daily": now,
            "daily_streak": streak,
        },
    )

    add_activity(
        user_id,
        "🎁 Daily Bonus",
        reward,
    )

    level_text = ""

    if xp_result.get("level_up"):
        level_text = (
            "\n🎉 **LEVEL UP!**\n"
            f"🏆 New Level: "
            f"{xp_result.get('level', 1)}\n"
        )

    day7_text = ""

    if day7_bonus:
        day7_text = (
            f"🎉 Day 7 Special: "
            f"+{day7_bonus} Points\n"
        )

    message = (
        "🎁 **DAILY BONUS CLAIMED!**\n\n"
        f"💰 Reward: +{reward} Points\n"
        f"{day7_text}"
        f"🔥 Daily Streak: {streak} Days\n"
        "⭐ XP: +10\n"
        f"{level_text}\n"
        "Come back tomorrow for another bonus! 🚀"
    )

    await query.edit_message_text(
        text=message,
        reply_markup=back_menu(),
        parse_mode="Markdown",
    )


# ============================================================
# TASKS
# ============================================================

async def tasks(
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
            "⚠️ Account not found.",
            reply_markup=back_menu(),
        )
        return

    if user.get("banned", False):
        await query.edit_message_text(
            "🚫 Your account has been banned."
        )
        return

    settings = get_bot_settings() or {}
    task_reward = max(0, int(settings.get("task_reward", 10) or 10))
    daily_task_limit = max(1, int(settings.get("daily_task_limit", MAX_DAILY_TASKS) or MAX_DAILY_TASKS))
    completed_today = user.get(
        "daily_task_count",
        0,
    )

    await query.edit_message_text(
        "📋 **TASK CENTER**\n\n"
        "🧪 **Test Task**\n"
        f"💰 Reward: {task_reward} Points\n"
        "⭐ XP: 5\n"
        "⚡ Energy: 1\n\n"
        f"📊 Daily Tasks: "
        f"{completed_today}/{daily_task_limit}\n\n"
        "Complete the test task below.",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Complete Task",
                        callback_data="claim_test_task",
                    )
                ],
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
        ),
        parse_mode="Markdown",
    )


# ============================================================
# TEST TASK
# ============================================================

async def claim_test_task(
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
            "⚠️ Account not found.",
            reply_markup=back_menu(),
        )
        return

    if user.get("banned", False):
        await query.edit_message_text(
            "🚫 Your account has been banned."
        )
        return

    settings = get_bot_settings() or {}
    task_reward = max(0, int(settings.get("task_reward", 10) or 10))
    daily_task_limit = max(1, int(settings.get("daily_task_limit", MAX_DAILY_TASKS) or MAX_DAILY_TASKS))

    daily_count = user.get(
        "daily_task_count",
        0,
    )

    last_task_reset = user.get(
        "last_task_reset",
        0,
    )

    now = int(time.time())

    if last_task_reset == 0:
        daily_count = 0
        last_task_reset = now

    elif now - last_task_reset >= 86400:
        daily_count = 0
        last_task_reset = now

    if daily_count >= daily_task_limit:
        await query.edit_message_text(
            "🚫 **DAILY TASK LIMIT REACHED**\n\n"
            f"You have completed "
            f"{daily_task_limit} tasks today.\n\n"
            "Please come back later.",
            reply_markup=back_menu(),
            parse_mode="Markdown",
        )
        return

    if not use_energy(
        user_id,
        1,
    ):
        await query.edit_message_text(
            "⚡ **NOT ENOUGH ENERGY**\n\n"
            "You need at least 1 Energy "
            "to complete this task.",
            reply_markup=back_menu(),
            parse_mode="Markdown",
        )
        return

    reward = task_reward

    add_balance(
        user_id,
        reward,
    )

    xp_result = add_xp(
        user_id,
        5,
    )

    daily_count += 1

    update_user(
        user_id,
        {
            "task_completed": (
                user.get(
                    "task_completed",
                    0,
                )
                + 1
            ),
            "daily_task_count": daily_count,
            "last_task_reset": last_task_reset,
        },
    )

    add_activity(
        user_id,
        "📋 Test Task Completed",
        reward,
    )

    level_text = ""

    if xp_result.get("level_up"):
        level_text = (
            "\n🎉 **LEVEL UP!**\n"
            f"🏆 New Level: "
            f"{xp_result.get('level', 1)}\n"
        )

    await query.edit_message_text(
        "✅ **TASK COMPLETED!**\n\n"
        f"💰 Reward: +{reward} Points\n"
        "⚡ Energy Used: 1\n"
        "⭐ XP: +5\n"
        f"📊 Daily Tasks: "
        f"{daily_count}/{daily_task_limit}\n"
        f"{level_text}",
        reply_markup=back_menu(),
        parse_mode="Markdown",
    )


# ============================================================
# SHORTLINKS
# ============================================================

async def shortlinks(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    from shortlinks import shortlinks_page
    await shortlinks_page(update, context)


# ============================================================
# SPIN WHEEL
# ============================================================

async def spin_wheel(
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
            "⚠️ Account not found.",
            reply_markup=back_menu(),
        )
        return

    if user.get("banned", False):
        await query.edit_message_text(
            "🚫 Your account has been banned."
        )
        return

    now = int(time.time())

    last_spin = user.get(
        "last_spin",
        0,
    )

    if last_spin:
        remaining = (
            SPIN_COOLDOWN
            - (now - last_spin)
        )

        if remaining > 0:
            await query.edit_message_text(
                "⏳ **SPIN WHEEL**\n\n"
                f"Please wait {remaining} seconds "
                "before spinning again.",
                reply_markup=back_menu(),
                parse_mode="Markdown",
            )
            return

    if not use_energy(
        user_id,
        SPIN_COST_ENERGY,
    ):
        await query.edit_message_text(
            "⚡ **NOT ENOUGH ENERGY**\n\n"
            "You need 1 Energy to spin.",
            reply_markup=back_menu(),
            parse_mode="Markdown",
        )
        return

    rewards = [
        0,
        5,
        10,
        20,
        25,
        50,
    ]

    reward = random.choice(
        rewards
    )

    update_user(
        user_id,
        {
            "last_spin": now,
            "spin_wins": (
                user.get(
                    "spin_wins",
                    0,
                )
                + (
                    1
                    if reward > 0
                    else 0
                )
            ),
        },
    )

    if reward > 0:
        add_balance(
            user_id,
            reward,
        )

    xp_result = add_xp(
        user_id,
        3,
    )

    add_activity(
        user_id,
        "🎡 Spin Wheel",
        reward,
    )

    level_text = ""

    if xp_result.get("level_up"):
        level_text = (
            "\n🎉 LEVEL UP!\n"
            f"🏆 Level: "
            f"{xp_result.get('level', 1)}\n"
        )

    await query.edit_message_text(
        "🎡 **SPIN WHEEL RESULT**\n\n"
        f"🎁 Reward: +{reward} Points\n"
        "⚡ Energy Used: 1\n"
        "⭐ XP: +3\n"
        f"{level_text}",
        reply_markup=back_menu(),
        parse_mode="Markdown",
    )


# ============================================================
# LUCKY BOX
# ============================================================

async def lucky_box(
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
            "⚠️ Account not found.",
            reply_markup=back_menu(),
        )
        return

    if user.get("banned", False):
        await query.edit_message_text(
            "🚫 Your account has been banned."
        )
        return

    now = int(time.time())

    last_box = user.get(
        "last_lucky_box",
        0,
    )

    if last_box:
        remaining = (
            LUCKY_BOX_COOLDOWN
            - (now - last_box)
        )

        if remaining > 0:
            await query.edit_message_text(
                "⏳ **LUCKY BOX**\n\n"
                f"Please wait {remaining} seconds.",
                reply_markup=back_menu(),
                parse_mode="Markdown",
            )
            return

    if not use_energy(
        user_id,
        LUCKY_BOX_COST_ENERGY,
    ):
        await query.edit_message_text(
            "⚡ **NOT ENOUGH ENERGY**\n\n"
            "You need 1 Energy to open Lucky Box.",
            reply_markup=back_menu(),
            parse_mode="Markdown",
        )
        return

    rewards = [
        0,
        5,
        10,
        20,
        30,
        50,
        100,
    ]

    reward = random.choice(
        rewards
    )

    update_user(
        user_id,
        {
            "last_lucky_box": now,
            "lucky_box_wins": (
                user.get(
                    "lucky_box_wins",
                    0,
                )
                + (
                    1
                    if reward > 0
                    else 0
                )
            ),
        },
    )

    if reward > 0:
        add_balance(
            user_id,
            reward,
        )

    xp_result = add_xp(
        user_id,
        3,
    )

    add_activity(
        user_id,
        "🎁 Lucky Box",
        reward,
    )

    level_text = ""

    if xp_result.get("level_up"):
        level_text = (
            "\n🎉 LEVEL UP!\n"
            f"🏆 Level: "
            f"{xp_result.get('level', 1)}\n"
        )

    await query.edit_message_text(
        "🎁 **LUCKY BOX OPENED!**\n\n"
        f"💰 Reward: +{reward} Points\n"
        "⚡ Energy Used: 1\n"
        "⭐ XP: +3\n"
        f"{level_text}",
        reply_markup=back_menu(),
        parse_mode="Markdown",
    )


# ============================================================
# SCRATCH CARD
# ============================================================

async def scratch_card(
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
            "⚠️ Account not found.",
            reply_markup=back_menu(),
        )
        return

    if user.get("banned", False):
        await query.edit_message_text(
            "🚫 Your account has been banned."
        )
        return

    now = int(time.time())

    last_scratch = user.get(
        "last_scratch",
        0,
    )

    if last_scratch:
        remaining = (
            SCRATCH_COOLDOWN
            - (now - last_scratch)
        )

        if remaining > 0:
            await query.edit_message_text(
                "⏳ **SCRATCH CARD**\n\n"
                f"Please wait {remaining} seconds.",
                reply_markup=back_menu(),
                parse_mode="Markdown",
            )
            return

    if not use_energy(
        user_id,
        SCRATCH_COST_ENERGY,
    ):
        await query.edit_message_text(
            "⚡ **NOT ENOUGH ENERGY**\n\n"
            "You need 1 Energy to scratch.",
            reply_markup=back_menu(),
            parse_mode="Markdown",
        )
        return

    rewards = [
        0,
        5,
        10,
        15,
        25,
        50,
    ]

    reward = random.choice(
        rewards
    )

    update_user(
        user_id,
        {
            "last_scratch": now,
            "scratch_wins": (
                user.get(
                    "scratch_wins",
                    0,
                )
                + (
                    1
                    if reward > 0
                    else 0
                )
            ),
        },
    )

    if reward > 0:
        add_balance(
            user_id,
            reward,
        )

    xp_result = add_xp(
        user_id,
        3,
    )

    add_activity(
        user_id,
        "🎫 Scratch Card",
        reward,
    )

    level_text = ""

    if xp_result.get("level_up"):
        level_text = (
            "\n🎉 LEVEL UP!\n"
            f"🏆 Level: "
            f"{xp_result.get('level', 1)}\n"
        )

    await query.edit_message_text(
        "🎫 **SCRATCH CARD RESULT**\n\n"
        f"💰 Reward: +{reward} Points\n"
        "⚡ Energy Used: 1\n"
        "⭐ XP: +3\n"
        f"{level_text}",
        reply_markup=back_menu(),
        parse_mode="Markdown",
    )


# ============================================================
# ENERGY PAGE
# ============================================================

async def energy_page(
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
            "⚠️ Account not found.",
            reply_markup=back_menu(),
        )
        return

    if user.get("banned", False):
        await query.edit_message_text(
            "🚫 Your account has been banned."
        )
        return

    energy_value = update_energy(
        user_id
    )

    user = get_user(
        user_id,
        create=False,
    )

    max_energy = user.get(
        "max_energy",
        100,
    )

    await query.edit_message_text(
        "⚡ **ENERGY CENTER**\n\n"
        f"⚡ Energy: "
        f"{energy_value}/{max_energy}\n\n"
        "🔄 Energy regenerates automatically.\n"
        "⏱️ Regeneration: 1 Energy / 60 seconds\n\n"
        "💡 Some earning activities use Energy.",
        reply_markup=back_menu(),
        parse_mode="Markdown",
    )


# Backward-compatible alias
energy = energy_page


# ============================================================
# HANDLER MAP
# ============================================================

EARN_HANDLERS = {
    "earn": earn_page,
    "daily_bonus": daily_bonus,
    "tasks": tasks,
    "shortlinks": shortlinks,
    "spin": spin_wheel,
    "lucky_box": lucky_box,
    "scratch": scratch_card,
    "energy": energy_page,
    "claim_test_task": claim_test_task,
}


# ============================================================
# EXPORTS
# ============================================================
__all__ = [
    "earn_page",
    "earn",
    "daily_bonus",
    "tasks",
    "claim_test_task",
    "shortlinks",
    "spin_wheel",
    "lucky_box",
    "scratch_card",
    "energy_page",
    "energy",
    "EARN_HANDLERS",
]
