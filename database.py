from config import PREMIUM_MULTIPLIER
# ============================================================
# database.py
# Unlimited Energy Bot V2
# FINAL DATABASE LAYER
# PART 1/8
# ============================================================

import time
import uuid
import logging

from pymongo import (
    MongoClient,
    ASCENDING,
    DESCENDING,
)

from pymongo.errors import (
    DuplicateKeyError,
)

from config import (
    MONGO_URI,
    DATABASE_NAME,
    COLLECTION_NAME,
    MAX_ENERGY,
    ENERGY_REGEN_SECONDS,
    XP_PER_LEVEL,
    LEADERBOARD_LIMIT,
    ACTIVITY_LIMIT,
)


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# DATABASE CONNECTION
# ============================================================

if not MONGO_URI:
    raise RuntimeError(
        "MONGO_URI environment variable is not configured."
    )


client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=10000,
    connectTimeoutMS=10000,
    socketTimeoutMS=10000,
)


db = client[DATABASE_NAME]


# ============================================================
# COLLECTIONS
# ============================================================

users = db[COLLECTION_NAME]

transactions = db[
    "transactions"
]

withdrawals = db[
    "withdrawals"
]

security_logs = db[
    "security_logs"
]

daily_statistics = db[
    "daily_statistics"
]

bot_settings = db[
    "bot_settings"
]


# ============================================================
# DATABASE INDEXES
# ============================================================

def ensure_indexes():
    """
    Create required MongoDB indexes safely.

    Existing indexes are checked first to avoid
    IndexOptionsConflict during repeated deployments.
    """

    try:

        # ----------------------------------------------------
        # USERS
        # ----------------------------------------------------

        existing_indexes = (
            users.index_information()
        )

        user_id_index_exists = False

        for (
            index_name,
            index_info,
        ) in existing_indexes.items():

            key_list = index_info.get(
                "key",
                [],
            )

            if key_list == [
                (
                    "user_id",
                    ASCENDING,
                )
            ]:

                user_id_index_exists = True
                break

        if not user_id_index_exists:

            users.create_index(
                [
                    (
                        "user_id",
                        ASCENDING,
                    )
                ],
                unique=True,
                name="user_id_unique",
            )

        users.create_index(
            [
                (
                    "balance",
                    DESCENDING,
                )
            ],
        )

        users.create_index(
            [
                (
                    "last_login",
                    DESCENDING,
                )
            ],
            name="last_login_desc",
        )

        users.create_index(
            [
                (
                    "banned",
                    ASCENDING,
                )
            ],
            name="banned_index",
        )

        # ----------------------------------------------------
        # TRANSACTIONS
        # ----------------------------------------------------

        transactions.create_index(
            [
                (
                    "transaction_id",
                    ASCENDING,
                )
            ],
            unique=True,
            name="transaction_id_unique",
        )

        transactions.create_index(
            [
                (
                    "user_id",
                    ASCENDING,
                ),
                (
                    "created_at",
                    DESCENDING,
                ),
            ],
            name="user_transactions",
        )

        # ----------------------------------------------------
        # WITHDRAWALS
        # ----------------------------------------------------

        withdrawals.create_index(
            [
                (
                    "withdrawal_id",
                    ASCENDING,
                )
            ],
            unique=True,
            name="withdrawal_id_unique",
        )

        withdrawals.create_index(
            [
                (
                    "user_id",
                    ASCENDING,
                ),
                (
                    "created_at",
                    DESCENDING,
                ),
            ],
            name="user_withdrawals",
        )

        withdrawals.create_index(
            [
                (
                    "status",
                    ASCENDING,
                ),
                (
                    "created_at",
                    DESCENDING,
                ),
            ],
            name="withdrawal_status",
        )

        # ----------------------------------------------------
        # SECURITY LOGS
        # ----------------------------------------------------

        security_logs.create_index(
            [
                (
                    "user_id",
                    ASCENDING,
                ),
                (
                    "created_at",
                    DESCENDING,
                ),
            ],
            name="user_security_logs",
        )

        # ----------------------------------------------------
        # DAILY STATISTICS
        # ----------------------------------------------------

        daily_statistics.create_index(
            [
                (
                    "date",
                    ASCENDING,
                )
            ],
            unique=True,
            name="statistics_date_unique",
        )

    except Exception as error:

        logger.warning(
            "Database index setup warning: %s",
            error,
        )


# ============================================================
# DEFAULT USER DOCUMENT
# ============================================================

def build_default_user(user_id):

    now = int(
        time.time()
    )

    return {

        # ====================================================
        # BASIC
        # ====================================================

        "user_id": int(user_id),

        "username": "",

        "first_name": "",

        "last_name": "",

        "banned": False,

        "blacklisted": False,


        # ====================================================
        # WALLET
        # ====================================================

        "balance": 0,

        "bonus_balance": 0,

        "premium_balance": 0,

        "total_earned": 0,

        "total_spent": 0,


        # ====================================================
        # EARNING
        # ====================================================

        "offer_completed": 0,

        "shortlink_completed": 0,

        "daily_task_count": 0,

        "last_task_reset": 0,


        # ====================================================
        # DAILY
        # ====================================================

        "last_daily": 0,

        "daily_streak": 0,


        # ====================================================
        # SPIN
        # ====================================================

        "spin_ticket": 0,

        "last_spin": 0,

        "spin_wins": 0,

        "spin_count": 0,


        # ====================================================
        # LUCKY BOX
        # ====================================================

        "lucky_box": 0,

        "last_lucky_box": 0,

        "lucky_box_wins": 0,

        "lucky_box_count": 0,


        # ====================================================
        # SCRATCH CARD
        # ====================================================

        "scratch_card": 0,

        "last_scratch": 0,

        "scratch_wins": 0,

        "scratch_count": 0,


        # ====================================================
        # JACKPOT
        # ====================================================

        "jackpot_ticket": 0,

        "last_jackpot": 0,

        "jackpot_wins": 0,

        "jackpot_count": 0,


        # ====================================================
        # ENERGY
        # ====================================================

        "energy": MAX_ENERGY,

        "max_energy": MAX_ENERGY,

        "last_energy_update": now,


        # ====================================================
        # XP / LEVEL
        # ====================================================

        "xp": 0,

        "level": 1,

        "rank": "🔰 Beginner",


        # ====================================================
        # REFERRAL
        # ====================================================

        "referrals": 0,

        "referred_by": None,

        "referral_earn": 0,

        "referral_xp": 0,

        "referral_reward_given": False,

        "referral_ids": [],


        # ====================================================
        # PREMIUM
        # ====================================================

        "premium": False,

        "premium_expire": 0,

        "premium_balance": 0,


        # ====================================================
        # VIP
        # ====================================================

        "vip": False,

        "vip_expire": 0,


        # ====================================================
        # FORCE JOIN
        # ====================================================

        "group_reward": False,

        "groups_verified": False,

        "verified_at": 0,


        # ====================================================
        # WITHDRAW
        # ====================================================

        "withdraw_pending": 0,

        "total_withdraw": 0,

        "withdraw_history": [],


        # ====================================================
        # ACTIVITY
        # ====================================================

        "activity": [],


        # ====================================================
        # TRANSACTIONS
        # ====================================================

        "transactions": [],


        # ====================================================
        # ACHIEVEMENTS
        # ====================================================

        "badges": [],

        "achievements": [],


        # ====================================================
        # NOTIFICATIONS
        # ====================================================

        "notifications": True,


        # ====================================================
        # COUPONS
        # ====================================================

        "used_coupons": [],


        # ====================================================
        # GIFTS
        # ====================================================

        "gift_claimed": [],


        # ====================================================
        # TASK PROTECTION
        # ====================================================

        "completed_tasks": [],

        "completed_offers": [],

        "completed_shortlinks": [],


        # ====================================================
        # SECURITY
        # ====================================================

        "last_ip": "",

        "device_id": "",

        "suspicious_activity": False,

        "suspicious_count": 0,

        "security_flags": [],


        # ====================================================
        # COOLDOWN / ABUSE
        # ====================================================

        "last_reward": 0,

        "last_task": 0,

        "last_offer": 0,

        "last_shortlink": 0,


        # ====================================================
        # LANGUAGE
        # ====================================================

        "language": "en",


        # ====================================================
        # LOGIN / ACTIVITY TIME
        # ====================================================

        "last_login": now,

        "last_active": now,


        # ====================================================
        # CREATED
        # ====================================================

        "created_at": now,

    }


# ============================================================
# CREATE USER
# ============================================================

def create_user(
    user_id,
    username="",
    first_name="",
    last_name="",
):

    user_id = int(
        user_id
    )

    existing = users.find_one(
        {
            "user_id": user_id
        }
    )

    if existing:

        update_data = {}

        if username:
            update_data[
                "username"
            ] = username

        if first_name:
            update_data[
                "first_name"
            ] = first_name

        if last_name:
            update_data[
                "last_name"
            ] = last_name

        if update_data:

            update_data[
                "last_active"
            ] = int(
                time.time()
            )

            users.update_one(
                {
                    "user_id": user_id
                },
                {
                    "$set": update_data
                },
            )

        return get_user(
            user_id,
            create=False,
        )

    new_user = build_default_user(
        user_id
    )

    if username:
        new_user[
            "username"
        ] = username

    if first_name:
        new_user[
            "first_name"
        ] = first_name

    if last_name:
        new_user[
            "last_name"
        ] = last_name

    try:

        users.insert_one(
            new_user
        )

    except DuplicateKeyError:

        return get_user(
            user_id,
            create=False,
        )

    return new_user


# ============================================================
# GET USER
# ============================================================

def get_user(
    user_id,
    create=True,
):

    user_id = int(
        user_id
    )

    user = users.find_one(
        {
            "user_id": user_id
        }
    )

    if not user and create:

        return create_user(
            user_id
        )

    return user


# ============================================================
# UPDATE USER
# ============================================================

def update_user(
    user_id,
    data,
):

    if not data:
        return False

    user_id = int(
        user_id
    )

    result = users.update_one(
        {
            "user_id": user_id
        },
        {
            "$set": data
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# TOUCH USER
# ============================================================

def touch_user(
    user_id
):

    now = int(
        time.time()
    )

    result = users.update_one(
        {
            "user_id": int(
                user_id
            )
        },
        {
            "$set": {
                "last_active": now,
                "last_login": now,
            }
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# ADD BALANCE
# ============================================================

def add_balance(
    user_id,
    amount,
):

    amount = int(
        amount
    )

    if amount <= 0:
        return False

    user_id = int(
        user_id
    )

    get_user(
        user_id
    )

    result = users.update_one(
        {
            "user_id": user_id,
            "banned": {
                "$ne": True
            },
            "blacklisted": {
                "$ne": True
            },
        },
        {
            "$inc": {
                "balance": amount,
                "total_earned": amount,
            }
        },
    )

    if result.modified_count > 0:

        record_transaction(
            user_id=user_id,
            transaction_type="credit",
            amount=amount,
            source="balance_reward",
        )

        update_daily_statistic(
            field="total_points_distributed",
            amount=amount,
        )

        return True

    return False


# ============================================================
# ADD BONUS BALANCE
# ============================================================

def add_bonus(
    user_id,
    amount,
):

    amount = int(
        amount
    )

    if amount <= 0:
        return False

    user_id = int(
        user_id
    )

    get_user(
        user_id
    )

    result = users.update_one(
        {
            "user_id": user_id,
            "banned": {
                "$ne": True
            },
            "blacklisted": {
                "$ne": True
            },
        },
        {
            "$inc": {
                "bonus_balance": amount,
                "total_earned": amount,
            }
        },
    )

    if result.modified_count > 0:

        record_transaction(
            user_id=user_id,
            transaction_type="bonus_credit",
            amount=amount,
            source="bonus_reward",
        )

        update_daily_statistic(
            field="total_points_distributed",
            amount=amount,
        )

        return True

    return False


# ============================================================
# REMOVE BALANCE
# ============================================================

def remove_balance(
    user_id,
    amount,
):

    amount = int(
        amount
    )

    if amount <= 0:
        return 0

    user_id = int(
        user_id
    )

    result = users.update_one(
        {
            "user_id": user_id,
            "balance": {
                "$gte": amount
            },
        },
        {
            "$inc": {
                "balance": -amount,
                "total_spent": amount,
            }
        },
    )

    if result.modified_count <= 0:
        return 0

    record_transaction(
        user_id=user_id,
        transaction_type="debit",
        amount=amount,
        source="balance_remove",
    )

    return amount

# ============================================================
# ADD XP
# ============================================================

def add_xp(
    user_id,
    amount,
):

    amount = int(
        amount
    )

    user = get_user(
        user_id
    )

    if amount <= 0:

        return {
            "xp": user.get(
                "xp",
                0,
            ),
            "level": user.get(
                "level",
                1,
            ),
            "level_up": False,
        }

    old_xp = int(
        user.get(
            "xp",
            0,
        )
    )

    old_level = int(
        user.get(
            "level",
            1,
        )
    )

    new_xp = (
        old_xp + amount
    )

    new_level = (
        new_xp
        // XP_PER_LEVEL
    ) + 1

    if new_level < 1:
        new_level = 1

    users.update_one(
        {
            "user_id": int(
                user_id
            )
        },
        {
            "$inc": {
                "xp": amount
            },
            "$set": {
                "level": new_level
            },
        },
    )

    return {
        "xp": new_xp,
        "level": new_level,
        "level_up": (
            new_level
            > old_level
        ),
    }


# ============================================================
# ADD ACTIVITY
# ============================================================

def add_activity(
    user_id,
    action,
    amount=0,
):

    user_id = int(
        user_id
    )

    now = int(
        time.time()
    )

    activity = {
        "action": str(
            action
        ),
        "amount": int(
            amount or 0
        ),
        "time": now,
    }

    get_user(
        user_id
    )

    users.update_one(
        {
            "user_id": user_id
        },
        {
            "$push": {
                "activity": {
                    "$each": [
                        activity
                    ],
                    "$slice": (
                        -ACTIVITY_LIMIT
                    ),
                }
            },
            "$set": {
                "last_active": now,
            },
        },
    )

    return activity


# ============================================================
# TRANSACTION ID
# ============================================================

def generate_transaction_id():

    return (
        "TXN-"
        + uuid.uuid4()
        .hex
        .upper()
    )


# ============================================================
# RECORD TRANSACTION
# ============================================================

def record_transaction(
    user_id,
    transaction_type,
    amount,
    source="unknown",
    status="completed",
    metadata=None,
):

    transaction_id = (
        generate_transaction_id()
    )

    transaction = {

        "transaction_id":
            transaction_id,

        "user_id":
            int(user_id),

        "type":
            str(
                transaction_type
            ),

        "amount":
            int(amount),

        "source":
            str(source),

        "status":
            str(status),

        "metadata":
            metadata or {},

        "created_at":
            int(
                time.time()
            ),

    }

    try:

        transactions.insert_one(
            transaction
        )

    except Exception as error:

        logger.error(
            "Transaction insert failed: %s",
            error,
        )

    try:

        users.update_one(
            {
                "user_id": int(
                    user_id
                )
            },
            {
                "$push": {
                    "transactions": {
                        "$each": [
                            transaction
                        ],
                        "$slice": -100,
                    }
                }
            },
        )

    except Exception as error:

        logger.error(
            "User transaction history update failed: %s",
            error,
        )

    return transaction_id


# ============================================================
# GET TRANSACTIONS
# ============================================================

def get_transactions(
    user_id,
    limit=20,
):

    return list(
        transactions.find(
            {
                "user_id": int(
                    user_id
                )
            }
        )
        .sort(
            "created_at",
            DESCENDING,
        )
        .limit(
            int(limit)
        )
    )


# ============================================================
# ADD SPIN TICKET
# ============================================================

def add_spin_ticket(
    user_id,
    amount=1,
):

    amount = int(
        amount
    )

    if amount <= 0:
        return False

    result = users.update_one(
        {
            "user_id": int(
                user_id
            )
        },
        {
            "$inc": {
                "spin_ticket": amount
            }
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# USE SPIN TICKET
# ============================================================

def use_spin_ticket(
    user_id
):

    result = users.update_one(
        {
            "user_id": int(
                user_id
            ),
            "spin_ticket": {
                "$gt": 0
            },
        },
        {
            "$inc": {
                "spin_ticket": -1
            }
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# ADD LUCKY BOX
# ============================================================

def add_lucky_box(
    user_id,
    amount=1,
):

    amount = int(
        amount
    )

    if amount <= 0:
        return False

    result = users.update_one(
        {
            "user_id": int(
                user_id
            )
        },
        {
            "$inc": {
                "lucky_box": amount
            }
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# USE LUCKY BOX
# ============================================================

def use_lucky_box(
    user_id
):

    result = users.update_one(
        {
            "user_id": int(
                user_id
            ),
            "lucky_box": {
                "$gt": 0
            },
        },
        {
            "$inc": {
                "lucky_box": -1
            }
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# ADD SCRATCH CARD
# ============================================================

def add_scratch_card(
    user_id,
    amount=1,
):

    amount = int(
        amount
    )

    if amount <= 0:
        return False

    result = users.update_one(
        {
            "user_id": int(
                user_id
            )
        },
        {
            "$inc": {
                "scratch_card": amount
            }
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# USE SCRATCH CARD
# ============================================================

def use_scratch_card(
    user_id
):

    result = users.update_one(
        {
            "user_id": int(
                user_id
            ),
            "scratch_card": {
                "$gt": 0
            },
        },
        {
            "$inc": {
                "scratch_card": -1
            }
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# ADD JACKPOT TICKET
# ============================================================

def add_jackpot_ticket(
    user_id,
    amount=1,
):

    amount = int(
        amount
    )

    if amount <= 0:
        return False

    result = users.update_one(
        {
            "user_id": int(
                user_id
            )
        },
        {
            "$inc": {
                "jackpot_ticket": amount
            }
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# USE JACKPOT TICKET
# ============================================================

def use_jackpot_ticket(
    user_id
):

    result = users.update_one(
        {
            "user_id": int(
                user_id
            ),
            "jackpot_ticket": {
                "$gt": 0
            },
        },
        {
            "$inc": {
                "jackpot_ticket": -1
            }
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# UPDATE ENERGY
# ============================================================

def update_energy(
    user_id
):

    user = get_user(
        user_id
    )

    now = int(
        time.time()
    )

    current_energy = int(
        user.get(
            "energy",
            MAX_ENERGY,
        )
    )

    max_energy = int(
        user.get(
            "max_energy",
            MAX_ENERGY,
        )
    )

    last_update = int(
        user.get(
            "last_energy_update",
            now,
        )
    )

    if current_energy >= max_energy:

        users.update_one(
            {
                "user_id": int(
                    user_id
                )
            },
            {
                "$set": {
                    "last_energy_update": now,
                }
            },
        )

        return max_energy

    elapsed = (
        now - last_update
    )

    if elapsed < ENERGY_REGEN_SECONDS:

        return current_energy

    recovered = (
        elapsed
        // ENERGY_REGEN_SECONDS
    )

    if recovered <= 0:

        return current_energy

    new_energy = min(
        max_energy,
        current_energy
        + recovered,
    )

    consumed_time = (
        recovered
        * ENERGY_REGEN_SECONDS
    )

    new_last_update = (
        last_update
        + consumed_time
    )

    users.update_one(
        {
            "user_id": int(
                user_id
            )
        },
        {
            "$set": {
                "energy": new_energy,
                "last_energy_update":
                    new_last_update,
            }
        },
    )

    return new_energy
      # ============================================================
# GET ENERGY
# ============================================================

def get_energy(
    user_id
):

    update_energy(
        user_id
    )

    user = get_user(
        user_id
    )

    return int(
        user.get(
            "energy",
            MAX_ENERGY,
        )
    )


# ============================================================
# USE ENERGY
# ============================================================

def use_energy(
    user_id,
    amount=1,
):

    amount = int(
        amount
    )

    if amount <= 0:

        return True

    update_energy(
        user_id
    )

    result = users.update_one(
        {
            "user_id": int(
                user_id
            ),
            "energy": {
                "$gte": amount
            },
        },
        {
            "$inc": {
                "energy": -amount
            }
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# RESET ENERGY
# ============================================================

def reset_energy(
    user_id
):

    now = int(
        time.time()
    )

    result = users.update_one(
        {
            "user_id": int(
                user_id
            )
        },
        {
            "$set": {
                "energy": MAX_ENERGY,
                "max_energy": MAX_ENERGY,
                "last_energy_update": now,
            }
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# GET BALANCE
# ============================================================

def get_balance(
    user_id
):

    user = get_user(
        user_id
    )

    return int(
        user.get(
            "balance",
            0,
        )
    )


# ============================================================
# GET XP
# ============================================================

def get_xp(
    user_id
):

    user = get_user(
        user_id
    )

    return int(
        user.get(
            "xp",
            0,
        )
    )


# ============================================================
# GET LEVEL
# ============================================================

def get_level(
    user_id
):

    user = get_user(
        user_id
    )

    return int(
        user.get(
            "level",
            1,
        )
    )


# ============================================================
# ENSURE DATABASE READY
# ============================================================

try:

    ensure_indexes()

except Exception as error:

    logger.warning(
        "Database initialization warning: %s",
        error,
    )          
# ============================================================
# database.py
# FINAL DATABASE LAYER
# PART 2/8
# ============================================================


# ============================================================
# SET ENERGY
# ============================================================

def set_energy(
    user_id,
    amount,
):

    user = get_user(
        user_id
    )

    if not user:
        return False

    max_energy = int(
        user.get(
            "max_energy",
            MAX_ENERGY,
        )
    )

    amount = max(
        0,
        min(
            int(amount),
            max_energy,
        ),
    )

    result = users.update_one(
        {
            "user_id": int(
                user_id
            )
        },
        {
            "$set": {
                "energy": amount,
                "last_energy_update":
                    int(time.time()),
            }
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# TOTAL USERS
# ============================================================

def total_users():

    return users.count_documents(
        {}
    )


# ============================================================
# ACTIVE USERS
# ============================================================

def active_users(
    seconds=86400,
):

    cutoff = (
        int(time.time())
        - int(seconds)
    )

    return users.count_documents(
        {
            "last_active": {
                "$gte": cutoff
            }
        }
    )


# ============================================================
# BANNED USERS
# ============================================================

def banned_users():

    return users.count_documents(
        {
            "banned": True
        }
    )


# ============================================================
# LEADERBOARD
# ============================================================

def leaderboard(
    limit=None,
):

    if limit is None:

        limit = (
            LEADERBOARD_LIMIT
        )

    return list(
        users.find(
            {
                "banned": {
                    "$ne": True
                }
            }
        )
        .sort(
            "balance",
            DESCENDING,
        )
        .limit(
            int(limit)
        )
    )


# ============================================================
# USER WITHDRAWAL LOCK
# ============================================================

def reserve_withdrawal(
    user_id,
    amount,
    method="",
    payment_account="",
):

    amount = int(
        amount
    )

    if amount <= 0:
        return None

    user_id = int(
        user_id
    )

    method = str(
        method
    ).strip()

    payment_account = str(
        payment_account
    ).strip()

    if (
        not method
        or not payment_account
    ):

        return None

    withdrawal_id = (
        "WD-"
        + uuid.uuid4()
        .hex
        .upper()
    )

    now = int(
        time.time()
    )

    result = users.update_one(
        {
            "user_id": user_id,

            "balance": {
                "$gte": amount
            },

            "banned": {
                "$ne": True
            },

            "blacklisted": {
                "$ne": True
            },
        },
        {
            "$inc": {

                "balance":
                    -amount,

                "withdraw_pending":
                    amount,
            }
        },
    )

    if result.modified_count <= 0:

        return None

    withdrawal = {

        "withdrawal_id":
            withdrawal_id,

        "user_id":
            user_id,

        "amount":
            amount,

        "method":
            method,

        "payment_account":
            payment_account,

        "status":
            "pending",

        "created_at":
            now,

        "updated_at":
            now,
    }

    try:

        withdrawals.insert_one(
            withdrawal
        )

        record_transaction(
            user_id=user_id,

            transaction_type=
                "withdrawal",

            amount=amount,

            source=
                "withdraw_request",

            status=
                "pending",

            metadata={

                "withdrawal_id":
                    withdrawal_id,

                "method":
                    method,

                "payment_account":
                    payment_account,
            },
        )

        update_daily_statistic(
            field=
                "pending_withdrawals",

            amount=1,
        )

    except Exception as error:

        users.update_one(
            {
                "user_id":
                    user_id
            },
            {
                "$inc": {

                    "balance":
                        amount,

                    "withdraw_pending":
                        -amount,
                }
            },
        )

        logger.error(
            "Withdrawal reservation failed: %s",
            error,
        )

        return None

    return withdrawal


# ============================================================
# APPROVE WITHDRAWAL
# ============================================================

def approve_withdrawal(
    withdrawal_id,
):

    withdrawal = (
        withdrawals.find_one(
            {
                "withdrawal_id":
                    withdrawal_id
            }
        )
    )

    if not withdrawal:

        return False

    if (
        withdrawal.get(
            "status"
        )
        != "pending"
    ):

        return False

    user_id = int(
        withdrawal[
            "user_id"
        ]
    )

    amount = int(
        withdrawal[
            "amount"
        ]
    )

    now = int(
        time.time()
    )

    result = withdrawals.update_one(
        {
            "withdrawal_id":
                withdrawal_id,

            "status":
                "pending",
        },
        {
            "$set": {

                "status":
                    "approved",

                "updated_at":
                    now,
            }
        },
    )

    if result.modified_count <= 0:

        return False

    users.update_one(
        {
            "user_id":
                user_id
        },
        {
            "$inc": {

                "withdraw_pending":
                    -amount,

                "total_withdraw":
                    amount,
            },

            "$push": {

                "withdraw_history": {

                    "$each": [

                        {

                            "withdrawal_id":
                                withdrawal_id,

                            "amount":
                                amount,

                            "status":
                                "approved",

                            "time":
                                now,
                        }
                    ],

                    "$slice":
                        -100,
                }
            },
        },
    )

    update_daily_statistic(field="pending_withdrawals", amount=-1)
    update_daily_statistic(field="withdrawals", amount=1)

    transactions.update_many(
        {"user_id": user_id, "type": "withdrawal", "metadata.withdrawal_id": withdrawal_id},
        {"$set": {"status": "approved"}},
    )
    try:
        users.update_one(
            {"user_id": user_id},
            {"$set": {"transactions.$[tx].status": "approved"}},
            array_filters=[{"tx.type": "withdrawal", "tx.metadata.withdrawal_id": withdrawal_id}],
        )
    except Exception:
        logger.exception("Embedded withdrawal approval sync failed | withdrawal=%s", withdrawal_id)

    return True


# ============================================================
# REJECT WITHDRAWAL
# ============================================================

def reject_withdrawal(
    withdrawal_id,
    reason="Rejected",
):

    withdrawal = (
        withdrawals.find_one(
            {
                "withdrawal_id":
                    withdrawal_id
            }
        )
    )

    if not withdrawal:

        return False

    if (
        withdrawal.get(
            "status"
        )
        != "pending"
    ):

        return False

    user_id = int(
        withdrawal[
            "user_id"
        ]
    )

    amount = int(
        withdrawal[
            "amount"
        ]
    )

    now = int(
        time.time()
    )

    result = withdrawals.update_one(
        {
            "withdrawal_id":
                withdrawal_id,

            "status":
                "pending",
        },
        {
            "$set": {

                "status":
                    "rejected",

                "reason":
                    str(reason),

                "updated_at":
                    now,
            }
        },
    )

    if result.modified_count <= 0:

        return False

    users.update_one(
        {
            "user_id":
                user_id
        },
        {
            "$inc": {

                "balance":
                    amount,

                "withdraw_pending":
                    -amount,
            },

            "$push": {

                "withdraw_history": {

                    "$each": [

                        {

                            "withdrawal_id":
                                withdrawal_id,

                            "amount":
                                amount,

                            "status":
                                "rejected",

                            "reason":
                                str(reason),

                            "time":
                                now,
                        }
                    ],

                    "$slice":
                        -100,
                }
            },
        },
    )

    update_daily_statistic(field="pending_withdrawals", amount=-1)

    transactions.update_many(
        {"user_id": user_id, "type": "withdrawal", "metadata.withdrawal_id": withdrawal_id},
        {"$set": {"status": "rejected", "metadata.rejection_reason": str(reason)}},
    )
    try:
        users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "transactions.$[tx].status": "rejected",
                    "transactions.$[tx].metadata.rejection_reason": str(reason),
                }
            },
            array_filters=[{"tx.type": "withdrawal", "tx.metadata.withdrawal_id": withdrawal_id}],
        )
    except Exception:
        logger.exception("Embedded withdrawal rejection sync failed | withdrawal=%s", withdrawal_id)

    return True


# ============================================================
# GET WITHDRAWALS
# ============================================================

def get_withdrawals(
    status=None,
    limit=50,
):

    query = {}

    if status:

        query[
            "status"
        ] = status

    return list(
        withdrawals.find(
            query
        )
        .sort(
            "created_at",
            DESCENDING,
        )
        .limit(
            int(limit)
        )
    )


# ============================================================
# SECURITY LOG
# ============================================================

def add_security_log(
    user_id,
    event,
    severity="low",
    metadata=None,
):

    log = {

        "log_id":
            "SEC-"
            + uuid.uuid4()
            .hex
            .upper(),

        "user_id":
            int(user_id),

        "event":
            str(event),

        "severity":
            str(severity),

        "metadata":
            metadata or {},

        "created_at":
            int(
                time.time()
            ),
    }

    try:

        security_logs.insert_one(
            log
        )

    except Exception as error:

        logger.error(
            "Security log failed: %s",
            error,
        )

    try:

        users.update_one(
            {
                "user_id":
                    int(user_id)
            },
            {
                "$inc": {

                    "suspicious_count":
                        1,
                },

                "$push": {

                    "security_flags": {

                        "$each": [
                            log
                        ],

                        "$slice":
                            -50,
                    }
                },
            },
        )

    except Exception as error:

        logger.error(
            "User security state update failed: %s",
            error,
        )

    return log


# ============================================================
# MARK SUSPICIOUS
# ============================================================

def mark_suspicious(
    user_id,
    reason,
    metadata=None,
):

    result = users.update_one(
        {
            "user_id":
                int(user_id)
        },
        {
            "$set": {

                "suspicious_activity":
                    True,
            }
        },
    )

    add_security_log(
        user_id,

        reason,

        severity=
            "high",

        metadata=
            metadata,
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# BLACKLIST USER
# ============================================================

def set_blacklist(
    user_id,
    status=True,
):

    result = users.update_one(
        {
            "user_id":
                int(user_id)
        },
        {
            "$set": {

                "blacklisted":
                    bool(status)
            }
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# BAN USER
# ============================================================

def set_banned(
    user_id,
    status=True,
):

    result = users.update_one(
        {
            "user_id":
                int(user_id)
        },
        {
            "$set": {

                "banned":
                    bool(status)
            }
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# GET USER SECURITY LOGS
# ============================================================

def get_security_logs(
    user_id,
    limit=50,
):

    return list(
        security_logs.find(
            {
                "user_id":
                    int(user_id)
            }
        )
        .sort(
            "created_at",
            DESCENDING,
        )
        .limit(
            int(limit)
        )
    )


# ============================================================
# CLEAR SUSPICIOUS FLAG
# ============================================================

def clear_suspicious(
    user_id,
):

    result = users.update_one(
        {
            "user_id":
                int(user_id)
        },
        {
            "$set": {

                "suspicious_activity":
                    False,

                "suspicious_count":
                    0,

                "security_flags":
                    [],
            }
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# TASK COMPLETION PROTECTION
# ============================================================

def has_completed_task(
    user_id,
    task_id,
):

    user = get_user(
        user_id
    )

    if not user:

        return False

    completed = user.get(
        "completed_tasks",
        [],
    )

    return (
        str(task_id)
        in [
            str(x)
            for x in completed
        ]
    )


# ============================================================
# MARK TASK COMPLETED
# ============================================================

def mark_task_completed(
    user_id,
    task_id,
):

    task_id = str(
        task_id
    )

    result = users.update_one(
        {
            "user_id":
                int(user_id),

            "completed_tasks":
                {
                    "$ne":
                        task_id
                },
        },
        {
            "$push": {

                "completed_tasks":
                    task_id,
            }
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# OFFER COMPLETION PROTECTION
# ============================================================

def has_completed_offer(
    user_id,
    offer_id,
):

    user = get_user(
        user_id
    )

    if not user:

        return False

    completed = user.get(
        "completed_offers",
        [],
    )

    return (
        str(offer_id)
        in [
            str(x)
            for x in completed
        ]
    )


# ============================================================
# MARK OFFER COMPLETED
# ============================================================

def mark_offer_completed(
    user_id,
    offer_id,
):

    offer_id = str(
        offer_id
    )

    result = users.update_one(
        {
            "user_id":
                int(user_id),

            "completed_offers":
                {
                    "$ne":
                        offer_id
                },
        },
        {
            "$push": {

                "completed_offers":
                    offer_id,
            },

            "$inc": {

                "offer_completed":
                    1,
            },
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# SHORTLINK COMPLETION PROTECTION
# ============================================================

def has_completed_shortlink(
    user_id,
    shortlink_id,
):

    user = get_user(
        user_id
    )

    if not user:

        return False

    completed = user.get(
        "completed_shortlinks",
        [],
    )

    return (
        str(shortlink_id)
        in [
            str(x)
            for x in completed
        ]
    )


# ============================================================
# MARK SHORTLINK COMPLETED
# ============================================================

def mark_shortlink_completed(
    user_id,
    shortlink_id,
):

    shortlink_id = str(
        shortlink_id
    )

    result = users.update_one(
        {
            "user_id":
                int(user_id),

            "completed_shortlinks":
                {
                    "$ne":
                        shortlink_id
                },
        },
        {
            "$push": {

                "completed_shortlinks":
                    shortlink_id,
            },

            "$inc": {

                "shortlink_completed":
                    1,
            },
        },
    )

    return (
        result.modified_count > 0
    )
# ============================================================
# REFERRAL PROTECTION
# ============================================================

def can_apply_referral(
    new_user_id,
    referrer_id,
):

    new_user = get_user(
        new_user_id
    )

    referrer = get_user(
        referrer_id
    )

    if not referrer:
        return False

    if int(new_user_id) == int(
        referrer_id
    ):
        return False

    if new_user.get(
        "referred_by"
    ) is not None:
        return False

    return True


# ============================================================
# APPLY REFERRAL
# ============================================================

def apply_referral(
    new_user_id,
    referrer_id,
    reward=0,
):

    new_user_id = int(
        new_user_id
    )

    referrer_id = int(
        referrer_id
    )

    if not can_apply_referral(
        new_user_id,
        referrer_id,
    ):
        return False

    now = int(
        time.time()
    )

    # Atomic referred_by protection
    result = users.update_one(
        {
            "user_id":
                new_user_id,

            "referred_by":
                None,
        },
        {
            "$set": {
                "referred_by":
                    referrer_id
            }
        },
    )

    if result.modified_count <= 0:
        return False

    update_data = {

        "$inc": {
            "referrals":
                1
        }
    }

    if reward > 0:

        update_data[
            "$inc"
        ]["referral_earn"] = reward

        update_data[
            "$inc"
        ]["balance"] = reward

        update_data[
            "$inc"
        ]["total_earned"] = reward

    users.update_one(
        {
            "user_id":
                referrer_id
        },
        update_data,
    )

    add_security_log(
        new_user_id,

        "Valid referral applied",

        severity="low",

        metadata={
            "referrer_id":
                referrer_id
        },
    )

    if reward > 0:

        record_transaction(
            user_id=referrer_id,

            transaction_type=
                "referral",

            amount=reward,

            source=
                "referral_reward",

            metadata={
                "referred_user":
                    new_user_id
            },
        )

        update_daily_statistic(
            field=
                "referral_earnings",

            amount=reward,
        )

    return True


# ============================================================
# BOT SETTINGS
# ============================================================

def get_bot_settings():

    settings = bot_settings.find_one(
        {
            "_id":
                "main"
        }
    )

    if settings:
        return settings

    now = int(
        time.time()
    )

    default_settings = {

        "_id":
            "main",

        "daily_bonus":
            5,

        "group_reward":
            20,

        "task_reward":
            10,

        "daily_task_limit":
            20,

        "spin_min":
            1,

        "spin_max":
            20,

        "spin_cooldown":
            60,

        "lucky_min":
            5,

        "lucky_max":
            30,

        "lucky_cooldown":
            60,

        "scratch_min":
            2,

        "scratch_max":
            15,

        "scratch_cooldown":
            60,

        "referral_reward":
            10,

        "vip_purchase_enabled":
            True,

        "updated_at":
            now,
    }

    try:

        bot_settings.insert_one(
            default_settings
        )

    except DuplicateKeyError:

        pass

    return bot_settings.find_one(
        {
            "_id":
                "main"
        }
    )


# ============================================================
# UPDATE BOT SETTINGS
# ============================================================

def update_bot_settings(
    data,
):

    if not data:
        return False

    data = dict(
        data
    )

    data[
        "updated_at"
    ] = int(
        time.time()
    )

    result = bot_settings.update_one(
        {
            "_id":
                "main"
        },
        {
            "$set":
                data
        },
        upsert=True,
    )

    return (
        result.modified_count > 0
        or result.upserted_id is not None
    )


# ============================================================
# DAILY STATISTICS
# ============================================================

def update_daily_statistic(
    field,
    amount=1,
    date=None,
):

    if date is None:

        date = time.strftime(
            "%Y-%m-%d"
        )

    allowed_fields = {

        "total_points_distributed",

        "daily_rewards",

        "referral_earnings",

        "wheel_spins",

        "lucky_boxes",

        "scratch_cards",

        "withdrawals",

        "pending_withdrawals",

        "new_users",

        "active_users",
    }

    if field not in allowed_fields:
        return False

    result = daily_statistics.update_one(
        {
            "date":
                date
        },
        {
            "$inc": {
                field:
                    int(amount)
            },

            "$setOnInsert": {
                "date":
                    date
            },
        },
        upsert=True,
    )

    return (
        result.modified_count > 0
        or result.upserted_id is not None
    )


# ============================================================
# GET DAILY STATISTICS
# ============================================================

def get_daily_statistics(
    days=30,
):

    return list(
        daily_statistics.find(
            {}
        )
        .sort(
            "date",
            DESCENDING,
        )
        .limit(
            int(days)
        )
    )


# ============================================================
# GET PENDING WITHDRAWALS COUNT
# ============================================================

def pending_withdrawals_count():

    return withdrawals.count_documents(
        {
            "status":
                "pending"
        }
    )


# ============================================================
# GET TOTAL WITHDRAWALS
# ============================================================

def total_withdrawals():

    result = list(
        withdrawals.aggregate(
            [

                {
                    "$match": {
                        "status":
                            "approved"
                    }
                },

                {
                    "$group": {

                        "_id":
                            None,

                        "total": {
                            "$sum":
                                "$amount"
                        },
                    }
                },
            ]
        )
    )

    if not result:
        return 0

    return result[0].get(
        "total",
        0,
    )


# ============================================================
# TOTAL POINTS DISTRIBUTED
# ============================================================

def total_points_distributed():

    result = list(
        transactions.aggregate(
            [

                {
                    "$match": {

                        "type": {
                            "$in": [
                                "credit",
                                "bonus_credit",
                                "referral",
                            ]
                        },

                        "status":
                            "completed",
                    }
                },

                {
                    "$group": {

                        "_id":
                            None,

                        "total": {
                            "$sum":
                                "$amount"
                        },
                    }
                },
            ]
        )
    )

    if not result:
        return 0

    return result[0].get(
        "total",
        0,
    )


# ============================================================
# DATABASE HEALTH CHECK
# ============================================================

def database_health():

    try:

        client.admin.command(
            "ping"
        )

        return True

    except Exception as error:

        logger.error(
            "MongoDB health check failed: %s",
            error,
        )

        return False


# ============================================================
# INITIALIZE DATABASE
# ============================================================

try:

    ensure_indexes()

    get_bot_settings()

    logger.info(
        "MongoDB database initialized successfully."
    )

except Exception as error:

    logger.error(
        "MongoDB initialization error: %s",
        error,
    )
# ============================================================
# FUTURE USER HELPERS
# ============================================================

def get_user_by_username(
    username,
):
    """
    Find a user by Telegram username.
    Accepts username with or without @.
    """

    if not username:
        return None

    username = str(
        username
    ).strip().lstrip("@")

    if not username:
        return None

    return users.find_one(
        {
            "username":
                username
        }
    )


# ============================================================
# USER EXISTS
# ============================================================

def user_exists(
    user_id,
):
    """
    Check whether a user exists.
    """

    return (
        users.find_one(
            {
                "user_id":
                    int(user_id)
            },
            {
                "_id": 1
            },
        )
        is not None
    )


# ============================================================
# COUNT USERS
# ============================================================

def count_users():
    """
    Return total registered users.
    """

    return users.count_documents({})


# ============================================================
# COUNT ACTIVE USERS
# ============================================================

def count_active_users(
    since_seconds=86400,
):
    """
    Count users active within the given period.

    Default:
        86400 seconds = 24 hours
    """

    now = int(
        time.time()
    )

    since = (
        now
        - int(since_seconds)
    )

    return users.count_documents(
        {
            "last_active": {
                "$gte": since
            }
        }
    )


# ============================================================
# COUNT BANNED USERS
# ============================================================

def count_banned_users():
    """
    Return total banned users.
    """

    return users.count_documents(
        {
            "banned": True
        }
    )


# ============================================================
# COUNT BLACKLISTED USERS
# ============================================================

def count_blacklisted_users():
    """
    Return total blacklisted users.
    """

    return users.count_documents(
        {
            "blacklisted": True
        }
    )


# ============================================================
# GET USERS
# ============================================================

def get_users(
    limit=100,
):
    """
    Return users ordered by newest activity.
    """

    limit = max(
        1,
        int(limit),
    )

    return list(
        users.find({})
        .sort(
            "last_active",
            DESCENDING,
        )
        .limit(limit)
    )


# ============================================================
# SEARCH USERS
# ============================================================

def search_users(
    query,
    limit=20,
):
    """
    Search users by:
        - user_id
        - username
        - first_name
        - last_name
    """

    if query is None:
        return []

    query = str(
        query
    ).strip()

    if not query:
        return []

    limit = max(
        1,
        int(limit),
    )

    conditions = []

    if query.isdigit():

        conditions.append(
            {
                "user_id":
                    int(query)
            }
        )

    escaped = query.replace(
        "\\",
        "\\\\",
    ).replace(
        ".",
        "\\.",
    ).replace(
        "*",
        "\\*",
    ).replace(
        "+",
        "\\+",
    ).replace(
        "?",
        "\\?",
    ).replace(
        "[",
        "\\[",
    ).replace(
        "]",
        "\\]",
    ).replace(
        "(",
        "\\(",
    ).replace(
        ")",
        "\\)",
    )

    conditions.extend(
        [
            {
                "username": {
                    "$regex":
                        escaped,
                    "$options":
                        "i",
                }
            },
            {
                "first_name": {
                    "$regex":
                        escaped,
                    "$options":
                        "i",
                }
            },
            {
                "last_name": {
                    "$regex":
                        escaped,
                    "$options":
                        "i",
                }
            },
        ]
    )

    return list(
        users.find(
            {
                "$or":
                    conditions
            }
        )
        .sort(
            "last_active",
            DESCENDING,
        )
        .limit(limit)
    )


# ============================================================
# RESET DAILY TASK COUNT
# ============================================================

def reset_daily_task_count(
    user_id,
):
    """
    Reset the user's daily task counter.
    """

    result = users.update_one(
        {
            "user_id":
                int(user_id)
        },
        {
            "$set": {
                "daily_task_count":
                    0,

                "last_task_reset":
                    int(time.time()),
            }
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# RESET EXPIRED DAILY TASKS
# ============================================================

def reset_expired_daily_tasks():
    """
    Reset daily task counters for users
    whose last reset was before today.
    """

    now = int(
        time.time()
    )

    day_start = (
        now
        - (
            now
            % 86400
        )
    )

    result = users.update_many(
        {
            "$or": [
                {
                    "last_task_reset": {
                        "$lt":
                            day_start
                    }
                },
                {
                    "last_task_reset": {
                        "$exists":
                            False
                    }
                },
            ]
        },
        {
            "$set": {
                "daily_task_count":
                    0,

                "last_task_reset":
                    now,
            }
        },
    )

    return result.modified_count


# ============================================================
# USER SUMMARY
# ============================================================

def get_user_summary(
    user_id,
):
    """
    Return a compact user summary
    for profile/admin/statistics screens.
    """

    user = get_user(
        user_id,
        create=False,
    )

    if not user:
        return None

    return {
        "user_id":
            int(
                user.get(
                    "user_id",
                    user_id,
                )
            ),

        "username":
            user.get(
                "username",
                "",
            ),

        "balance":
            int(
                user.get(
                    "balance",
                    0,
                )
            ),

        "bonus_balance":
            int(
                user.get(
                    "bonus_balance",
                    0,
                )
            ),

        "total_earned":
            int(
                user.get(
                    "total_earned",
                    0,
                )
            ),

        "total_spent":
            int(
                user.get(
                    "total_spent",
                    0,
                )
            ),

        "xp":
            int(
                user.get(
                    "xp",
                    0,
                )
            ),

        "level":
            int(
                user.get(
                    "level",
                    1,
                )
            ),

        "daily_streak":
            int(
                user.get(
                    "daily_streak",
                    0,
                )
            ),

        "referrals":
            int(
                user.get(
                    "referrals",
                    0,
                )
            ),

        "energy":
            int(
                user.get(
                    "energy",
                    0,
                )
            ),

        "premium":
            bool(
                user.get(
                    "premium",
                    False,
                )
            ),

        "vip":
            bool(
                user.get(
                    "vip",
                    False,
                )
            ),

        "banned":
            bool(
                user.get(
                    "banned",
                    False,
                )
            ),

        "blacklisted":
            bool(
                user.get(
                    "blacklisted",
                    False,
                )
            ),
}
# ============================================================
# USER ACTIVITY HELPERS
# ============================================================

def update_last_active(
    user_id,
):
    """
    Update the user's latest activity timestamp.
    """

    now = int(
        time.time()
    )

    result = users.update_one(
        {
            "user_id":
                int(user_id)
        },
        {
            "$set": {
                "last_active":
                    now,
            }
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# UPDATE LOGIN
# ============================================================

def update_last_login(
    user_id,
):
    """
    Update the user's latest login timestamp.
    """

    now = int(
        time.time()
    )

    result = users.update_one(
        {
            "user_id":
                int(user_id)
        },
        {
            "$set": {
                "last_login":
                    now,
                "last_active":
                    now,
            }
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# UPDATE USERNAME
# ============================================================

def update_username(
    user_id,
    username,
):
    """
    Safely update Telegram username.
    """

    username = (
        str(username or "")
        .strip()
        .lstrip("@")
    )

    result = users.update_one(
        {
            "user_id":
                int(user_id)
        },
        {
            "$set": {
                "username":
                    username,
                "last_active":
                    int(time.time()),
            }
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# UPDATE USER PROFILE
# ============================================================

def update_user_profile(
    user_id,
    username=None,
    first_name=None,
    last_name=None,
):
    """
    Update available Telegram profile fields.
    Fields passed as None are left unchanged.
    """

    update_data = {}

    if username is not None:

        update_data[
            "username"
        ] = (
            str(username)
            .strip()
            .lstrip("@")
        )

    if first_name is not None:

        update_data[
            "first_name"
        ] = str(
            first_name
        ).strip()

    if last_name is not None:

        update_data[
            "last_name"
        ] = str(
            last_name
        ).strip()

    if not update_data:
        return False

    update_data[
        "last_active"
    ] = int(
        time.time()
    )

    result = users.update_one(
        {
            "user_id":
                int(user_id)
        },
        {
            "$set":
                update_data
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# GET USER ACTIVITY
# ============================================================

def get_user_activity(
    user_id,
    limit=None,
):
    """
    Return the user's activity list.
    """

    if limit is None:

        limit = ACTIVITY_LIMIT

    limit = max(
        1,
        int(limit),
    )

    user = get_user(
        user_id,
        create=False,
    )

    if not user:
        return []

    activity = user.get(
        "activity",
        [],
    )

    if not isinstance(
        activity,
        list,
    ):
        return []

    return activity[
        -limit:
    ]


# ============================================================
# CLEAR USER ACTIVITY
# ============================================================

def clear_user_activity(
    user_id,
):
    """
    Remove stored activity history.
    """

    result = users.update_one(
        {
            "user_id":
                int(user_id)
        },
        {
            "$set": {
                "activity":
                    [],
            }
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# GET RECENT USERS
# ============================================================

def get_recent_users(
    limit=20,
):
    """
    Return recently active users.
    """

    limit = max(
        1,
        int(limit),
    )

    return list(
        users.find({})
        .sort(
            "last_active",
            DESCENDING,
        )
        .limit(limit)
    )


# ============================================================
# GET NEW USERS
# ============================================================

def get_new_users(
    limit=20,
):
    """
    Return recently registered users.
    """

    limit = max(
        1,
        int(limit),
    )

    return list(
        users.find({})
        .sort(
            "created_at",
            DESCENDING,
        )
        .limit(limit)
    )
# ============================================================
# USER REWARD / ECONOMY HELPERS
# ============================================================

def add_premium_balance(
    user_id,
    amount,
):
    amount = int(amount)

    if amount <= 0:
        return False

    result = users.update_one(
        {
            "user_id": int(user_id),
            "banned": {"$ne": True},
            "blacklisted": {"$ne": True},
        },
        {
            "$inc": {
                "premium_balance": amount,
            }
        },
    )

    return result.modified_count > 0


# ============================================================
# REMOVE BONUS BALANCE
# ============================================================

def convert_bonus_to_balance(user_id, amount=None):
    """Move promotional bonus points into the main balance atomically.

    Bonus points remain non-withdrawable until explicitly converted; the
    conversion is recorded as an internal transfer and does not increase
    total_earned a second time.
    """
    user_id = int(user_id)
    user = get_user(user_id, create=False)
    if not user or user.get("banned", False) or user.get("blacklisted", False):
        return 0
    available = int(user.get("bonus_balance", 0) or 0)
    if available <= 0:
        return 0
    if amount is None:
        amount = available
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return 0
    if amount <= 0 or amount > available:
        return 0
    result = users.update_one(
        {"user_id": user_id, "bonus_balance": {"$gte": amount}},
        {"$inc": {"bonus_balance": -amount, "balance": amount}},
    )
    if result.modified_count != 1:
        return 0
    record_transaction(
        user_id=user_id,
        transaction_type="bonus_to_balance",
        amount=amount,
        source="bonus_conversion",
    )
    add_activity(user_id, "🎁 Bonus converted to balance", amount)
    return amount


def remove_bonus(
    user_id,
    amount,
):
    amount = int(amount)

    if amount <= 0:
        return 0

    result = users.update_one(
        {
            "user_id": int(user_id),
            "bonus_balance": {
                "$gte": amount,
            },
        },
        {
            "$inc": {
                "bonus_balance": -amount,
            }
        },
    )

    if result.modified_count <= 0:
        return 0

    return amount


# ============================================================
# GET BALANCE DATA
# ============================================================

def get_balance_data(
    user_id,
):
    user = get_user(
        user_id,
        create=False,
    )

    if not user:
        return None

    return {
        "balance": int(
            user.get(
                "balance",
                0,
            )
        ),
        "bonus_balance": int(
            user.get(
                "bonus_balance",
                0,
            )
        ),
        "premium_balance": int(
            user.get(
                "premium_balance",
                0,
            )
        ),
        "total_earned": int(
            user.get(
                "total_earned",
                0,
            )
        ),
        "total_spent": int(
            user.get(
                "total_spent",
                0,
            )
        ),
    }


# ============================================================
# GET REWARD SUMMARY
# ============================================================

def get_reward_summary(
    user_id,
):
    user = get_user(
        user_id,
        create=False,
    )

    if not user:
        return None

    return {
        "daily_streak": int(
            user.get(
                "daily_streak",
                0,
            )
        ),
        "daily_task_count": int(
            user.get(
                "daily_task_count",
                0,
            )
        ),
        "offer_completed": int(
            user.get(
                "offer_completed",
                0,
            )
        ),
        "shortlink_completed": int(
            user.get(
                "shortlink_completed",
                0,
            )
        ),
        "total_earned": int(
            user.get(
                "total_earned",
                0,
            )
        ),
        "xp": int(
            user.get(
                "xp",
                0,
            )
        ),
        "level": int(
            user.get(
                "level",
                1,
            )
        ),
    }


# ============================================================
# SAFE REWARD
# ============================================================

def give_reward(
    user_id,
    amount,
    source="reward",
):
    amount = int(amount)

    if amount <= 0:
        return False

    user = get_user(
        user_id,
        create=False,
    )

    if not user:
        return False

    if user.get(
        "banned",
        False,
    ):
        return False

    if user.get(
        "blacklisted",
        False,
    ):
        return False

    success = add_balance(
        user_id,
        amount,
    )

    if not success:
        return False

    add_activity(
        user_id,
        f"🎁 {source}",
        amount,
    )

    return True


# ============================================================
# SAFE XP REWARD
# ============================================================

def give_xp_reward(
    user_id,
    amount,
):
    amount = int(amount)

    if amount <= 0:
        return None

    user = get_user(
        user_id,
        create=False,
    )

    if not user:
        return None

    if user.get(
        "banned",
        False,
    ):
        return None

    if user.get(
        "blacklisted",
        False,
    ):
        return None

    return add_xp(
        user_id,
        amount,
    )
# ============================================================
# TASK COMPLETION PROTECTION
# ============================================================

def has_completed_task(
    user_id,
    task_id,
):
    user = get_user(user_id)

    completed = user.get(
        "completed_tasks",
        [],
    )

    return str(task_id) in [
        str(x)
        for x in completed
    ]


# ============================================================
# MARK TASK COMPLETED
# ============================================================

def mark_task_completed(
    user_id,
    task_id,
):
    task_id = str(task_id)

    result = users.update_one(
        {
            "user_id":
                int(user_id),

            "completed_tasks":
                {
                    "$ne":
                        task_id
                },
        },
        {
            "$push": {
                "completed_tasks":
                    task_id
            }
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# OFFER COMPLETION PROTECTION
# ============================================================

def has_completed_offer(
    user_id,
    offer_id,
):
    user = get_user(user_id)

    completed = user.get(
        "completed_offers",
        [],
    )

    return str(offer_id) in [
        str(x)
        for x in completed
    ]


# ============================================================
# MARK OFFER COMPLETED
# ============================================================

def mark_offer_completed(
    user_id,
    offer_id,
):
    offer_id = str(offer_id)

    result = users.update_one(
        {
            "user_id":
                int(user_id),

            "completed_offers":
                {
                    "$ne":
                        offer_id
                },
        },
        {
            "$push": {
                "completed_offers":
                    offer_id
            },

            "$inc": {
                "offer_completed":
                    1
            },
        },
    )

    return (
        result.modified_count > 0
    )


# ============================================================
# SHORTLINK COMPLETION PROTECTION
# ============================================================

def has_completed_shortlink(
    user_id,
    shortlink_id,
):
    user = get_user(user_id)

    completed = user.get(
        "completed_shortlinks",
        [],
    )

    return str(shortlink_id) in [
        str(x)
        for x in completed
    ]


# ============================================================
# MARK SHORTLINK COMPLETED
# ============================================================

def mark_shortlink_completed(
    user_id,
    shortlink_id,
):
    shortlink_id = str(
        shortlink_id
    )

    result = users.update_one(
        {
            "user_id":
                int(user_id),

            "completed_shortlinks":
                {
                    "$ne":
                        shortlink_id
                },
        },
        {
            "$push": {
                "completed_shortlinks":
                    shortlink_id
            },

            "$inc": {
                "shortlink_completed":
                    1
            },
        },
    )

    return (
        result.modified_count > 0
               )
    # ==================================================
# REFERRAL PROTECTION
# ==================================================

def can_apply_referral(
    new_user_id,
    referrer_id,
):

    new_user = get_user(
        new_user_id
    )

    referrer = get_user(
        referrer_id
    )

    if not referrer:
        return False

    if int(new_user_id) == int(
        referrer_id
    ):
        return False

    if new_user.get(
        "referred_by"
    ) is not None:
        return False

    return True


# ==================================================
# APPLY REFERRAL
# ==================================================

def apply_referral(
    new_user_id,
    referrer_id,
    reward=0,
):

    new_user_id = int(
        new_user_id
    )

    referrer_id = int(
        referrer_id
    )

    if not can_apply_referral(
        new_user_id,
        referrer_id,
    ):
        return False

    now = int(time.time())

    # Atomic referred_by protection
    result = users.update_one(
        {
            "user_id":
                new_user_id,

            "referred_by":
                None,
        },
        {
            "$set": {
                "referred_by":
                    referrer_id
            }
        },
    )

    if result.modified_count <= 0:
        return False

    update_data = {

        "$inc": {
            "referrals":
                1
        }

    }

    if reward > 0:

        update_data[
            "$inc"
        ]["referral_earn"] = reward

        update_data[
            "$inc"
        ]["balance"] = reward

        update_data[
            "$inc"
        ]["total_earned"] = reward

    users.update_one(
        {
            "user_id":
                referrer_id
        },
        update_data,
    )

    add_security_log(
        new_user_id,
        "Valid referral applied",
        severity="low",
        metadata={
            "referrer_id":
                referrer_id
        },
    )

    if reward > 0:

        record_transaction(
            user_id=referrer_id,
            transaction_type="referral",
            amount=reward,
            source="referral_reward",
            metadata={
                "referred_user":
                    new_user_id
            },
        )

    return True


# ==================================================
# BOT SETTINGS
# ==================================================

def get_bot_settings():

    settings = bot_settings.find_one(
        {
            "_id":
                "main"
        }
    )

    if settings:
        return settings

    now = int(time.time())

    default_settings = {

        "_id": "main",

        "daily_bonus": 5,
        "group_reward": 20,

        "task_reward": 10,
        "daily_task_limit": 20,

        "spin_min": 1,
        "spin_max": 20,
        "spin_cooldown": 60,

        "lucky_min": 5,
        "lucky_max": 30,
        "lucky_cooldown": 60,

        "scratch_min": 2,
        "scratch_max": 15,
        "scratch_cooldown": 60,

        "referral_reward": 10,

        "updated_at": now,
    }

    try:

        bot_settings.insert_one(
            default_settings
        )

    except DuplicateKeyError:

        pass

    return bot_settings.find_one(
        {
            "_id":
                "main"
        }
    )


# ==================================================
# UPDATE BOT SETTINGS
# ==================================================

def update_bot_settings(
    data,
):

    if not data:
        return False

    data = dict(data)

    data["updated_at"] = int(
        time.time()
    )

    result = bot_settings.update_one(
        {
            "_id":
                "main"
        },
        {
            "$set":
                data
        },
        upsert=True,
    )

    return (
        result.modified_count > 0
        or result.upserted_id is not None
    )


# ==================================================
# DAILY STATISTICS
# ==================================================

def update_daily_statistic(
    field,
    amount=1,
    date=None,
):

    if date is None:

        date = time.strftime(
            "%Y-%m-%d"
        )

    allowed_fields = {

        "total_points_distributed",
        "daily_rewards",
        "referral_earnings",

        "wheel_spins",
        "lucky_boxes",
        "scratch_cards",

        "withdrawals",
        "pending_withdrawals",

        "new_users",
        "active_users",
    }

    if field not in allowed_fields:
        return False

    result = daily_statistics.update_one(
        {
            "date":
                date
        },
        {
            "$inc": {
                field:
                    int(amount)
            },

            "$setOnInsert": {
                "date":
                    date
            },
        },
        upsert=True,
    )

    return (
        result.modified_count > 0
        or result.upserted_id is not None
    )


# ==================================================
# GET DAILY STATISTICS
# ==================================================

def get_daily_statistics(
    days=30,
):

    return list(
        daily_statistics.find({})
        .sort(
            "date",
            DESCENDING,
        )
        .limit(
            int(days)
        )
    )


# ==================================================
# GET PENDING WITHDRAWALS COUNT
# ==================================================

def pending_withdrawals_count():

    return withdrawals.count_documents(
        {
            "status":
                "pending"
        }
    )


# ==================================================
# GET TOTAL WITHDRAWALS
# ==================================================

def total_withdrawals():

    result = list(
        withdrawals.aggregate(
            [
                {
                    "$match": {
                        "status":
                            "approved"
                    }
                },

                {
                    "$group": {
                        "_id":
                            None,

                        "total": {
                            "$sum":
                                "$amount"
                        },
                    }
                },
            ]
        )
    )

    if not result:
        return 0

    return result[0].get(
        "total",
        0,
    )


# ==================================================
# TOTAL POINTS DISTRIBUTED
# ==================================================

def total_points_distributed():

    result = list(
        transactions.aggregate(
            [
                {
                    "$match": {

                        "type": {
                            "$in": [
                                "credit",
                                "bonus_credit",
                                "referral",
                            ]
                        },

                        "status":
                            "completed",
                    }
                },

                {
                    "$group": {

                        "_id":
                            None,

                        "total": {
                            "$sum":
                                "$amount"
                        },
                    }
                },
            ]
        )
    )

    if not result:
        return 0

    return result[0].get(
        "total",
        0,
    )


# ==================================================
# DATABASE HEALTH CHECK
# ==================================================

def database_health():

    try:

        client.admin.command(
            "ping"
        )

        return True

    except Exception as error:

        logger.error(
            "MongoDB health check failed: %s",
            error,
        )

        return False
        
# ============================================================
# PREMIUM / VIP MEMBERSHIP SYSTEM
# ============================================================

def _membership_now():
    return int(time.time())


def get_premium_status(user_id):
    """
    Return current Premium status.
    """
    user = get_user(
        user_id,
        create=False,
    )

    if not user:
        return {
            "active": False,
            "expire": 0,
        }

    expire = int(
        user.get(
            "premium_expire",
            0,
        ) or 0
    )

    active = bool(
        user.get(
            "premium",
            False,
        )
    )

    if expire > 0 and expire <= _membership_now():
        active = False

    return {
        "active": active,
        "expire": expire,
    }


def activate_premium(
    user_id,
    days=30,
):
    """
    Activate or extend Premium.
    """

    user_id = int(user_id)
    days = int(days)

    if days <= 0:
        return False

    user = get_user(
        user_id,
        create=False,
    )

    if not user:
        return False

    if user.get("banned", False):
        return False

    if user.get("blacklisted", False):
        return False

    now = _membership_now()

    current_expire = int(
        user.get(
            "premium_expire",
            0,
        ) or 0
    )

    if current_expire > now:
        new_expire = (
            current_expire
            + days * 86400
        )
    else:
        new_expire = (
            now
            + days * 86400
        )

    result = users.update_one(
        {
            "user_id": user_id,
        },
        {
            "$set": {
                "premium": True,
                "premium_expire": new_expire,
            }
        },
    )

    return (
        result.modified_count > 0
        or result.matched_count > 0
    )


def remove_premium(user_id):
    """
    Immediately remove Premium.
    """

    result = users.update_one(
        {
            "user_id": int(user_id),
        },
        {
            "$set": {
                "premium": False,
                "premium_expire": 0,
            }
        },
    )

    return (
        result.modified_count > 0
        or result.matched_count > 0
    )


def get_vip_status(user_id):
    """
    Return current VIP status.
    """

    user = get_user(
        user_id,
        create=False,
    )

    if not user:
        return {
            "active": False,
            "level": 0,
            "expire": 0,
            "daily_multiplier": 1.0,
            "extra_spins": 0,
        }

    expire = int(
        user.get(
            "vip_expire",
            0,
        ) or 0
    )

    active = bool(
        user.get(
            "vip",
            False,
        )
    )

    level = int(
        user.get(
            "vip_level",
            0,
        ) or 0
    )

    multiplier = float(
        user.get(
            "vip_multiplier",
            1.0,
        ) or 1.0
    )

    extra_spins = int(
        user.get(
            "vip_extra_spins",
            0,
        ) or 0
    )

    if expire > 0 and expire <= _membership_now():
        active = False

    if not active:
        level = 0
        multiplier = 1.0
        extra_spins = 0

    return {
        "active": active,
        "level": level,
        "expire": expire,
        "daily_multiplier": multiplier,
        "extra_spins": extra_spins,
    }


def activate_vip(
    user_id,
    level=1,
    days=30,
):
    """
    Activate or extend VIP.
    """

    user_id = int(user_id)
    level = int(level)
    days = int(days)

    vip_benefits = {
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
            "extra_spins": 2,
        },
        4: {
            "daily_multiplier": 1.75,
            "extra_spins": 3,
        },
        5: {
            "daily_multiplier": 2.00,
            "extra_spins": 4,
        },
    }

    if level not in vip_benefits:
        return False

    if days <= 0:
        return False

    user = get_user(
        user_id,
        create=False,
    )

    if not user:
        return False

    if user.get("banned", False):
        return False

    if user.get("blacklisted", False):
        return False

    now = _membership_now()

    current_expire = int(
        user.get(
            "vip_expire",
            0,
        ) or 0
    )

    if current_expire > now:
        new_expire = (
            current_expire
            + days * 86400
        )
    else:
        new_expire = (
            now
            + days * 86400
        )

    benefits = vip_benefits[level]

    result = users.update_one(
        {
            "user_id": user_id,
        },
        {
            "$set": {
                "vip": True,
                "vip_level": level,
                "vip_expire": new_expire,
                "vip_multiplier": benefits[
                    "daily_multiplier"
                ],
                "vip_extra_spins": benefits[
                    "extra_spins"
                ],
            }
        },
    )

    return (
        result.modified_count > 0
        or result.matched_count > 0
    )


def remove_vip(user_id):
    """
    Immediately remove VIP.
    """

    result = users.update_one(
        {
            "user_id": int(user_id),
        },
        {
            "$set": {
                "vip": False,
                "vip_level": 0,
                "vip_expire": 0,
                "vip_multiplier": 1.0,
                "vip_extra_spins": 0,
            }
        },
    )

    return (
        result.modified_count > 0
        or result.matched_count > 0
    )


def get_membership_status(user_id):
    """
    Return combined Premium + VIP status.
    """

    user = get_user(
        user_id,
        create=False,
    )

    if not user:
        return {
            "premium": False,
            "premium_expire": 0,
            "vip": False,
            "vip_level": 0,
            "vip_expire": 0,
        }

    now = _membership_now()

    premium_expire = int(
        user.get(
            "premium_expire",
            0,
        ) or 0
    )

    vip_expire = int(
        user.get(
            "vip_expire",
            0,
        ) or 0
    )

    premium = bool(
        user.get(
            "premium",
            False,
        )
    )

    vip = bool(
        user.get(
            "vip",
            False,
        )
    )

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
            int(
                user.get(
                    "vip_level",
                    0,
                ) or 0
            )
            if vip
            else 0
        ),
        "vip_expire": vip_expire,
    }


def get_membership_multiplier(user_id):
    """
    Return effective Premium/VIP multiplier.

    VIP takes priority over Premium.
    """

    vip_status = get_vip_status(
        user_id
    )

    if vip_status.get("active"):
        return float(
            vip_status.get(
                "daily_multiplier",
                1.0,
            )
        )

    premium_status = get_premium_status(
        user_id
    )

    if premium_status.get("active"):
        return 1.10

    return 1.0


def get_extra_spins(user_id):
    """
    Return VIP extra spins.
    """

    status = get_vip_status(
        user_id
    )

    if not status.get("active"):
        return 0

    return max(
        0,
        int(
            status.get(
                "extra_spins",
                0,
            )
        ),
    )
# ============================================================
# VIP PURCHASE SYSTEM SETTING
# ============================================================

def is_vip_purchase_enabled():
    """
    Return True when users are allowed to purchase VIP.

    The setting is stored in the shared ``bot_settings`` document
    whose MongoDB _id is ``main``.
    """
    try:
        settings = get_bot_settings() or {}
        return bool(settings.get("vip_purchase_enabled", True))
    except Exception:
        logger.exception("Failed to read VIP purchase setting")
        # Fail CLOSED on a database read error so a temporary DB problem
        # can never accidentally enable paid purchases.
        return False


def set_vip_purchase_enabled(enabled):
    """
    Enable/disable paid VIP purchases and persist the setting.
    """
    try:
        return bool(update_bot_settings({
            "vip_purchase_enabled": bool(enabled),
        }))
    except Exception:
        logger.exception("Failed to save VIP purchase setting")
        return False
# ==================================================
# INITIALIZE DATABASE
# ==================================================

try:

    ensure_indexes()

    get_bot_settings()

    logger.info(
        "MongoDB database initialized successfully."
    )

except Exception as error:

    logger.error(
        "MongoDB initialization error: %s",
        error,
    )
    
