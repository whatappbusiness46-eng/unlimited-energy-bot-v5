# ============================================================
# config.py
# Unlimited Energy Bot V2
# FINAL CENTRAL CONFIGURATION
# ============================================================

import os


# ============================================================
# BOT
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN environment variable is not configured."
    )


BOT_NAME = "Unlimited Energy Bot"
BOT_VERSION = "V2.1-FINAL"


# ============================================================
# DATABASE
# ============================================================

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError(
        "MONGO_URI environment variable is not configured."
    )

DATABASE_NAME = os.getenv(
    "DATABASE_NAME",
    "UnlimitedEnergy",
)

COLLECTION_NAME = "users"


# ============================================================
# ADMIN
# ============================================================

# Recommended:
# Set ADMIN_ID in Render Environment Variables.
#
# Example:
# ADMIN_ID=7713476833

try:
    ADMIN_ID = int(
        os.getenv(
            "ADMIN_ID",
            "7713476833",
        )
    )
except ValueError:
    raise RuntimeError(
        "ADMIN_ID must be a valid Telegram user ID."
    )


# ============================================================
# FORCE JOIN
# ============================================================

GROUPS = [
    "@UnlimitedEnergyTasks",
    "@UnlimitedEnergyRewards",
    "@UnlimitedEnergyCommunity",
    "@UnlimitedEnergyOfficial",
]


# Reward for successfully completing force join.
GROUP_JOIN_REWARD = 20


# ============================================================
# WITHDRAW
# ============================================================

MIN_WITHDRAW = 1000
# IMPORTANT:
# Replace these placeholders with your real payment details
# through Render Environment Variables.

BKASH_NUMBER = os.getenv(
    "BKASH_NUMBER",
    "017XXXXXXXX",
)

NAGAD_NUMBER = os.getenv(
    "NAGAD_NUMBER",
    "018XXXXXXXX",
)

BYBIT_UID = os.getenv(
    "BYBIT_UID",
    "YOUR_BYBIT_UID",
)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")

PREMIUM_CASH_PRICE = float(os.getenv("PREMIUM_CASH_PRICE", "199"))
PREMIUM_MULTIPLIER = float(os.getenv("PREMIUM_MULTIPLIER", "2.0"))
VIP1_CASH_PRICE = float(os.getenv("VIP1_CASH_PRICE", "299"))
VIP2_CASH_PRICE = float(os.getenv("VIP2_CASH_PRICE", "499"))
VIP3_CASH_PRICE = float(os.getenv("VIP3_CASH_PRICE", "799"))
VIP4_CASH_PRICE = float(os.getenv("VIP4_CASH_PRICE", "1199"))
VIP5_CASH_PRICE = float(os.getenv("VIP5_CASH_PRICE", "1799"))


# ============================================================
# WITHDRAW STATUS
# ============================================================

WITHDRAW_PENDING = "pending"
WITHDRAW_APPROVED = "approved"
WITHDRAW_REJECTED = "rejected"


# ============================================================
# DAILY BONUS
# ============================================================

DAILY_BONUS = 5
DAILY_XP = 5

# Day 7 special reward.
DAY7_BONUS = 25

# Maximum normal streak display/tracking limit.
MAX_DAILY_STREAK = 7


# ============================================================
# DAILY TASKS
# ============================================================

MAX_DAILY_TASKS = 5

TASK_REWARD_MIN = 5
TASK_REWARD_MAX = 50

TASK_XP = 5
TASK_ENERGY_COST = 1


# ============================================================
# OFFERS
# ============================================================

OFFER_REWARD_MIN = 10
OFFER_REWARD_MAX = 100

OFFER_XP = 10


# ============================================================
# SHORTLINK
# ============================================================

SHORTLINK_REWARD_MIN = 5
SHORTLINK_REWARD_MAX = 50

SHORTLINK_XP = 10


# ============================================================
# REFERRAL
# ============================================================

REFERRAL_REWARD = 10
REFERRAL_XP = 10

MAX_REFERRAL_REWARD_PER_USER = 1000


# ============================================================
# ENERGY
# ============================================================

MAX_ENERGY = 100

# One energy every 300 seconds.
ENERGY_REGEN_SECONDS = 300


# ============================================================
# SPIN WHEEL
# ============================================================

SPIN_MIN = 1
SPIN_MAX = 20

SPIN_TICKET_REWARD = 1

# 0 means no cooldown.
SPIN_COOLDOWN = 0


# ============================================================
# LUCKY BOX
# ============================================================

LUCKYBOX_MIN = 5
LUCKYBOX_MAX = 30

LUCKYBOX_TICKET_REWARD = 1

LUCKYBOX_COOLDOWN = 0


# ============================================================
# SCRATCH CARD
# ============================================================

SCRATCH_MIN = 2
SCRATCH_MAX = 15

SCRATCH_CARD_REWARD = 1

SCRATCH_COOLDOWN = 0


# ============================================================
# JACKPOT
# ============================================================

JACKPOT_MIN = 10
JACKPOT_MAX = 100

JACKPOT_TICKET_REWARD = 1

JACKPOT_COOLDOWN = 0


# ============================================================
# PREMIUM
# ============================================================

PREMIUM_PRICE = 199
PREMIUM_DAYS = 30

FIRST_PREMIUM_WINNERS = 5


# ============================================================
# VIP
# ============================================================

VIP_PRICE = 499
VIP_DAYS = 30


# ============================================================
# XP / LEVEL
# ============================================================

XP_PER_LEVEL = 100


# ============================================================
# RANK REQUIREMENTS
# ============================================================

BRONZE_REQUIRED = 600
SILVER_REQUIRED = 2000
GOLD_REQUIRED = 6000
DIAMOND_REQUIRED = 10000


# ============================================================
# GAME / REWARD SECURITY
# ============================================================

# Prevent impossible negative rewards.
MIN_REWARD = 0

# Maximum reward that one individual game/action can give.
MAX_SINGLE_REWARD = 1000


# ============================================================
# NOTIFICATIONS
# ============================================================

ENABLE_NOTIFICATIONS = True


# ============================================================
# LEADERBOARD / ACTIVITY
# ============================================================

LEADERBOARD_LIMIT = 10
ACTIVITY_LIMIT = 10


# ============================================================
# PAGINATION
# ============================================================

PAGE_SIZE = 10


# ============================================================
# CALLBACK SECURITY
# ============================================================

MAX_CALLBACK_DATA_LENGTH = 64


# ============================================================
# BOT FEATURES
# ============================================================

FEATURES = {
    "daily_bonus": True,
    "daily_tasks": True,
    "offers": True,
    "shortlinks": True,
    "spin": True,
    "lucky_box": True,
    "scratch_card": True,
    "jackpot": True,
    "referral": True,
    "withdraw": True,
    "premium": True,
    "vip": True,
    "leaderboard": True,
    "activity": True,
    "statistics": True,
    "force_join": True,
}


# ============================================================
# DEFAULT USER VALUES
# ============================================================

DEFAULT_USER_VALUES = {
    "balance": 0,
    "xp": 0,
    "level": 1,
    "energy": MAX_ENERGY,
    "daily_streak": 0,
    "daily_task_count": 0,
    "referrals": 0,
    "spin_tickets": 0,
    "luckybox_tickets": 0,
    "scratch_tickets": 0,
    "jackpot_tickets": 0,
    "banned": False,
    "blacklisted": False,
}


# ============================================================
# LOGGING / DEBUG
# ============================================================

DEBUG_MODE = (
    os.getenv(
        "DEBUG_MODE",
        "false",
    ).lower()
    == "true"
)


# ============================================================
# TIMEZONE
# ============================================================

TIMEZONE = os.getenv(
    "TIMEZONE",
    "Asia/Dhaka",
)


# ============================================================
# ENVIRONMENT
# ============================================================

ENVIRONMENT = os.getenv(
    "ENVIRONMENT",
    "production",
)




# ============================================================
# PROVIDER INTEGRATIONS
# ============================================================

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
REWARD_POINTS_PER_USD = int(os.getenv("REWARD_POINTS_PER_USD", "1000"))

# CPAGrip
CPAGRIP_ENABLED = os.getenv("CPAGRIP_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
CPAGRIP_API_KEY = os.getenv("CPAGRIP_API_KEY", "")
CPAGRIP_OFFERS_API_URL = os.getenv("CPAGRIP_OFFERS_API_URL", "")
CPAGRIP_POSTBACK_PASSWORD = os.getenv("CPAGRIP_POSTBACK_PASSWORD", os.getenv("CPAGRIP_POSTBACK_SECRET", ""))

# Shortlink providers.
# Their exact API URL/parameter contract must be copied from the provider
# documentation; the bot never guesses an undocumented endpoint.
SHRTFLY_ENABLED = os.getenv("SHRTFLY_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
SHRTFLY_API_TOKEN = os.getenv("SHRTFLY_API_TOKEN", "")
SHRTFLY_API_URL = os.getenv("SHRTFLY_API_URL", "")

SHRINKME_ENABLED = os.getenv("SHRINKME_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
SHRINKME_API_KEY = os.getenv("SHRINKME_API_KEY", "")
SHRINKME_API_URL = os.getenv("SHRINKME_API_URL", "")

CONFIG_READY = True

CPAGRIP_USER_REWARD_PERCENT = float(os.getenv("CPAGRIP_USER_REWARD_PERCENT", "40"))
