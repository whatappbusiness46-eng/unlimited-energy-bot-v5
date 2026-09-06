import time
import logging

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import ContextTypes

from config import ADMIN_ID

from provider_integrations import (
    get_provider_offers,
    set_provider_offer_enabled,
    delete_provider_offer,
    shorten_with_provider,
)

from payments import pending as pending_payments, get_payment, approve_payment, reject_payment
from premium import grant_premium, revoke_premium
from vip import grant_vip, remove_vip, is_valid_vip_level

from tasks import (
    get_tasks, register_task, set_task_enabled, delete_task,
)
from referral import get_milestones, set_milestone, delete_milestone

from shortlinks import (
    get_shortlinks,
    register_shortlink,
    set_shortlink_enabled,
    delete_shortlink,
)

from database import (
    get_user,
    update_user,
    add_balance,
    remove_balance,
    add_bonus,
    remove_bonus,
    users,
    db,
    get_withdrawals,
    approve_withdrawal,
    reject_withdrawal,
    pending_withdrawals_count,
    total_withdrawals,
    is_vip_purchase_enabled,
    set_vip_purchase_enabled,
)


logger = logging.getLogger(__name__)


# ==================================================
# ADMIN CHECK
# ==================================================

def is_admin(user_id):
    try:
        return int(user_id) == int(ADMIN_ID)
    except (TypeError, ValueError):
        return False


def admin_only(user_id):
    return is_admin(user_id)

# ==================================================
# COMMON KEYBOARDS
# ==================================================

def admin_back():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔙 Admin Panel",
                    callback_data="admin",
                )
            ]
        ]
    )


def admin_menu():
    vip_status = (
    "🟢 ON"
    if is_vip_purchase_enabled()
    else "🔴 OFF"
    )
    keyboard = [

        [
            InlineKeyboardButton(
                "👥 Users",
                callback_data="admin_users",
            ),
            InlineKeyboardButton(
                "📊 Statistics",
                callback_data="admin_stats",
            ),
        ],

        [
            InlineKeyboardButton(
                "💰 Manage Balance",
                callback_data="admin_balance",
            )
        ],

        [
            InlineKeyboardButton(
                "🎁 Manage Rewards",
                callback_data="admin_rewards",
            )
        ],

        [
            InlineKeyboardButton(
                "🎯 Manage Tasks",
                callback_data="admin_tasks",
            )
        ],

        [
            InlineKeyboardButton(
                "🎡 Wheel Settings",
                callback_data="admin_wheel",
            )
        ],

        [
            InlineKeyboardButton(
                "🎁 Lucky Box",
                callback_data="admin_lucky",
            )
        ],

        [
            InlineKeyboardButton(
                "👥 Referral Settings",
                callback_data="admin_referral",
            )
        ],
        [
            InlineKeyboardButton(
                "🔗 Shortlinks",
                callback_data="admin_shortlinks",
            )
        ],
        [
            InlineKeyboardButton(
                "🎁 CPAGrip Offers",
                callback_data="admin_cpagrip_offers",
            )
        ],

        [
            InlineKeyboardButton(
                "💳 Membership Payments",
                callback_data="admin_membership_payments",
            )
        ],

        [
            InlineKeyboardButton(
                "💸 Withdrawals",
                callback_data="admin_withdrawals",
            )
        ],

        [
            InlineKeyboardButton(
                "🔒 Ban / Unban",
                callback_data="admin_ban",
            )
        ],

        [
            InlineKeyboardButton(
                "📢 Broadcast",
                callback_data="admin_broadcast",
            )
        ],

        [
            InlineKeyboardButton(
                "⚙️ Bot Settings",
                callback_data="admin_settings",
            )
        ],
            [
            InlineKeyboardButton(
                f"💎 VIP Purchase: {vip_status}",
                callback_data="admin_vip_toggle",
            )
        ],

        [
            InlineKeyboardButton(
                "🏠 Home",
                callback_data="home",
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def user_info_keyboard(user_id):

    return InlineKeyboardMarkup(
        [

            [
                InlineKeyboardButton(
                    "💰 Add Balance",
                    callback_data=f"admin_add_{user_id}",
                )
            ],

            [
                InlineKeyboardButton(
                    "➖ Remove Balance",
                    callback_data=f"admin_remove_{user_id}",
                ),
                InlineKeyboardButton(
                    "🎁 Add Bonus",
                    callback_data=f"admin_bonus_add_{user_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🎁 Remove Bonus",
                    callback_data=f"admin_bonus_remove_{user_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "👑 Premium ON",
                    callback_data=f"admin_premium_on_{user_id}",
                ),
                InlineKeyboardButton(
                    "❌ Premium OFF",
                    callback_data=f"admin_premium_off_{user_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "💎 Set VIP",
                    callback_data=f"admin_vip_set_{user_id}",
                ),
                InlineKeyboardButton(
                    "🚫 VIP OFF",
                    callback_data=f"admin_vip_off_{user_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔒 Ban / Unban",
                    callback_data=f"admin_toggleban_{user_id}",
                )
            ],

            [
                InlineKeyboardButton(
                    "🔙 Users",
                    callback_data="admin_users",
                )
            ],

        ]
    )

# ==================================================
# ADMIN PANEL
# ==================================================

async def admin_panel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.effective_user:
        return

    user_id = update.effective_user.id

    if not admin_only(user_id):

        if update.callback_query:

            await update.callback_query.answer(
                "🚫 Admin only.",
                show_alert=True,
            )

        elif update.message:

            await update.message.reply_text(
                "🚫 You are not an Admin."
            )

        return

    text = (
        "🛡️ **ADMIN CONTROL PANEL**\n\n"
        "Welcome Admin.\n\n"
        "Choose an option below:"
    )

    if update.callback_query:

        query = update.callback_query

        await query.answer()

        await query.edit_message_text(
            text,
            reply_markup=admin_menu(),
            parse_mode="Markdown",
        )

    elif update.message:

        await update.message.reply_text(
            text,
            reply_markup=admin_menu(),
            parse_mode="Markdown",
        )


# ==================================================
# USERS
# ==================================================

async def admin_users(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    if not admin_only(query.from_user.id):

        await query.answer(
            "🚫 Admin only.",
            show_alert=True,
        )

        return

    await query.answer()

    total = users.count_documents({})

    active_24h = users.count_documents(
        {
            "last_login": {
                "$gte": int(time.time()) - 86400
            }
        }
    )

    banned = users.count_documents(
        {
            "banned": True
        }
    )

    await query.edit_message_text(

        "👥 **USER MANAGEMENT**\n\n"

        f"👥 Total Users: {total}\n"
        f"🟢 Active 24h: {active_24h}\n"
        f"🔒 Banned: {banned}\n\n"

        "Use the buttons below to manage users.",

        reply_markup=InlineKeyboardMarkup(
            [

                [
                    InlineKeyboardButton(
                        "🔍 Find User",
                        callback_data="admin_find_user",
                    )
                ],

                [
                    InlineKeyboardButton(
                        "🔙 Admin Panel",
                        callback_data="admin",
                    )
                ],

            ]
        ),

        parse_mode="Markdown",
    )


# ==================================================
# FIND USER
# ==================================================

async def admin_find_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    if not admin_only(query.from_user.id):

        await query.answer(
            "🚫 Admin only.",
            show_alert=True,
        )

        return

    await query.answer()

    context.user_data["admin_action"] = "find_user"

    await query.edit_message_text(

        "🔍 **FIND USER**\n\n"

        "Send the Telegram User ID.\n\n"

        "Example:\n"
        "`123456789`",

        reply_markup=admin_back(),

        parse_mode="Markdown",
    )


# ==================================================
# SHOW USER
# ==================================================

async def show_admin_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
):

    query = update.callback_query

    user = get_user(user_id)

    if not user:

        await query.edit_message_text(
            "❌ User not found.",
            reply_markup=admin_back(),
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

    xp = user.get(
        "xp",
        0,
    )

    level = user.get(
        "level",
        1,
    )

    referrals = user.get(
        "referrals",
        0,
    )

    banned = user.get(
        "banned",
        False,
    )

    status = (
        "🔒 BANNED"
        if banned
        else "🟢 ACTIVE"
    )

    await query.edit_message_text(

        "👤 **USER INFORMATION**\n\n"

        f"🆔 ID: `{user_id}`\n"
        f"📌 Status: {status}\n\n"

        f"💰 Balance: {balance}\n"
        f"🎁 Bonus: {bonus}\n"
        f"💎 Premium Balance: {premium_balance}\n\n"

        f"⭐ XP: {xp}\n"
        f"🏆 Level: {level}\n"
        f"👥 Referrals: {referrals}\n",

        reply_markup=user_info_keyboard(
            user_id
        ),

        parse_mode="Markdown",
    )


# ==================================================
# BALANCE MENU
# ==================================================

async def admin_balance(
    update,
    context,
):

    query = update.callback_query

    if not admin_only(query.from_user.id):

        await query.answer(
            "🚫 Admin only.",
            show_alert=True,
        )

        return

    await query.answer()

    context.user_data["admin_action"] = "find_user"

    await query.edit_message_text(

        "💰 **MANAGE BALANCE**\n\n"

        "Send the User ID whose balance "
        "you want to manage.",

        reply_markup=admin_back(),

        parse_mode="Markdown",
    )


# ==================================================
# ADD BALANCE
# ==================================================

async def admin_add_balance(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    if not admin_only(query.from_user.id):

        await query.answer(
            "🚫 Admin only.",
            show_alert=True,
        )

        return

    await query.answer()

    user_id = int(
        query.data.replace(
            "admin_add_",
            "",
            1,
        )
    )

    context.user_data["admin_action"] = "add_balance"

    context.user_data["admin_target"] = user_id

    await query.edit_message_text(

        "💰 **ADD BALANCE**\n\n"

        f"User ID: `{user_id}`\n\n"

        "Send the amount to add.\n\n"

        "Example: `100`",

        reply_markup=admin_back(),

        parse_mode="Markdown",
    )


# ==================================================
# REMOVE BALANCE
# ==================================================

async def admin_remove_balance(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    if not admin_only(query.from_user.id):

        await query.answer(
            "🚫 Admin only.",
            show_alert=True,
        )

        return

    await query.answer()

    user_id = int(
        query.data.replace(
            "admin_remove_",
            "",
            1,
        )
    )

    context.user_data["admin_action"] = "remove_balance"

    context.user_data["admin_target"] = user_id

    await query.edit_message_text(

        "➖ **REMOVE BALANCE**\n\n"

        f"User ID: `{user_id}`\n\n"

        "Send amount to remove.\n\n"

        "Example: `50`",

        reply_markup=admin_back(),

        parse_mode="Markdown",
    )


# ==================================================
# MEMBERSHIP / BONUS USER CONTROLS
# ==================================================

async def _admin_target_action(update, context, action, target_id):
    q = update.callback_query
    if not q or not admin_only(q.from_user.id):
        if q:
            await q.answer("🚫 Admin only.", show_alert=True)
        return
    target_id = int(target_id)
    user = get_user(target_id, create=False)
    if not user:
        await q.answer("❌ User not found.", show_alert=True)
        return
    if action == "premium_on":
        ok = grant_premium(target_id, 30)
        msg = "👑 Premium ON for 30 days." if ok else "❌ Could not activate Premium."
    elif action == "premium_off":
        ok = revoke_premium(target_id)
        msg = "❌ Premium removed." if ok else "❌ Could not remove Premium."
    elif action == "vip_off":
        ok = remove_vip(target_id)
        msg = "🚫 VIP removed." if ok else "❌ Could not remove VIP."
    else:
        return
    await q.answer(msg, show_alert=True)
    await admin_view_user(update, context, target_id)


async def admin_premium_on(update, context):
    await _admin_target_action(update, context, "premium_on", update.callback_query.data.replace("admin_premium_on_", "", 1))

async def admin_premium_off(update, context):
    await _admin_target_action(update, context, "premium_off", update.callback_query.data.replace("admin_premium_off_", "", 1))

async def admin_vip_off(update, context):
    await _admin_target_action(update, context, "vip_off", update.callback_query.data.replace("admin_vip_off_", "", 1))

async def admin_bonus_add(update, context):
    q=update.callback_query
    if not q or not admin_only(q.from_user.id): return
    await q.answer()
    target=int(q.data.replace("admin_bonus_add_", "", 1))
    context.user_data["admin_action"]="add_bonus"
    context.user_data["admin_target"]=target
    await q.edit_message_text(f"🎁 **ADD BONUS**\n\nUser ID: `{target}`\n\nSend bonus points to add.", reply_markup=admin_back(), parse_mode="Markdown")

async def admin_bonus_remove(update, context):
    q=update.callback_query
    if not q or not admin_only(q.from_user.id): return
    await q.answer()
    target=int(q.data.replace("admin_bonus_remove_", "", 1))
    context.user_data["admin_action"]="remove_bonus"
    context.user_data["admin_target"]=target
    await q.edit_message_text(f"🎁 **REMOVE BONUS**\n\nUser ID: `{target}`\n\nSend bonus points to remove.", reply_markup=admin_back(), parse_mode="Markdown")

async def admin_vip_set(update, context):
    q=update.callback_query
    if not q or not admin_only(q.from_user.id): return
    await q.answer()
    target=int(q.data.replace("admin_vip_set_", "", 1))
    context.user_data["admin_action"]="set_vip"
    context.user_data["admin_target"]=target
    await q.edit_message_text(f"💎 **SET VIP**\n\nUser ID: `{target}`\n\nSend VIP level `1` to `5`.", reply_markup=admin_back(), parse_mode="Markdown")


# ==================================================
# BAN MENU
# ==================================================

async def admin_ban(
    update,
    context,
):

    query = update.callback_query

    if not admin_only(query.from_user.id):

        await query.answer(
            "🚫 Admin only.",
            show_alert=True,
        )

        return

    await query.answer()

    context.user_data["admin_action"] = "find_user"

    await query.edit_message_text(

        "🔒 **BAN / UNBAN USER**\n\n"

        "Send the Telegram User ID.",

        reply_markup=admin_back(),

        parse_mode="Markdown",
    )


# ==================================================
# BAN / UNBAN
# ==================================================

async def admin_toggle_ban(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    if not admin_only(query.from_user.id):

        await query.answer(
            "🚫 Admin only.",
            show_alert=True,
        )

        return

    await query.answer()

    user_id = int(
        query.data.replace(
            "admin_toggleban_",
            "",
            1,
        )
    )

    user = get_user(user_id)

    if not user:

        await query.edit_message_text(
            "❌ User not found.",
            reply_markup=admin_back(),
        )

        return

    current = user.get(
        "banned",
        False,
    )

    new_status = not current

    update_user(
        user_id,
        {
            "banned": new_status,
        },
    )

    status = (
        "🔒 BANNED"
        if new_status
        else "🟢 UNBANNED"
    )

    await query.edit_message_text(

        f"✅ User `{user_id}` is now {status}.",

        reply_markup=InlineKeyboardMarkup(
            [

                [
                    InlineKeyboardButton(
                        "👤 User Info",
                        callback_data=f"admin_view_{user_id}",
                    )
                ],

                [
                    InlineKeyboardButton(
                        "🔙 Admin Panel",
                        callback_data="admin",
                    )
                ],

            ]
        ),

        parse_mode="Markdown",
    )
# ==================================================
# SHORTLINK MANAGEMENT
# ==================================================

async def admin_shortlinks(update, context):
    query = update.callback_query
    if not query or not admin_only(query.from_user.id):
        if query:
            await query.answer("🚫 Admin only.", show_alert=True)
        return

    await query.answer()
    items = get_shortlinks(include_disabled=True)
    buttons = [[InlineKeyboardButton("➕ Add Shortlink", callback_data="admin_add_shortlink")]]

    for item in items[:30]:
        status = "🟢" if item.get("enabled", True) else "🔴"
        sid = str(item.get("id"))
        buttons.append([
            InlineKeyboardButton(
                f"{status} {item.get('name', sid)} | {item.get('reward', 0)}",
                callback_data=f"admin_shortlink_toggle_{sid}",
            )
        ])
        buttons.append([
            InlineKeyboardButton(
                f"🗑 Delete {sid}",
                callback_data=f"admin_shortlink_delete_{sid}",
            )
        ])

    buttons.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin")])
    await query.edit_message_text(
        "🔗 **SHORTLINK MANAGEMENT**\n\n"
        f"Configured: {len(items)}\n\n"
        "Add format: `id|name|url|reward|cooldown|provider`\n"
        "Example: `sl1|Example|https://example.com/go|0|86400|shrtfly`",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )


async def admin_add_shortlink(update, context):
    query = update.callback_query
    if not query or not admin_only(query.from_user.id):
        if query:
            await query.answer("🚫 Admin only.", show_alert=True)
        return
    await query.answer()
    context.user_data["admin_action"] = "add_shortlink"
    await query.edit_message_text(
        "🔗 **ADD SHORTLINK**\n\n"
        "Send: `id|name|url|reward|cooldown`\n\n"
        "Example: `sl1|Example|https://example.com/go|0|86400|shrtfly`",
        reply_markup=admin_back(),
        parse_mode="Markdown",
    )


async def admin_shortlink_toggle(update, context):
    query = update.callback_query
    if not query or not admin_only(query.from_user.id):
        if query:
            await query.answer("🚫 Admin only.", show_alert=True)
        return
    sid = str(query.data).replace("admin_shortlink_toggle_", "", 1)
    item = next((x for x in get_shortlinks(include_disabled=True) if str(x.get("id")) == sid), None)
    if not item:
        await query.answer("Shortlink not found.", show_alert=True)
        return
    new_state = not bool(item.get("enabled", True))
    if set_shortlink_enabled(sid, new_state):
        await query.answer("🟢 Enabled" if new_state else "🔴 Disabled")
    else:
        await query.answer("Update failed.", show_alert=True)
    await admin_shortlinks(update, context)


async def admin_shortlink_delete(update, context):
    query = update.callback_query
    if not query or not admin_only(query.from_user.id):
        if query:
            await query.answer("🚫 Admin only.", show_alert=True)
        return
    sid = str(query.data).replace("admin_shortlink_delete_", "", 1)
    if delete_shortlink(sid):
        await query.answer("🗑 Deleted")
    else:
        await query.answer("Shortlink not found.", show_alert=True)
    await admin_shortlinks(update, context)


# ==================================================
# MEMBERSHIP CASH PAYMENT MANAGEMENT
# ==================================================
async def admin_membership_payments(update, context):
    q=update.callback_query
    if not q or not admin_only(q.from_user.id): return
    await q.answer(); items=pending_payments(30)
    buttons=[]
    for p in items:
        label=f"{p['payment_id']} | {p['product']} | ৳{p['price']:g}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"admin_payment_view_{p['payment_id']}")])
    buttons.append([InlineKeyboardButton("🔙 Admin Panel",callback_data="admin")])
    await q.edit_message_text("💳 **MEMBERSHIP PAYMENTS**\n\n"+ (f"Pending: {len(items)}" if items else "No pending payments."), reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

async def admin_payment_view(update, context):
    q=update.callback_query
    if not q or not admin_only(q.from_user.id): return
    await q.answer(); pid=str(q.data).replace("admin_payment_view_", "", 1); p=get_payment(pid)
    if not p: await q.edit_message_text("⚠️ Payment not found.",reply_markup=admin_back()); return
    ref=p.get("reference","(not submitted)")
    buttons=[]
    if p.get("status")=="pending" and ref!="(not submitted)":
        buttons.append([InlineKeyboardButton("✅ Approve",callback_data=f"admin_payment_approve_{pid}")])
        buttons.append([InlineKeyboardButton("❌ Reject",callback_data=f"admin_payment_reject_{pid}")])
    buttons.append([InlineKeyboardButton("🔙 Payments",callback_data="admin_membership_payments")])
    await q.edit_message_text(f"💳 **PAYMENT REVIEW**\n\n🆔 `{pid}`\n👤 User: `{p.get('user_id')}`\n📦 Product: `{p.get('product')}`\n💰 Amount: ৳{float(p.get('price',0)):g}\n📱 Method: `{p.get('method')}`\n🧾 Reference: `{ref}`\n📌 Status: `{p.get('status')}`",reply_markup=InlineKeyboardMarkup(buttons),parse_mode="Markdown")

async def admin_payment_approve(update, context):
    q=update.callback_query
    if not q or not admin_only(q.from_user.id): return
    pid=str(q.data).replace("admin_payment_approve_", "", 1); ok,msg=approve_payment(pid,q.from_user.id); await q.answer(msg,show_alert=not ok)
    p=get_payment(pid)
    if ok:
        try: await context.bot.send_message(int(p['user_id']),f"✅ **Payment approved!**\n\n💳 {p['product']} is now active for 30 days.",parse_mode="Markdown")
        except Exception: pass
    await admin_membership_payments(update,context)

async def admin_payment_reject(update, context):
    q=update.callback_query
    if not q or not admin_only(q.from_user.id): return
    pid=str(q.data).replace("admin_payment_reject_", "", 1); context.user_data["admin_action"]="payment_reject_reason"; context.user_data["payment_id"]=pid
    await q.answer(); await q.edit_message_text("❌ Send rejection reason:",reply_markup=admin_back())

# ==================================================
# WITHDRAWAL MANAGEMENT
# ==================================================

async def admin_withdrawals(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query:
        return

    if not admin_only(query.from_user.id):
        await query.answer(
            "🚫 Admin only.",
            show_alert=True,
        )
        return

    await query.answer()

    pending = get_withdrawals(
        status="pending",
        limit=30,
    )

    pending_count = pending_withdrawals_count()
    approved_total = total_withdrawals()

    if not pending:
        await query.edit_message_text(
            "💸 **WITHDRAWAL MANAGEMENT**\n\n"
            f"🟡 Pending: {pending_count}\n"
            f"🟢 Approved Total: {approved_total} Points\n\n"
            "✅ No pending withdrawals.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔄 Refresh",
                            callback_data="admin_withdrawals",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🔙 Admin Panel",
                            callback_data="admin",
                        )
                    ],
                ]
            ),
            parse_mode="Markdown",
        )
        return

    buttons = []

    for item in pending[:20]:
        withdrawal_id = item.get(
            "withdrawal_id",
            "N/A",
        )

        amount = int(
            item.get(
                "amount",
                0,
            )
        )

        buttons.append(
            [
                InlineKeyboardButton(
                    f"💸 {withdrawal_id} • {amount}",
                    callback_data=(
                        f"admin_withdraw_view_{withdrawal_id}"
                    ),
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                "🔄 Refresh",
                callback_data="admin_withdrawals",
            )
        ]
    )

    buttons.append(
        [
            InlineKeyboardButton(
                "🔙 Admin Panel",
                callback_data="admin",
            )
        ]
    )

    await query.edit_message_text(
        "💸 **WITHDRAWAL MANAGEMENT**\n\n"
        f"🟡 Pending: {pending_count}\n"
        f"🟢 Approved Total: {approved_total} Points\n\n"
        "Select a pending withdrawal:",
        reply_markup=InlineKeyboardMarkup(
            buttons
        ),
        parse_mode="Markdown",
    )


async def admin_withdrawal_view(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query:
        return

    if not admin_only(query.from_user.id):
        await query.answer(
            "🚫 Admin only.",
            show_alert=True,
        )
        return

    withdrawal_id = query.data.replace(
        "admin_withdraw_view_",
        "",
        1,
    )

    records = get_withdrawals(
        status="pending",
        limit=100,
    )

    withdrawal = next(
        (
            item
            for item in records
            if item.get(
                "withdrawal_id"
            ) == withdrawal_id
        ),
        None,
    )

    if not withdrawal:
        await query.answer(
            "Withdrawal not found or already processed.",
            show_alert=True,
        )

        await admin_withdrawals(
            update,
            context,
        )

        return

    await query.answer()

    user_id = int(
        withdrawal.get(
            "user_id",
            0,
        )
    )

    amount = int(
        withdrawal.get(
            "amount",
            0,
        )
    )

    method = withdrawal.get(
        "method",
        "N/A",
    )

    account = withdrawal.get(
        "payment_account",
        "N/A",
    )

    created_at = withdrawal.get(
        "created_at",
        0,
    )

    if created_at:
        created_text = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(
                int(created_at)
            ),
        )
    else:
        created_text = "N/A"

    await query.edit_message_text(
        "💸 **WITHDRAWAL REQUEST**\n\n"
        f"🆔 ID: `{withdrawal_id}`\n"
        f"👤 User ID: `{user_id}`\n"
        f"💰 Amount: {amount} Points\n"
        f"💳 Method: {method}\n"
        f"📱 Account: `{account}`\n"
        f"🕒 Created: {created_text}\n"
        "🟡 Status: Pending\n\n"
        "Choose an action:",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🟢 Approve",
                        callback_data=(
                            f"admin_withdraw_approve_{withdrawal_id}"
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔴 Reject",
                        callback_data=(
                            f"admin_withdraw_reject_{withdrawal_id}"
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔙 Pending Withdrawals",
                        callback_data="admin_withdrawals",
                    )
                ],
            ]
        ),
        parse_mode="Markdown",
    )


async def admin_withdrawal_approve(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query:
        return

    if not admin_only(query.from_user.id):
        await query.answer(
            "🚫 Admin only.",
            show_alert=True,
        )
        return

    withdrawal_id = query.data.replace(
        "admin_withdraw_approve_",
        "",
        1,
    )

    success = approve_withdrawal(withdrawal_id)

    if not success:
        await query.answer(
            "Withdrawal not found or already processed.",
            show_alert=True,
        )
        return

    records = get_withdrawals(status="approved", limit=100)
    withdrawal = next(
        (item for item in records if item.get("withdrawal_id") == withdrawal_id),
        None,
    )

    await query.answer("🟢 Withdrawal approved.")

    if withdrawal:
        user_id = int(withdrawal.get("user_id", 0))
        amount = int(withdrawal.get("amount", 0))
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "🟢 **WITHDRAWAL APPROVED**\n\n"
                    f"🆔 ID: `{withdrawal_id}`\n"
                    f"💰 Amount: {amount} Points\n\n"
                    "Your withdrawal has been approved by Admin."
                ),
                parse_mode="Markdown",
            )
        except Exception:
            logger.exception(
                "Withdrawal approval notification failed | user=%s",
                user_id,
            )

    await admin_withdrawals(update, context)


# ==================================================
# STATISTICS
# ==================================================

async def admin_statistics(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    if not admin_only(query.from_user.id):

        await query.answer(
            "🚫 Admin only.",
            show_alert=True,
        )

        return

    await query.answer()

    total_users = users.count_documents({})

    active_users = users.count_documents(
        {
            "last_login": {
                "$gte": int(time.time()) - 86400
            }
        }
    )

    banned_users = users.count_documents(
        {
            "banned": True
        }
    )

    pipeline = [
        {
            "$group": {
                "_id": None,
                "total": {
                    "$sum": "$total_earned"
                },
            }
        }
    ]

    result = list(
        users.aggregate(pipeline)
    )

    total_distributed = 0

    if result:

        total_distributed = result[0].get(
            "total",
            0,
        )

    referral_pipeline = [
        {
            "$group": {
                "_id": None,
                "total": {
                    "$sum": "$referral_earn"
                },
            }
        }
    ]

    referral_result = list(
        users.aggregate(
            referral_pipeline
        )
    )

    referral_earnings = 0

    if referral_result:

        referral_earnings = referral_result[0].get(
            "total",
            0,
        )

    spin_pipeline = [
        {
            "$group": {
                "_id": None,
                "total": {
                    "$sum": "$spin_wins"
                },
            }
        }
    ]

    spin_result = list(
        users.aggregate(
            spin_pipeline
        )
    )

    spin_wins = 0

    if spin_result:

        spin_wins = spin_result[0].get(
            "total",
            0,
        )

    await query.edit_message_text(

        "📊 **ADVANCED STATISTICS**\n\n"

        f"👥 Total Users: {total_users}\n"
        f"🟢 Active Users (24h): {active_users}\n"
        f"🔒 Banned Users: {banned_users}\n\n"

        f"💰 Total Points Distributed: "
        f"{total_distributed}\n"

        f"👥 Referral Earnings: "
        f"{referral_earnings}\n"

        f"🎡 Winning Spins: "
        f"{spin_wins}\n",

        reply_markup=admin_back(),

        parse_mode="Markdown",
    )

# ==================================================
# REWARD SETTINGS
# ==================================================

async def admin_rewards(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    if not admin_only(query.from_user.id):

        await query.answer(
            "🚫 Admin only.",
            show_alert=True,
        )

        return

    await query.answer()

    settings = (
        db["bot_settings"].find_one(
            {"_id": "main"}
        )
        or {}
    )

    daily_bonus = settings.get(
        "daily_bonus",
        5,
    )

    group_reward = settings.get(
        "group_reward",
        20,
    )

    await query.edit_message_text(

        "🎁 **REWARD SETTINGS**\n\n"

        f"🎁 Daily Bonus: {daily_bonus}\n"
        f"👥 Group Join Reward: {group_reward}\n\n"

        "Reward configuration is stored "
        "in MongoDB.",

        reply_markup=InlineKeyboardMarkup(
            [

                [
                    InlineKeyboardButton(
                        "🎁 Change Daily Bonus",
                        callback_data="admin_set_daily",
                    )
                ],

                [
                    InlineKeyboardButton(
                        "👥 Change Group Reward",
                        callback_data="admin_set_group",
                    )
                ],

                [
                    InlineKeyboardButton(
                        "🔙 Admin Panel",
                        callback_data="admin",
                    )
                ],

            ]
        ),

        parse_mode="Markdown",
    )

# ==================================================
# DAILY REWARD
# ==================================================

async def admin_set_daily(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    context.user_data["admin_action"] = "set_daily"

    await query.edit_message_text(
        "🎁 Send new Daily Bonus amount:",
        reply_markup=admin_back(),
    )


# ==================================================
# GROUP REWARD
# ==================================================

async def admin_set_group(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    context.user_data["admin_action"] = "set_group"

    await query.edit_message_text(
        "👥 Send new Group Join Reward:",
        reply_markup=admin_back(),
    )


# ==================================================
# TASK SETTINGS
# ==================================================

async def admin_tasks(update, context):
    query = update.callback_query
    if not query or not admin_only(query.from_user.id):
        if query: await query.answer("🚫 Admin only.", show_alert=True)
        return
    await query.answer()
    items = get_tasks(include_disabled=True)
    buttons = [[InlineKeyboardButton("➕ Add Task", callback_data="admin_add_task")]]
    for t in items[:30]:
        status = "🟢" if t.get("enabled", True) else "🔴"
        tid = str(t.get("id"))
        title = str(t.get('title', tid))[:40]
        action = "🔴 Disable" if t.get("enabled", True) else "🟢 Enable"
        buttons.append([InlineKeyboardButton(f"{status} {title} | +{t.get('reward',0)}", callback_data=f"admin_task_toggle_{tid}")])
        buttons.append([
            InlineKeyboardButton(action, callback_data=f"admin_task_toggle_{tid}"),
            InlineKeyboardButton("🗑 Delete", callback_data=f"admin_task_delete_{tid}"),
        ])
    buttons.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin")])
    await query.edit_message_text(
        "🎯 **TASK MANAGEMENT**\n\n"
        f"Configured: {len(items)}\n\n"
        "Add format:\n`id|title|description|url|reward|cooldown|xp|energy`\n\n"
        "Example:\n`task1|Join Channel|Join our channel|https://t.me/example|50|86400|5|1`\n\n"
        "🟢 visible/active · 🔴 disabled",
        reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

async def admin_add_task(update, context):
    query=update.callback_query
    if not query or not admin_only(query.from_user.id):
        if query: await query.answer("🚫 Admin only.", show_alert=True)
        return
    await query.answer(); context.user_data["admin_action"]="add_task"
    await query.edit_message_text(
        "🎯 **ADD TASK**\n\nSend one line:\n`id|title|description|url|reward|cooldown|xp|energy`\n\n"
        "Use `-` for no URL/description. Example:\n`task1|Join Channel|Join our channel|https://t.me/example|50|86400|5|1`",
        reply_markup=admin_back(), parse_mode="Markdown")

async def admin_task_toggle(update, context):
    q=update.callback_query
    if not q or not admin_only(q.from_user.id): return
    tid=str(q.data).replace("admin_task_toggle_", "", 1); task=next((x for x in get_tasks(True) if str(x.get("id"))==tid),None)
    if not task: await q.answer("Task not found.", show_alert=True); return
    new = not bool(task.get("enabled", True))
    if not set_task_enabled(tid, new):
        await q.answer("⚠️ Could not change task status.", show_alert=True)
        return
    await q.answer("🟢 Task enabled" if new else "🔴 Task disabled")
    await admin_tasks(update, context)

async def admin_task_delete(update, context):
    q=update.callback_query
    if not q or not admin_only(q.from_user.id): return
    tid=str(q.data).replace("admin_task_delete_", "", 1)
    if delete_task(tid): await q.answer("🗑 Deleted")
    else: await q.answer("Task not found.", show_alert=True)
    await admin_tasks(update,context)


async def admin_set_task_reward(update, context):
    query = update.callback_query
    if not query or not admin_only(query.from_user.id):
        if query: await query.answer("🚫 Admin only.", show_alert=True)
        return
    await query.answer()
    context.user_data["admin_action"] = "set_task_reward"
    await query.edit_message_text("🎯 Send new default Task Reward (points):", reply_markup=admin_back())


async def admin_set_task_limit(update, context):
    query = update.callback_query
    if not query or not admin_only(query.from_user.id):
        if query: await query.answer("🚫 Admin only.", show_alert=True)
        return
    await query.answer()
    context.user_data["admin_action"] = "set_task_limit"
    await query.edit_message_text("🎯 Send new Daily Task Limit:", reply_markup=admin_back())


# ==================================================
# WHEEL SETTINGS
# ==================================================

async def admin_wheel(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    settings = (
        db["bot_settings"].find_one(
            {"_id": "main"}
        )
        or {}
    )

    minimum = settings.get(
        "spin_min",
        1,
    )

    maximum = settings.get(
        "spin_max",
        20,
    )

    cooldown = settings.get(
        "spin_cooldown",
        60,
    )

    await query.edit_message_text(

        "🎡 **WHEEL SETTINGS**\n\n"

        f"🔽 Minimum Reward: {minimum}\n"
        f"🔼 Maximum Reward: {maximum}\n"
        f"⏳ Cooldown: {cooldown}s",

        reply_markup=InlineKeyboardMarkup(
            [

                [
                    InlineKeyboardButton(
                        "🔽 Set Minimum",
                        callback_data="admin_set_spin_min",
                    ),

                    InlineKeyboardButton(
                        "🔼 Set Maximum",
                        callback_data="admin_set_spin_max",
                    ),
                ],

                [
                    InlineKeyboardButton(
                        "⏳ Set Cooldown",
                        callback_data="admin_set_spin_cd",
                    )
                ],

                [
                    InlineKeyboardButton(
                        "🔙 Admin Panel",
                        callback_data="admin",
                    )
                ],

            ]
        ),

        parse_mode="Markdown",
    )


async def admin_set_spin_min(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    context.user_data["admin_action"] = (
        "set_spin_min"
    )

    await query.edit_message_text(
        "🎡 Send new minimum reward:",
        reply_markup=admin_back(),
    )


async def admin_set_spin_max(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    context.user_data["admin_action"] = (
        "set_spin_max"
    )

    await query.edit_message_text(
        "🎡 Send new maximum reward:",
        reply_markup=admin_back(),
    )


async def admin_set_spin_cd(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    context.user_data["admin_action"] = (
        "set_spin_cd"
    )

    await query.edit_message_text(
        "🎡 Send new cooldown in seconds:",
        reply_markup=admin_back(),
    )
    
# ==================================================
# LUCKY BOX
# ==================================================

async def admin_lucky(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    settings = (
        db["bot_settings"].find_one(
            {"_id": "main"}
        )
        or {}
    )

    minimum = settings.get(
        "lucky_min",
        5,
    )

    maximum = settings.get(
        "lucky_max",
        30,
    )

    await query.edit_message_text(

        "🎁 **LUCKY BOX SETTINGS**\n\n"

        f"🔽 Minimum Reward: {minimum}\n"
        f"🔼 Maximum Reward: {maximum}",

        reply_markup=InlineKeyboardMarkup(
            [

                [
                    InlineKeyboardButton(
                        "🔽 Set Minimum",
                        callback_data="admin_set_lucky_min",
                    ),

                    InlineKeyboardButton(
                        "🔼 Set Maximum",
                        callback_data="admin_set_lucky_max",
                    ),
                ],

                [
                    InlineKeyboardButton(
                        "🔙 Admin Panel",
                        callback_data="admin",
                    )
                ],

            ]
        ),

        parse_mode="Markdown",
    )


async def admin_set_lucky_min(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    context.user_data["admin_action"] = (
        "set_lucky_min"
    )

    await query.edit_message_text(
        "🎁 Send new Lucky Box minimum:",
        reply_markup=admin_back(),
    )


async def admin_set_lucky_max(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    context.user_data["admin_action"] = (
        "set_lucky_max"
    )

    await query.edit_message_text(
        "🎁 Send new Lucky Box maximum:",
        reply_markup=admin_back(),
    )

# ==================================================
# REFERRAL SETTINGS
# ==================================================

async def admin_referral(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    settings = (
        db["bot_settings"].find_one(
            {"_id": "main"}
        )
        or {}
    )

    reward = settings.get(
        "referral_reward",
        10,
    )

    xp = settings.get(
        "referral_xp",
        10,
    )

    await query.edit_message_text(

        "👥 **REFERRAL SETTINGS**\n\n"

        f"💰 Referral Reward: {reward}\n"
        f"⭐ Referral XP: {xp}",

        reply_markup=InlineKeyboardMarkup(
            [

                [
                    InlineKeyboardButton(
                        "💰 Change Reward",
                        callback_data="admin_set_ref_reward",
                    )
                ],

                [
                    InlineKeyboardButton(
                        "⭐ Change XP",
                        callback_data="admin_set_ref_xp",
                    )
                ],
                [
                    InlineKeyboardButton("🏆 Milestones", callback_data="admin_ref_milestones"),
                ],
                [
                    InlineKeyboardButton(
                        "🔙 Admin Panel",
                        callback_data="admin",
                    )
                ],

            ]
        ),

        parse_mode="Markdown",
    )


async def admin_ref_milestones(update, context):
    q=update.callback_query; await q.answer()
    ms=get_milestones()
    lines=["🏆 **REFERRAL MILESTONES**", "", "Format: `count|reward`", "Send `0|0` to delete a milestone.", ""]
    lines += [f"{n} referrals → {r} Points" for n,r in ms.items()] or ["No milestones configured."]
    await q.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ Add/Edit",callback_data="admin_add_ref_milestone")],[InlineKeyboardButton("🗑 Delete",callback_data="admin_del_ref_milestone")],[InlineKeyboardButton("🔙 Referral Settings",callback_data="admin_referral")]]), parse_mode="Markdown")

async def admin_add_ref_milestone(update, context):
    q=update.callback_query; await q.answer(); context.user_data["admin_action"]="add_ref_milestone"
    await q.edit_message_text("🏆 Send milestone as `referral_count|reward_points`\nExample: `25|700`",reply_markup=admin_back(),parse_mode="Markdown")

async def admin_del_ref_milestone(update, context):
    q=update.callback_query; await q.answer(); context.user_data["admin_action"]="del_ref_milestone"
    await q.edit_message_text("🗑 Send the referral milestone count to delete. Example: `25`",reply_markup=admin_back())

async def admin_set_ref_reward(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    context.user_data["admin_action"] = (
        "set_ref_reward"
    )

    await query.edit_message_text(
        "👥 Send new Referral Reward:",
        reply_markup=admin_back(),
    )


async def admin_set_ref_xp(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    context.user_data["admin_action"] = (
        "set_ref_xp"
    )

    await query.edit_message_text(
        "👥 Send new Referral XP:",
        reply_markup=admin_back(),
    )

# ==================================================
# BOT SETTINGS
# ==================================================

async def admin_settings(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    settings = (
        db["bot_settings"].find_one(
            {"_id": "main"}
        )
        or {}
    )

    maintenance = settings.get(
        "maintenance",
        False,
    )

    notifications = settings.get(
        "notifications",
        True,
    )

    await query.edit_message_text(

        "⚙️ **BOT SETTINGS**\n\n"

        f"🔧 Maintenance: "
        f"{'ON' if maintenance else 'OFF'}\n"

        f"🔔 Notifications: "
        f"{'ON' if notifications else 'OFF'}",

        reply_markup=InlineKeyboardMarkup(
            [

                [
                    InlineKeyboardButton(
                        "🔧 Toggle Maintenance",
                        callback_data=(
                            "admin_toggle_maintenance"
                        ),
                    )
                ],

                [
                    InlineKeyboardButton(
                        "🔔 Toggle Notifications",
                        callback_data=(
                            "admin_toggle_notifications"
                        ),
                    )
                ],

                [
                    InlineKeyboardButton(
                        "🔙 Admin Panel",
                        callback_data="admin",
                    )
                ],

            ]
        ),

        parse_mode="Markdown",
    )

# ==================================================
# BROADCAST
# ==================================================

async def admin_broadcast(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    await query.edit_message_text(

        "📢 **BROADCAST CENTER**\n\n"

        "Choose broadcast type:",

        reply_markup=InlineKeyboardMarkup(
            [

                [
                    InlineKeyboardButton(
                        "👥 All Users",
                        callback_data="admin_bc_all",
                    )
                ],

                [
                    InlineKeyboardButton(
                        "🟢 Active 24h",
                        callback_data="admin_bc_active",
                    )
                ],

                [
                    InlineKeyboardButton(
                        "👤 Specific User",
                        callback_data="admin_bc_specific",
                    )
                ],

                [
                    InlineKeyboardButton(
                        "🔙 Admin Panel",
                        callback_data="admin",
                    )
                ],

            ]
        ),

        parse_mode="Markdown",
    )


async def admin_bc_all(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    context.user_data["admin_action"] = (
        "broadcast_all"
    )

    await query.edit_message_text(
        "📢 Send the message you want to broadcast.",
        reply_markup=admin_back(),
    )


async def admin_bc_active(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    context.user_data["admin_action"] = (
        "broadcast_active"
    )

    await query.edit_message_text(
        "📢 Send the message for active users.",
        reply_markup=admin_back(),
    )


async def admin_bc_specific(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    context.user_data["admin_action"] = (
        "broadcast_specific"
    )

    await query.edit_message_text(

        "👤 **SPECIFIC USER BROADCAST**\n\n"

        "Send User ID first.\n\n"
        "Example:\n"
        "`123456789`",

        reply_markup=admin_back(),

        parse_mode="Markdown",
    )

# ==================================================
# ADMIN TEXT HANDLER
# ==================================================

async def admin_text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.effective_user:
        return False

    if not update.message:
        return False

    user_id = update.effective_user.id

    if not admin_only(user_id):
        return False

    action = context.user_data.get(
        "admin_action"
    )

    if not action:
        return False

    text = (
        update.message.text or ""
    ).strip()

    # ==================================================
    # FIND USER
    # ==================================================

    if action == "find_user":

        try:
            target_id = int(text)

        except ValueError:

            await update.message.reply_text(
                "❌ Invalid User ID."
            )

            return True

        context.user_data.clear()

        user = get_user(
            target_id
        )

        if not user:

            await update.message.reply_text(
                "❌ User not found.",
                reply_markup=admin_back(),
            )

            return True

        balance = user.get(
            "balance",
            0,
        )

        bonus = user.get(
            "bonus_balance",
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

        referrals = user.get(
            "referrals",
            0,
        )

        banned = user.get(
            "banned",
            False,
        )

        await update.message.reply_text(

            "👤 **USER INFORMATION**\n\n"

            f"🆔 ID: `{target_id}`\n"
            f"💰 Balance: {balance}\n"
            f"🎁 Bonus: {bonus}\n"
            f"⭐ XP: {xp}\n"
            f"🏆 Level: {level}\n"
            f"👥 Referrals: {referrals}\n"
            f"🔒 Banned: {banned}",

            reply_markup=user_info_keyboard(
                target_id
            ),

            parse_mode="Markdown",
        )

        return True

    # ==================================================
    # BONUS / VIP ADMIN ACTIONS
    # ==================================================
    if action in ("add_bonus", "remove_bonus", "set_vip"):
        target_id = int(context.user_data.get("admin_target", 0) or 0)
        if not get_user(target_id, create=False):
            context.user_data.clear()
            await update.message.reply_text("❌ User not found.", reply_markup=admin_back())
            return True
        try:
            value = int(text)
        except ValueError:
            await update.message.reply_text("❌ Send a valid whole number.")
            return True
        if action == "add_bonus":
            ok = add_bonus(target_id, value)
            message = "🎁 Bonus added." if ok else "❌ Could not add bonus."
        elif action == "remove_bonus":
            removed = remove_bonus(target_id, value)
            ok = removed == value
            message = f"🎁 Removed {removed} bonus points." if ok else "❌ Could not remove that amount."
        else:
            if value not in (1,2,3,4,5):
                await update.message.reply_text("❌ VIP level must be 1–5.")
                return True
            ok = grant_vip(target_id, value, 30)
            message = f"💎 VIP {value} activated for 30 days." if ok else "❌ Could not activate VIP."
        context.user_data.clear()
        await update.message.reply_text(message, reply_markup=admin_back())
        return True

    # ==================================================
    # WITHDRAWAL REJECTION REASON
    # ==================================================

    if action == "withdrawal_reject_reason":

        withdrawal_id = (
            context.user_data.get(
                "withdrawal_reject_id"
            )
        )

        reason = (
            update.message.text or ""
        ).strip()

        if not withdrawal_id:

            context.user_data.clear()

            await update.message.reply_text(
                "❌ Withdrawal session expired.",
                reply_markup=admin_back(),
            )

            return True

        if not reason:

            await update.message.reply_text(
                "❌ Please send a rejection reason.",
                reply_markup=admin_back(),
            )

            return True

        records = get_withdrawals(
            status="pending",
            limit=100,
        )

        withdrawal = next(
            (
                item
                for item in records
                if item.get(
                    "withdrawal_id"
                ) == withdrawal_id
            ),
            None,
        )

        if not withdrawal:

            context.user_data.clear()

            await update.message.reply_text(
                "❌ Withdrawal not found.",
                reply_markup=admin_back(),
            )

            return True

        target_user_id = int(
            withdrawal.get(
                "user_id",
                0,
            )
        )

        amount = int(
            withdrawal.get(
                "amount",
                0,
            )
        )

        success = reject_withdrawal(
            withdrawal_id,
            reason,
        )

        if not success:

            context.user_data.clear()

            await update.message.reply_text(
                "❌ Withdrawal was already processed.",
                reply_markup=admin_back(),
            )

            return True

# ----------------------------------------------
        # USER NOTIFICATION
        # ----------------------------------------------

        try:

            await context.bot.send_message(

                chat_id=target_user_id,

                text=(

                    "🔴 **WITHDRAWAL REJECTED**\n\n"

                    f"🆔 ID: `{withdrawal_id}`\n"
                    f"💰 Amount: {amount} Points\n\n"

                    f"📝 Reason: {reason}\n\n"

                    "💰 The amount has been "
                    "returned to your balance."
                ),

                parse_mode="Markdown",
            )

        except Exception as error:

            logger.warning(

                "Withdrawal rejection "
                "notification failed | "
                "user=%s | error=%s",

                target_user_id,
                error,
            )

        context.user_data.clear()

        await update.message.reply_text(

            "🔴 **WITHDRAWAL REJECTED**\n\n"

            f"🆔 ID: `{withdrawal_id}`\n"
            f"👤 User: `{target_user_id}`\n"
            f"💰 Refunded: {amount} Points\n"
            f"📝 Reason: {reason}",

            reply_markup=admin_back(),

            parse_mode="Markdown",
        )

        return True

# ==================================================
    # BALANCE
    # ==================================================

    if action in (
        "add_balance",
        "remove_balance",
    ):

        target_id = (
            context.user_data.get(
                "admin_target"
            )
        )

        try:

            amount = int(text)

        except ValueError:

            await update.message.reply_text(
                "❌ Amount must be a number."
            )

            return True

        if amount <= 0:

            await update.message.reply_text(
                "❌ Amount must be greater than 0."
            )

            return True

        target_user = get_user(
            target_id
        )

        if not target_user:

            context.user_data.clear()

            await update.message.reply_text(
                "❌ User not found.",
                reply_markup=admin_back(),
            )

            return True

        if action == "add_balance":

            add_balance(
                target_id,
                amount,
            )

            message = (
                f"✅ Added {amount} Points "
                f"to {target_id}."
            )

        else:

            removed = remove_balance(
                target_id,
                amount,
            )

            if removed <= 0:

                await update.message.reply_text(
                    "❌ Insufficient balance."
                )

                return True

            message = (
                f"✅ Removed {removed} Points "
                f"from {target_id}."
            )

        context.user_data.clear()

        await update.message.reply_text(

            message,

            reply_markup=admin_back(),

            parse_mode="Markdown",
        )

        return True
        

    # ==================================================
    # SPECIFIC BROADCAST USER ID
    # ==================================================

    if action == "broadcast_specific":

        try:

            target_id = int(text)

        except ValueError:

            await update.message.reply_text(
                "❌ Invalid User ID."
            )

            return True

        target_user = get_user(
            target_id
        )

        if not target_user:

            await update.message.reply_text(
                "❌ User not found."
            )

            return True

        context.user_data[
            "admin_action"
        ] = "broadcast_specific_message"

        context.user_data[
            "admin_target"
        ] = target_id

        await update.message.reply_text(

            "📢 Now send the message.",

            reply_markup=admin_back(),
        )

        return True
        # ==================================================
    # SPECIFIC BROADCAST MESSAGE
    # ==================================================

    if action == "payment_reference":
        pid=context.user_data.get("payment_reference_id")
        ok=submit_reference(pid,text) if pid else False
        context.user_data.clear()
        await update.message.reply_text("✅ Transaction ID submitted. Admin will verify your payment." if ok else "❌ Could not submit. Please start payment again.", reply_markup=admin_back() if admin_only(user_id) else None)
        if ok:
            p=get_payment(pid)
            try: await context.bot.send_message(int(ADMIN_ID),f"💳 New membership payment\nID: {pid}\nUser: {p.get('user_id')}\nProduct: {p.get('product')}\nAmount: ৳{float(p.get('price',0)):g}\nMethod: {p.get('method')}\nReference: {text}")
            except Exception: pass
        return True

    if action == "payment_reject_reason":
        pid=context.user_data.get("payment_id"); reason=text or "Rejected"; p=get_payment(pid) if pid else None
        ok=reject_payment(pid,reason) if pid else False; context.user_data.clear()
        if ok and p:
            try: await context.bot.send_message(int(p['user_id']),f"❌ **Payment rejected**\n\nReason: {reason}",parse_mode="Markdown")
            except Exception: pass
        await update.message.reply_text("✅ Payment rejected." if ok else "❌ Payment was already processed.",reply_markup=admin_back())
        return True

    if action == "add_ref_milestone":
        parts=[x.strip() for x in text.split("|",1)]
        try: ok=len(parts)==2 and set_milestone(int(parts[0]), int(parts[1]))
        except ValueError: ok=False
        context.user_data.clear(); await update.message.reply_text("✅ Milestone saved." if ok else "❌ Invalid format. Use count|reward", reply_markup=admin_back()); return True

    if action == "del_ref_milestone":
        try: ok=delete_milestone(int(text.strip()))
        except ValueError: ok=False
        context.user_data.clear(); await update.message.reply_text("✅ Milestone deleted." if ok else "❌ Milestone not found.", reply_markup=admin_back()); return True

    if action == "add_task":
        parts = [x.strip() for x in text.split("|", 7)]
        if len(parts) != 8:
            await update.message.reply_text(
                "❌ Format: id|title|description|url|reward|cooldown|xp|energy",
                reply_markup=admin_back(),
            )
            return True

        tid, title, desc, url, reward_text, cooldown_text, xp_text, energy_text = parts
        if desc == "-":
            desc = ""
        if url == "-":
            url = None

        try:
            if not tid or not title:
                raise ValueError
            reward = int(reward_text)
            cooldown = int(cooldown_text)
            xp = int(xp_text)
            energy = int(energy_text)
            if reward < 0 or cooldown < 0 or xp < 0 or energy < 0:
                raise ValueError

            ok = register_task(
                tid, title, desc, reward, url, cooldown, True, xp, energy
            )
        except (TypeError, ValueError):
            ok = False

        context.user_data.clear()
        await update.message.reply_text(
            "✅ Task added/updated." if ok else
            "❌ Invalid task values. Use whole numbers for reward, cooldown, XP and energy.",
            reply_markup=admin_back(),
        )
        return True

    if action == "add_shortlink":
        parts = [part.strip() for part in (update.message.text or "").split("|")]
        if len(parts) not in (5, 6):
            await update.message.reply_text(
                "❌ Invalid format. Use: id|name|url|reward|cooldown|provider",
                reply_markup=admin_back(),
            )
            return True
        if len(parts) == 5:
            sid, name, url, reward_text, cooldown_text = parts
            provider = "manual"
        else:
            sid, name, url, reward_text, cooldown_text, provider = parts
            provider = provider.lower() or "manual"
        try:
            reward = int(reward_text)
            cooldown = int(cooldown_text)
        except ValueError:
            await update.message.reply_text("❌ Reward and cooldown must be numbers.", reply_markup=admin_back())
            return True
        if reward < 0 or cooldown < 0 or not sid or not url:
            await update.message.reply_text("❌ Invalid shortlink values.", reply_markup=admin_back())
            return True
        final_url = url
        if provider in {"shrtfly", "shrinkme"}:
            result = shorten_with_provider(provider, url, alias=sid, ad_type=1)
            if not result.get("ok"):
                await update.message.reply_text(
                    f"❌ {provider.title()} API failed: {result.get('error', 'unknown error')}",
                    reply_markup=admin_back(),
                )
                return True
            final_url = result["short_url"]
            # These APIs document link creation, not verified completion.
            # Keep reward at zero unless a compliant server-to-server reward
            # mechanism is separately documented/configured.
            reward = 0
        if not register_shortlink(sid, name, final_url, reward=reward, cooldown=cooldown):
            await update.message.reply_text("❌ Could not save shortlink.", reply_markup=admin_back())
            return True
        context.user_data.clear()
        await update.message.reply_text(
            f"✅ Shortlink `{sid}` saved ({provider}).\n\n"
            + ("🔗 Provider API generated the short URL. Reward remains 0 because the documented API does not provide verified completion callbacks." if provider in {"shrtfly", "shrinkme"} else "🔗 Manual/provider URL saved."),
            reply_markup=admin_back(),
            parse_mode="Markdown",
        )
        return True

    if action == "broadcast_specific_message":

        target_id = (
            context.user_data.get(
                "admin_target"
            )
        )

        message_text = (
            update.message.text or ""
        )

        try:

            await context.bot.send_message(

                chat_id=target_id,

                text=message_text,
            )

            result_text = (
                "📢 BROADCAST COMPLETE\n\n"
                "✅ Message sent successfully."
            )

        except Exception as error:

            logger.warning(

                "Specific broadcast failed | "
                "user=%s | error=%s",

                target_id,
                error,
            )

            result_text = (
                "📢 BROADCAST FAILED\n\n"
                "❌ Could not send the message."
            )

        context.user_data.clear()

        await update.message.reply_text(

            result_text,

            reply_markup=admin_back(),

            parse_mode="Markdown",
        )

        return True
        # ==================================================
    # SETTINGS
    # ==================================================

    setting_map = {

        "set_daily":
            "daily_bonus",

        "set_group":
            "group_reward",

        "set_task_reward":
            "task_reward",

        "set_task_limit":
            "daily_task_limit",

        "set_spin_min":
            "spin_min",

        "set_spin_max":
            "spin_max",

        "set_spin_cd":
            "spin_cooldown",

        "set_lucky_min":
            "lucky_min",

        "set_lucky_max":
            "lucky_max",

        "set_ref_reward":
            "referral_reward",

        "set_ref_xp":
            "referral_xp",
    }

    if action in setting_map:

        try:

            value = int(text)

        except ValueError:

            await update.message.reply_text(
                "❌ Please send a number."
            )

            return True

        if value < 0:

            await update.message.reply_text(
                "❌ Value cannot be negative."
            )

            return True

        field = setting_map[
            action
        ]

        db["bot_settings"].update_one(

            {
                "_id": "main"
            },

            {
                "$set": {
                    field: value
                }
            },

            upsert=True,
        )

        context.user_data.clear()

        await update.message.reply_text(

            "✅ SETTING UPDATED\n\n"

            f"⚙️ {field} = {value}",

            reply_markup=admin_back(),

            parse_mode="Markdown",
        )

        return True

    # ==================================================
    # BROADCAST ALL / ACTIVE
    # ==================================================

    if action in (
        "broadcast_all",
        "broadcast_active",
    ):

        message_text = (
            update.message.text or ""
        )

        if action == "broadcast_all":

            cursor = users.find(
                {},
                {
                    "user_id": 1
                },
            )

        else:

            cursor = users.find(

                {
                    "last_login": {
                        "$gte": (
                            int(time.time())
                            - 86400
                        )
                    }
                },

                {
                    "user_id": 1
                },
            )

        success = 0
        failed = 0

        for user in cursor:

            target_id = user.get(
                "user_id"
            )

            if not target_id:
                continue

            try:

                await context.bot.send_message(

                    chat_id=target_id,

                    text=message_text,
                )

                success += 1

            except Exception as error:

                failed += 1

                logger.warning(

                    "Broadcast failed | "
                    "user=%s | error=%s",

                    target_id,
                    error,
                )

        context.user_data.clear()

        await update.message.reply_text(

            "📢 BROADCAST COMPLETE\n\n"

            f"✅ Success: {success}\n"
            f"❌ Failed: {failed}",

            reply_markup=admin_back(),

            parse_mode="Markdown",
        )

        return True

    return False
# ==================================================
# VIP PURCHASE ON/OFF
# ==================================================

async def admin_vip_toggle(
    update,
    context,
):
    query = update.callback_query

    if not query:
        return

    if not admin_only(query.from_user.id):
        await query.answer(
            "🚫 Admin only.",
            show_alert=True,
        )
        return

    try:
        current = is_vip_purchase_enabled()
        new_status = not current

        # Persist the setting directly as a small, atomic upsert.
        # This avoids failures caused by unrelated optional settings code.
        result = db["bot_settings"].update_one(
            {"_id": "main"},
            {"$set": {"vip_purchase_enabled": bool(new_status)}},
            upsert=True,
        )

        if not (result.acknowledged):
            await query.answer(
                "❌ Failed to change VIP status.",
                show_alert=True,
            )
            return

        status = "🟢 ON" if new_status else "🔴 OFF"

        try:
            await query.answer(f"VIP Purchase: {status}")
        except Exception:
            # The callback may already have been acknowledged by the
            # central callback router.
            pass

        await admin_panel(update, context)

    except Exception:
        logger.exception("VIP purchase toggle failed")
        try:
            await query.answer(
                "⚠️ VIP setting failed.",
                show_alert=True,
            )
        except Exception:
            pass
# ==================================================
# ADMIN CALLBACK ROUTER
# ==================================================

async def admin_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query or not query.from_user:
        return

    if not admin_only(query.from_user.id):
        await query.answer(
            "🚫 Admin only.",
            show_alert=True,
        )
        return

    data = query.data or ""

    try:
        await query.answer()
    except Exception:
        pass

    if data in ("admin", "admin_panel"):
        await admin_panel(update, context)
        return

    routes = {
        "admin_users": admin_users,
        "admin_find_user": admin_find_user,
        "admin_balance": admin_balance,
        "admin_ban": admin_ban,
        "admin_stats": admin_statistics,
        "admin_rewards": admin_rewards,
        "admin_tasks": admin_tasks,
        "admin_membership_payments": admin_membership_payments,
        "admin_add_task": admin_add_task,
        "admin_wheel": admin_wheel,
        "admin_lucky": admin_lucky,
        "admin_referral": admin_referral,
        "admin_ref_milestones": admin_ref_milestones,
        "admin_add_ref_milestone": admin_add_ref_milestone,
        "admin_del_ref_milestone": admin_del_ref_milestone,
        "admin_settings": admin_settings,
        "admin_broadcast": admin_broadcast,
        "admin_bc_all": admin_bc_all,
        "admin_bc_active": admin_bc_active,
        "admin_bc_specific": admin_bc_specific,
        "admin_set_daily": admin_set_daily,
        "admin_set_group": admin_set_group,
        "admin_set_task_reward": admin_set_task_reward,
        "admin_set_task_limit": admin_set_task_limit,
        "admin_set_spin_min": admin_set_spin_min,
        "admin_set_spin_max": admin_set_spin_max,
        "admin_set_spin_cd": admin_set_spin_cd,
        "admin_set_lucky_min": admin_set_lucky_min,
        "admin_set_lucky_max": admin_set_lucky_max,
        "admin_set_ref_reward": admin_set_ref_reward,
        "admin_set_ref_xp": admin_set_ref_xp,
        "admin_shortlinks": admin_shortlinks,
        "admin_add_shortlink": admin_add_shortlink,
        "admin_cpagrip_offers": admin_cpagrip_offers,
        "admin_cpagrip_refresh": admin_cpagrip_refresh,
        "admin_withdrawals": admin_withdrawals,
        "admin_vip_toggle": admin_vip_toggle,
        "admin_premium_on": admin_premium_on,
    }

    if data.startswith("admin_payment_view_"):
        await admin_payment_view(update, context); return
    if data.startswith("admin_payment_approve_"):
        await admin_payment_approve(update, context); return
    if data.startswith("admin_payment_reject_"):
        await admin_payment_reject(update, context); return
    if data.startswith("admin_task_toggle_"):
        await admin_task_toggle(update, context)
        return
    if data.startswith("admin_task_delete_"):
        await admin_task_delete(update, context)
        return

    handler = routes.get(data)
    if handler:
        await handler(update, context)
        return

    if data.startswith("admin_shortlink_toggle_"):
        await admin_shortlink_toggle(update, context)
        return

    if data.startswith("admin_shortlink_delete_"):
        await admin_shortlink_delete(update, context)
        return
    if data.startswith("admin_cpa_toggle_"):
        await admin_cpagrip_toggle(update, context)
        return

    if data.startswith("admin_cpa_delete_"):
        await admin_cpagrip_delete(update, context)
        return

    if data == "admin_toggle_maintenance":
        settings = db["bot_settings"].find_one({"_id": "main"}) or {}
        current = bool(settings.get("maintenance", False))
        db["bot_settings"].update_one(
            {"_id": "main"},
            {"$set": {"maintenance": not current}},
            upsert=True,
        )
        await admin_settings(update, context)
        return

    if data == "admin_toggle_notifications":
        settings = db["bot_settings"].find_one({"_id": "main"}) or {}
        current = bool(settings.get("notifications", True))
        db["bot_settings"].update_one(
            {"_id": "main"},
            {"$set": {"notifications": not current}},
            upsert=True,
        )
        await admin_settings(update, context)
        return

    if data.startswith("admin_withdraw_view_"):
        await admin_withdrawal_view(update, context)
        return

    if data.startswith("admin_withdraw_approve_"):
        await admin_withdrawal_approve(update, context)
        return

    if data.startswith("admin_withdraw_reject_"):
        await admin_withdrawal_reject(update, context)
        return

    if data.startswith("admin_premium_on_"):
        await admin_premium_on(update, context); return
    if data.startswith("admin_premium_off_"):
        await admin_premium_off(update, context); return
    if data.startswith("admin_vip_set_"):
        await admin_vip_set(update, context); return
    if data.startswith("admin_vip_off_"):
        await admin_vip_off(update, context); return
    if data.startswith("admin_bonus_add_"):
        await admin_bonus_add(update, context); return
    if data.startswith("admin_bonus_remove_"):
        await admin_bonus_remove(update, context); return

    prefixed_handlers = (
        ("admin_add_", admin_add_balance),
        ("admin_remove_", admin_remove_balance),
        ("admin_toggleban_", admin_toggle_ban),
    )

    for prefix_name, handler in prefixed_handlers:
        if data.startswith(prefix_name):
            try:
                int(data.replace(prefix_name, "", 1))
            except ValueError:
                await query.answer(
                    "❌ Invalid user ID.",
                    show_alert=True,
                )
                return

            await handler(update, context)
            return

    if data.startswith("admin_view_"):
        try:
            user_id = int(
                data.replace(
                    "admin_view_",
                    "",
                    1,
                )
            )
        except ValueError:
            await query.answer(
                "❌ Invalid user ID.",
                show_alert=True,
            )
            return

        await show_admin_user(
            update,
            context,
            user_id,
        )
        return

    await query.answer(
        "⚠️ Admin option not available.",
        show_alert=True,
            )

# ==================================================
# EXPORTS
# ==================================================
ADMIN_HANDLERS = {
    "admin": admin_panel,
    "admin_panel": admin_panel,
    "admin_callback": admin_callback,
    "admin_text_handler": admin_text_handler,
}# ==================================================
# CPAGRIP OFFER MANAGEMENT
# ==================================================

async def admin_cpagrip_offers(update, context):
    query = update.callback_query
    if not query or not admin_only(query.from_user.id):
        if query:
            await query.answer("🚫 Admin only.", show_alert=True)
        return
    await query.answer()
    # Use cached provider offers. A refresh happens when users open Offers.
    items = list(db["provider_offers"].find(
        {"provider": "cpagrip"}, {"_id": 0}
    ).sort("updated_at", -1).limit(30))
    disabled = {
        str(x.get("offer_id"))
        for x in db["provider_disabled_offers"].find(
            {"provider": "cpagrip"}, {"offer_id": 1}
        )
    }
    buttons = []
    for item in items:
        oid = str(item.get("offer_id", ""))
        if not oid:
            continue
        state = "🔴" if oid in disabled else "🟢"
        title = str(item.get("title", oid))[:25]
        buttons.append([
            InlineKeyboardButton(
                f"{state} {title}",
                callback_data=f"admin_cpa_toggle_{oid}"[:64],
            ),
            InlineKeyboardButton(
                "🗑",
                callback_data=f"admin_cpa_delete_{oid}"[:64],
            ),
        ])
    if not buttons:
        buttons.append([InlineKeyboardButton("🔄 Refresh from CPAGrip", callback_data="admin_cpagrip_refresh")])
    buttons.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin")])
    await query.edit_message_text(
        "🎁 **CPAGrip Offer Management**\n\n"
        "🟢 = visible to users\n"
        "🔴 = hidden by admin\n\n"
        "Delete removes the cached offer. A later provider sync may add it again unless the provider no longer supplies it.",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )


async def admin_cpagrip_refresh(update, context):
    query = update.callback_query
    if not query or not admin_only(query.from_user.id):
        if query:
            await query.answer("🚫 Admin only.", show_alert=True)
        return
    await query.answer()
    # The provider adapter needs a real endpoint in Render; refresh is
    # intentionally explicit to avoid API calls on every admin page open.
    from provider_integrations import sync_cpagrip_offers
    count = sync_cpagrip_offers(query.from_user.id)
    await query.answer(f"Fetched {count} offer(s).")
    await admin_cpagrip_offers(update, context)


async def admin_cpagrip_toggle(update, context):
    query = update.callback_query
    if not query or not admin_only(query.from_user.id):
        if query:
            await query.answer("🚫 Admin only.", show_alert=True)
        return
    oid = str(query.data).replace("admin_cpa_toggle_", "", 1)
    doc = db["provider_disabled_offers"].find_one({"provider": "cpagrip", "offer_id": oid})
    new_enabled = doc is not None
    if set_provider_offer_enabled("cpagrip", oid, new_enabled):
        await query.answer("🟢 Enabled" if new_enabled else "🔴 Disabled")
    else:
        await query.answer("Update failed.", show_alert=True)
    await admin_cpagrip_offers(update, context)


async def admin_cpagrip_delete(update, context):
    query = update.callback_query
    if not query or not admin_only(query.from_user.id):
        if query:
            await query.answer("🚫 Admin only.", show_alert=True)
        return
    oid = str(query.data).replace("admin_cpa_delete_", "", 1)
    delete_provider_offer("cpagrip", oid)
    await query.answer("🗑 Deleted")
    await admin_cpagrip_offers(update, context)



