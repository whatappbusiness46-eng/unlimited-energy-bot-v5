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
    provider_events,
)

from payments import pending as pending_payments, get_payment, approve_payment, reject_payment
from premium import grant_premium, revoke_premium
from vip import grant_vip, remove_vip, is_valid_vip_level

from tasks import (
    get_tasks, get_task, register_task, set_task_enabled, delete_task,
    approve_task_completion, reject_task_completion,
    completions_collection,
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
    maintenance_reset_member_wallets,
    maintenance_cleanup_old_data,
    maintenance_optimize_indexes,
    get_withdrawal_settings,
    points_to_bdt,
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
                "🧹 Database / Maintenance",
                callback_data="admin_maintenance",
            )
        ],

        [InlineKeyboardButton("📨 VIP Task Approvals", callback_data="admin_task_pending")],

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
                "💵 Provider Payouts",
                callback_data="admin_provider_payouts",
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
        "Example: `sl1|Example|https://example.com/go|0|86400`",
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
        "Example: `sl1|Example|https://example.com/go|0|86400`",
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
        item_bdt = item.get("bdt_amount")
        if item_bdt is None:
            item_bdt = points_to_bdt(amount, item.get("withdrawal_rate_points_per_100_bdt"))

        buttons.append(
            [
                InlineKeyboardButton(
                    f"💸 {withdrawal_id} • {amount} pts • ৳{float(item_bdt):g}",
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
    rate = withdrawal.get("withdrawal_rate_points_per_100_bdt")
    bdt_amount = withdrawal.get("bdt_amount")
    if bdt_amount is None:
        bdt_amount = points_to_bdt(amount, rate)

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
        f"💵 Payout: ৳{float(bdt_amount):g}\n"
        f"💱 Rate: {rate or get_withdrawal_settings()['points_per_100_bdt']} Points = ৳100\n"
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
        rate = withdrawal.get("withdrawal_rate_points_per_100_bdt")
        bdt_amount = withdrawal.get("bdt_amount")
        if bdt_amount is None:
            bdt_amount = points_to_bdt(amount, rate)
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "🟢 **WITHDRAWAL APPROVED**\n\n"
                    f"🆔 ID: `{withdrawal_id}`\n"
                    f"💰 Amount: {amount} Points\n"
                    f"💵 Payout: ৳{float(bdt_amount):g}\n\n"
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

async def admin_task_pending(update, context):
    query = update.callback_query
    if not query or not admin_only(query.from_user.id):
        if query: await query.answer("🚫 Admin only.", show_alert=True)
        return
    await query.answer()
    pending = list(completions_collection.find({"status": "pending"}).sort("created_at", 1).limit(30))
    buttons = []
    lines = ["📨 **VIP TASK APPROVALS**", ""]
    if not pending:
        lines.append("No pending VIP task submissions.")
    else:
        lines.append(f"Pending: {len(pending)}")
        lines.append("")
        for item in pending:
            uid = int(item.get("user_id", 0)); tid = str(item.get("task_id", ""))
            task = get_task(tid) if 'get_task' in globals() else None
            title = str(task.get("title", tid) if task else tid)[:32]
            lines.append(f"👤 `{uid}` — {title}")
            buttons.append([
                InlineKeyboardButton("🟢 Approve", callback_data=f"admin_task_approve_{uid}_{tid}"),
                InlineKeyboardButton("🔴 Reject", callback_data=f"admin_task_reject_{uid}_{tid}"),
            ])
    buttons.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin")])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")


async def admin_task_approve(update, context):
    q = update.callback_query
    if not q or not admin_only(q.from_user.id): return
    raw = str(q.data).replace("admin_task_approve_", "", 1)
    try: uid, tid = raw.split("_", 1); uid = int(uid)
    except ValueError:
        await q.answer("Invalid request.", show_alert=True); return
    ok, msg = approve_task_completion(uid, tid, q.from_user.id)
    await q.answer(msg, show_alert=not ok)
    if ok:
        try: await context.bot.send_message(uid, f"✅ **VIP Task Approved!**\n\n🎯 Task: {get_task(tid).get('title', tid)}\n💰 Reward credited successfully.", parse_mode="Markdown")
        except Exception: pass
    await admin_task_pending(update, context)


async def admin_task_reject(update, context):
    q = update.callback_query
    if not q or not admin_only(q.from_user.id): return
    raw = str(q.data).replace("admin_task_reject_", "", 1)
    try: uid, tid = raw.split("_", 1); uid = int(uid)
    except ValueError:
        await q.answer("Invalid request.", show_alert=True); return
    ok, msg = reject_task_completion(uid, tid, q.from_user.id, "Rejected by Admin")
    await q.answer(msg, show_alert=not ok)
    if ok:
        try: await context.bot.send_message(uid, f"❌ **VIP Task Rejected**\n\n🎯 Task: {get_task(tid).get('title', tid)}\nNo reward was credited.", parse_mode="Markdown")
        except Exception: pass
    await admin_task_pending(update, context)


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
        buttons.append([InlineKeyboardButton(f"{status} {title} | +{t.get('reward',0)} | {str(t.get("audience","normal")).upper()}", callback_data=f"admin_task_toggle_{tid}")])
        buttons.append([
            InlineKeyboardButton(action, callback_data=f"admin_task_toggle_{tid}"),
            InlineKeyboardButton("🗑 Delete", callback_data=f"admin_task_delete_{tid}"),
        ])
    buttons.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin")])
    await query.edit_message_text(
        "🎯 **TASK MANAGEMENT**\n\n"
        f"Configured: {len(items)}\n\n"
        "Add format:\n`id|title|description|url|reward|cooldown|xp|energy|task_type|audience|verification`\n\n"
        "Example:\n`task1|Join Channel|Join our channel|https://t.me/example|50|86400|5|1|telegram|normal|telegram_join`\n\n"
        "🟢 visible/active · 🔴 disabled",
        reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

async def admin_add_task(update, context):
    query=update.callback_query
    if not query or not admin_only(query.from_user.id):
        if query: await query.answer("🚫 Admin only.", show_alert=True)
        return
    await query.answer(); context.user_data["admin_action"]="add_task"
    await query.edit_message_text(
        "🎯 **ADD TASK**\n\nSend one line:\n`id|title|description|url|reward|cooldown|xp|energy|task_type|audience|verification`\n\n"
        "Verification is controlled by Render ENV: `TASK_VERIFICATION_ENABLED=false` (default) or `true`.\nUse `-` for no URL/description. Example:\n`task1|Join Channel|Join our channel|https://t.me/example|50|86400|5|1|telegram|normal|telegram_join`",
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
    withdraw_settings = get_withdrawal_settings()
    withdraw_rate = withdraw_settings["points_per_100_bdt"]
    withdraw_min = withdraw_settings["min_points"]
    withdraw_step = withdraw_settings["step_points"]

    await query.edit_message_text(

        "⚙️ **BOT SETTINGS**\n\n"

        f"🔧 Maintenance: "
        f"{'ON' if maintenance else 'OFF'}\n"

        f"🔔 Notifications: "
        f"{'ON' if notifications else 'OFF'}\n\n"
        "💸 **WITHDRAWAL CONTROL**\n"
        f"💱 Rate: {withdraw_rate} Points = ৳100\n"
        f"📌 Minimum: {withdraw_min} Points = ৳{points_to_bdt(withdraw_min, withdraw_rate):g}\n"
        f"🔢 Step: {withdraw_step} Points\n"
        "Examples: 1000 Points = ৳100 • 1500 Points = ৳150",

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
                        "💸 Withdrawal Settings",
                        callback_data="admin_withdraw_settings",
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
# WITHDRAWAL SETTINGS
# ==================================================

async def admin_withdraw_settings(update, context):
    query = update.callback_query
    if not query or not admin_only(query.from_user.id):
        if query:
            await query.answer("🚫 Admin only.", show_alert=True)
        return
    await query.answer()
    settings = get_withdrawal_settings()
    rate = settings["points_per_100_bdt"]
    minimum = settings["min_points"]
    step = settings["step_points"]
    await query.edit_message_text(
        "💸 **WITHDRAWAL CONTROL CENTER**\n\n"
        f"💱 Conversion Rate: **{rate} Points = ৳100**\n"
        f"📌 Minimum Withdrawal: **{minimum} Points = ৳{points_to_bdt(minimum, rate):g}**\n"
        f"🔢 Allowed Step: **{step} Points**\n\n"
        "✅ Users can withdraw 1000, 1500, 2000, 2500... when the step is 500.\n"
        "❌ Arbitrary amounts like 1005 or 1010 are rejected.\n\n"
        "This setting controls the Points → BDT conversion used for new withdrawal requests.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💱 Change Rate", callback_data="admin_set_withdraw_rate")],
            [InlineKeyboardButton("📌 Change Minimum", callback_data="admin_set_withdraw_min")],
            [InlineKeyboardButton("🔢 Change Step", callback_data="admin_set_withdraw_step")],
            [InlineKeyboardButton("🔙 Bot Settings", callback_data="admin_settings")],
        ]),
        parse_mode="Markdown",
    )


async def admin_set_withdraw_rate(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data["admin_action"] = "set_withdraw_rate"
    await query.edit_message_text(
        "💱 **CHANGE WITHDRAWAL RATE**\n\n"
        "Send how many Points should equal ৳100.\n\n"
        "Example: `1000` → 1000 Points = ৳100\n"
        "Example: `1200` → 1200 Points = ৳100",
        reply_markup=admin_back(), parse_mode="Markdown"
    )


async def admin_set_withdraw_min(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data["admin_action"] = "set_withdraw_min"
    await query.edit_message_text(
        "📌 **CHANGE MINIMUM WITHDRAWAL**\n\n"
        "Send the minimum Points required for withdrawal.\n"
        "Example: `1000`",
        reply_markup=admin_back(), parse_mode="Markdown"
    )


async def admin_set_withdraw_step(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data["admin_action"] = "set_withdraw_step"
    await query.edit_message_text(
        "🔢 **CHANGE WITHDRAWAL STEP**\n\n"
        "Send the Points step allowed for withdrawal amounts.\n\n"
        "Example: `500` allows 1000, 1500, 2000, 2500...",
        reply_markup=admin_back(), parse_mode="Markdown"
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
        bdt_amount = withdrawal.get("bdt_amount")
        if bdt_amount is None:
            bdt_amount = points_to_bdt(amount, withdrawal.get("withdrawal_rate_points_per_100_bdt"))

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
                    f"💰 Amount: {amount} Points = ৳{float(bdt_amount):g}\n\n"

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
            f"💰 Refunded: {amount} Points = ৳{float(bdt_amount):g}\n"
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
        parts = [x.strip() for x in text.split("|")]
        if len(parts) not in (8, 11):
            await update.message.reply_text(
                "❌ Format: id|title|description|url|reward|cooldown|xp|energy|task_type|audience|verification",
                reply_markup=admin_back(),
            )
            return True

        tid, title, desc, url, reward_text, cooldown_text, xp_text, energy_text = parts[:8]
        task_type, audience, verification = (parts[8:11] if len(parts) == 11 else ("telegram", "normal", "telegram_join"))
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
                tid, title, desc, reward, url, cooldown, True, xp, energy,
                task_type=task_type, audience=audience, verification_method=verification
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

    if action == "edit_cpa_offer_name":
        oid = str(context.user_data.get("cpa_offer_id", "")).strip()
        name = text.strip()
        if not oid or not name:
            await update.message.reply_text("❌ Offer name cannot be empty.", reply_markup=admin_back())
            return True
        db["provider_offers"].update_one(
            {"provider": "cpagrip", "offer_id": oid},
            {"$set": {"custom_title": name}}
        )
        context.user_data.clear()
        await update.message.reply_text("✅ Offer name updated.", reply_markup=admin_back())
        return True

    if action == "edit_cpa_offer_reward":
        oid = str(context.user_data.get("cpa_offer_id", "")).strip()
        try:
            reward = int(text.strip())
            if reward < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Send a whole-number points value (0 or higher).", reply_markup=admin_back())
            return True
        if not oid:
            await update.message.reply_text("❌ Offer not found.", reply_markup=admin_back())
            return True
        db["provider_offers"].update_one(
            {"provider": "cpagrip", "offer_id": oid},
            {"$set": {"custom_reward_points": reward, "custom_reward_locked": True}}
        )
        context.user_data.clear()
        await update.message.reply_text(f"✅ Member reward set to {reward} points.", reply_markup=admin_back())
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
            # Shortlink providers used here monetize publisher traffic; member incentives
            # for clicks are not assumed to be allowed. Keep member reward at zero.
            reward = 0
            cooldown = int(cooldown_text)
        except ValueError:
            await update.message.reply_text("❌ Reward and cooldown must be numbers.", reply_markup=admin_back())
            return True
        if reward < 0 or cooldown < 0 or not sid or not url:
            await update.message.reply_text("❌ Invalid shortlink values.", reply_markup=admin_back())
            return True
        final_url = url
        if not register_shortlink(sid, name, final_url, reward=reward, cooldown=cooldown):
            await update.message.reply_text("❌ Could not save shortlink.", reply_markup=admin_back())
            return True
        context.user_data.clear()
        await update.message.reply_text(
            f"✅ Shortlink `{sid}` saved ({provider}).\n\n"
            + "🔗 Member reward is disabled; use CPA/task systems for verified member earnings.",
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
    # WITHDRAWAL SETTINGS
    # ==================================================

    if action in ("set_withdraw_rate", "set_withdraw_min", "set_withdraw_step"):
        try:
            value = int(text)
        except ValueError:
            await update.message.reply_text("❌ Please send a whole number.", reply_markup=admin_back())
            return True

        if value <= 0:
            await update.message.reply_text("❌ Value must be greater than 0.", reply_markup=admin_back())
            return True

        current = get_withdrawal_settings()
        if action == "set_withdraw_rate":
            field = "withdraw_points_per_100_bdt"
            label = "Conversion Rate"
        elif action == "set_withdraw_min":
            field = "withdraw_min_points"
            label = "Minimum Withdrawal"
        else:
            field = "withdraw_step_points"
            label = "Withdrawal Step"

        if action == "set_withdraw_step" and value > 100000000:
            await update.message.reply_text("❌ Step is too large.", reply_markup=admin_back())
            return True

        if action == "set_withdraw_min" and value > 100000000:
            await update.message.reply_text("❌ Minimum is too large.", reply_markup=admin_back())
            return True

        if action == "set_withdraw_rate" and value > 100000000:
            await update.message.reply_text("❌ Rate is too large.", reply_markup=admin_back())
            return True

        db["bot_settings"].update_one(
            {"_id": "main"},
            {"$set": {field: value}},
            upsert=True,
        )
        context.user_data.clear()
        updated = get_withdrawal_settings()
        await update.message.reply_text(
            "✅ **WITHDRAWAL SETTING UPDATED**\n\n"
            f"💸 {label}: `{value}`\n"
            f"💱 Current rate: **{updated['points_per_100_bdt']} Points = ৳100**\n"
            f"📌 Minimum: **{updated['min_points']} Points**\n"
            f"🔢 Step: **{updated['step_points']} Points**\n\n"
            "Example: `1000 Points = ৳100` • `1500 Points = ৳150` when the rate is 1000 Points = ৳100.",
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
async def admin_maintenance(update, context):
    q = update.callback_query
    if not q or not admin_only(q.from_user.id):
        if q: await q.answer("🚫 Admin only.", show_alert=True)
        return
    await q.answer()
    text = (
        "🧹 **DATABASE / MAINTENANCE**\n\n"
        "Safe tools for slow-bot situations.\n\n"
        "🟢 **Optimize indexes** — improves common DB lookups.\n"
        "🧹 **Clean old logs/stats** — removes only disposable operational data.\n"
        "⚠️ **Reset member wallets** — sets Balance, Bonus Balance and Premium Balance to 0.\n"
        "☢️ **Factory reset** — permanently clears member/activity/earning/payment history while keeping bot configuration, tasks, shortlinks, Force Join and provider settings.\n\n"
        "👥 User accounts, task definitions, shortlink definitions and bot/provider configuration are preserved unless the factory reset is explicitly confirmed."
    )
    buttons = [
        [InlineKeyboardButton("⚡ Optimize DB Indexes", callback_data="admin_maintenance_indexes")],
        [InlineKeyboardButton("🧹 Clean Old Logs/Stats", callback_data="admin_maintenance_clean")],
        [InlineKeyboardButton("⚠️ Reset ALL Member Wallets", callback_data="admin_maintenance_reset_confirm")],
        [InlineKeyboardButton("☢️ FACTORY RESET — DELETE ALL DATA", callback_data="admin_factory_reset_confirm")],
        [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin")],
    ]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")


async def admin_maintenance_reset_confirm(update, context):
    q = update.callback_query
    if not q or not admin_only(q.from_user.id): return
    await q.answer()
    buttons = [
        [InlineKeyboardButton("❌ Cancel", callback_data="admin_maintenance")],
        [InlineKeyboardButton("⚠️ YES, RESET WALLETS", callback_data="admin_maintenance_reset")],
    ]
    await q.edit_message_text(
        "⚠️ **FINAL CONFIRMATION**\n\nThis will set every member's `balance`, `bonus_balance`, and `premium_balance` to **0**.\n\nIt will NOT delete users or task/payment/withdrawal/provider history.\n\nContinue?",
        reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown"
    )


async def admin_maintenance_reset(update, context):
    q = update.callback_query
    if not q or not admin_only(q.from_user.id): return
    try:
        changed = maintenance_reset_member_wallets()
        await q.answer(f"Reset done: {changed} member records.", show_alert=True)
        await admin_maintenance(update, context)
    except Exception:
        logger.exception("Member wallet reset failed")
        await q.answer("❌ Wallet reset failed.", show_alert=True)


# Data collections intentionally cleared by the factory reset.
# Configuration collections (bot_settings, tasks, shortlinks, provider_disabled_offers,
# and provider_offers) are preserved so the bot does not need to be configured again.
_FACTORY_RESET_COLLECTIONS = (
    "users",
    "transactions",
    "withdrawals",
    "membership_payments",
    "security_logs",
    "daily_statistics",
    "task_completions",
    "provider_events",
    "offerwall_task_proofs",
    "offerwall_task_submissions",
    "referral_claims",
    "referral_milestone_claims",
)


async def admin_factory_reset_confirm(update, context):
    q = update.callback_query
    if not q or not admin_only(q.from_user.id):
        if q:
            await q.answer("🚫 Admin only.", show_alert=True)
        return
    await q.answer()
    buttons = [
        [InlineKeyboardButton("❌ Cancel", callback_data="admin_maintenance")],
        [InlineKeyboardButton("☢️ YES, START FRESH", callback_data="admin_factory_reset")],
    ]
    await q.edit_message_text(
        "☢️ **FACTORY RESET — FINAL CONFIRMATION**\n\n"
        "This permanently deletes **member accounts and all member/activity/earning/payment history** from the database.\n\n"
        "It clears:\n"
        "• Users / balances / VIP & premium state\n"
        "• Transactions / withdrawals / membership payments\n"
        "• Task completion history\n"
        "• Provider conversion/event history\n"
        "• Offerwall task submissions & proof records\n"
        "• Referral claim history\n"
        "• Security logs & daily statistics\n\n"
        "✅ Preserved: Admin ID/config, Force Join, bot settings, configured tasks, shortlinks, provider settings and offer configuration.\n\n"
        "**This cannot be undone. Continue?**",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )


async def admin_factory_reset(update, context):
    q = update.callback_query
    if not q or not admin_only(q.from_user.id):
        if q:
            await q.answer("🚫 Admin only.", show_alert=True)
        return
    try:
        counts = {}
        for name in _FACTORY_RESET_COLLECTIONS:
            result = db[name].delete_many({})
            counts[name] = int(getattr(result, "deleted_count", 0))

        total = sum(counts.values())
        await q.answer("☢️ Factory reset complete.", show_alert=True)
        await q.edit_message_text(
            "☢️ **FACTORY RESET COMPLETE**\n\n"
            f"Deleted database records: **{total}**\n\n"
            "✅ Member accounts/history cleared.\n"
            "✅ Provider conversion history cleared.\n"
            "✅ Payment/withdrawal history cleared.\n"
            "✅ Referral/task activity history cleared.\n\n"
            "🔒 Bot configuration, Force Join, configured tasks, shortlinks and provider settings were preserved.\n\n"
            "The bot is now ready to start fresh with the next user interaction.",
            reply_markup=admin_back(),
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("Factory reset failed")
        await q.answer("❌ Factory reset failed. No further action was taken.", show_alert=True)


async def admin_maintenance_clean(update, context):
    q = update.callback_query
    if not q or not admin_only(q.from_user.id): return
    try:
        result = maintenance_cleanup_old_data(30, 90)
        await q.answer("🧹 Old disposable data cleaned.", show_alert=True)
        await q.edit_message_text(
            "🧹 **CLEANUP COMPLETE**\n\n"
            f"Security logs removed: {result['security_logs']}\n"
            f"Old daily statistics removed: {result['daily_statistics']}\n\n"
            "Member accounts, balances, task history, withdrawals, payments and provider events were preserved.",
            reply_markup=admin_back(), parse_mode="Markdown"
        )
    except Exception:
        logger.exception("Maintenance cleanup failed")
        await q.answer("❌ Cleanup failed.", show_alert=True)


async def admin_maintenance_indexes(update, context):
    q = update.callback_query
    if not q or not admin_only(q.from_user.id): return
    try:
        ok = maintenance_optimize_indexes()
        await q.answer("⚡ DB indexes optimized." if ok else "⚠️ Some indexes could not be optimized.", show_alert=True)
        await admin_maintenance(update, context)
    except Exception:
        logger.exception("Index optimization failed")
        await q.answer("❌ Index optimization failed.", show_alert=True)


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
        "admin_maintenance": admin_maintenance,
        "admin_tasks": admin_tasks,
        "admin_task_pending": admin_task_pending,
        "admin_membership_payments": admin_membership_payments,
        "admin_add_task": admin_add_task,
        "admin_wheel": admin_wheel,
        "admin_lucky": admin_lucky,
        "admin_referral": admin_referral,
        "admin_ref_milestones": admin_ref_milestones,
        "admin_add_ref_milestone": admin_add_ref_milestone,
        "admin_del_ref_milestone": admin_del_ref_milestone,
        "admin_settings": admin_settings,
        "admin_withdraw_settings": admin_withdraw_settings,
        "admin_set_withdraw_rate": admin_set_withdraw_rate,
        "admin_set_withdraw_min": admin_set_withdraw_min,
        "admin_set_withdraw_step": admin_set_withdraw_step,
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
        "admin_provider_payouts": admin_provider_payouts,
        "admin_provider_payouts_clear": admin_provider_payouts_clear,
        "admin_withdrawals": admin_withdrawals,
        "admin_vip_toggle": admin_vip_toggle,
        "admin_premium_on": admin_premium_on,
    }

    if data == "admin_maintenance_reset_confirm":
        await admin_maintenance_reset_confirm(update, context); return
    if data == "admin_maintenance_reset":
        await admin_maintenance_reset(update, context); return
    if data == "admin_factory_reset_confirm":
        await admin_factory_reset_confirm(update, context); return
    if data == "admin_factory_reset":
        await admin_factory_reset(update, context); return
    if data == "admin_maintenance_clean":
        await admin_maintenance_clean(update, context); return
    if data == "admin_maintenance_indexes":
        await admin_maintenance_indexes(update, context); return

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
    if data.startswith("admin_task_approve_"):
        await admin_task_approve(update, context)
        return
    if data.startswith("admin_task_reject_"):
        await admin_task_reject(update, context)
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
    if data.startswith("admin_cpa_name_"):
        await admin_cpagrip_edit_name(update, context)
        return
    if data.startswith("admin_cpa_reward_"):
        await admin_cpagrip_edit_reward(update, context)
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
# PROVIDER PAYOUTS / CONVERSIONS
# ==================================================

async def admin_provider_payouts_clear(update, context):
    query = update.callback_query
    if not query or not admin_only(query.from_user.id):
        if query:
            await query.answer("🚫 Admin only.", show_alert=True)
        return
    await query.answer("🗑 Latest list cleared.")
    try:
        result = provider_events.update_many({"admin_hidden": {"$ne": True}}, {"$set": {"admin_hidden": True, "admin_hidden_at": int(time.time())}})
        await query.edit_message_text(
            f"✅ Cleared {int(result.modified_count)} conversion(s) from the admin latest list.\n\n"
            "Provider event ledger was preserved, so duplicate protection and reversal handling remain safe.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💵 Provider Payouts", callback_data="admin_provider_payouts")], [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin")]]),
        )
    except Exception:
        logger.exception("Provider payout clear failed")
        await query.edit_message_text("❌ Could not clear the latest conversion list.", reply_markup=admin_back())


async def admin_provider_payouts(update, context):
    query = update.callback_query
    if not query or not admin_only(query.from_user.id):
        if query:
            await query.answer("🚫 Admin only.", show_alert=True)
        return

    await query.answer()

    try:
        rows = list(provider_events.find({"admin_hidden": {"$ne": True}}, {"_id": 0}).sort("received_at", -1).limit(50))
        stats = {}
        for provider in ("offerwallme", "cpagrip"):
            items = [r for r in rows if str(r.get("provider", "")).lower() == provider]
            # Use all stored events for totals, not just the latest 25.
            all_items = list(provider_events.find({"provider": provider}, {"_id": 0}))
            active = [r for r in all_items if str(r.get("status", "1")) not in {"2", "reversed", "chargeback", "reject", "rejected"}]
            try:
                provider_total = sum(float(r.get("reward_raw", 0) or 0) for r in active)
            except (TypeError, ValueError):
                provider_total = 0.0
            if provider == "offerwallme":
                # Historical Offerwall.me events may contain the old oversized
                # credited-point value. Recalculate the member reward from the
                # stored provider reward using the current placement-currency
                # rules so the admin total remains accurate.
                try:
                    from provider_integrations import _offerwallme_reward_points
                    user_points = sum(
                        _offerwallme_reward_points(r.get("reward_raw", 0), r.get("user_id"))
                        for r in active
                    )
                except Exception:
                    logger.exception("Offerwall.me payout total recalculation failed")
                    user_points = sum(int(r.get("points", 0) or 0) for r in active)
            else:
                user_points = sum(int(r.get("points", 0) or 0) for r in active)
            stats[provider] = (len(active), provider_total, user_points)

        ow_count, ow_total, ow_points = stats["offerwallme"]
        cp_count, cp_total, cp_points = stats["cpagrip"]

        text = (
            "💵 **PROVIDER PAYOUTS**\n\n"
            "This section is **admin-only**. It shows the real provider payout, offer name, and the automatically calculated member reward.\n\n"
            "🟣 **Offerwall.me**\n"
            f"• Conversions: `{ow_count}`\n"
            f"• Provider reward total (placement currency): `{ow_total:g}`\n"
            f"• Estimated publisher USD: `${_admin_offerwall_usd(ow_total):.2f}`\n"
            f"• Member points credited: `{ow_points}`\n"
            f"• User reward share: `{_admin_env('OFFERWALLME_USER_REWARD_PERCENT', '40')}%`\n"
            f"• Reward unit: `{_admin_env('OFFERWALLME_REWARD_UNIT', 'points')}`\n"
            f"• Placement currency per USD: `{_admin_env('OFFERWALLME_CURRENCY_PER_USD', '200')}`\n\n"
            "🟠 **CPAGrip**\n"
            f"• Conversions: `{cp_count}`\n"
            f"• Provider payout total (USD): `${cp_total:.2f}`\n"
            f"• Member points credited: `{cp_points}`\n"
            f"• User reward share: `{_admin_env('CPAGRIP_USER_REWARD_PERCENT', '40')}%`\n"
            f"• Points per USD: `{_admin_env('REWARD_POINTS_PER_USD', '1000')}`\n\n"
            "🎁 **Current CPAGrip offers / real payout**\n"
        )

        live_cpagrip = list(db["provider_offers"].find(
            {"provider": "cpagrip"},
            {"_id": 0, "offer_id": 1, "title": 1, "custom_title": 1, "provider_reward": 1, "custom_reward_points": 1, "custom_reward_locked": 1},
        ).sort("updated_at", -1).limit(10))
        if live_cpagrip:
            for item in live_cpagrip:
                title = str(item.get("custom_title") or item.get("title") or "Offer")[:36]
                payout = float(item.get("provider_reward") or 0)
                auto_points = (int(item.get("custom_reward_points") or 0) if item.get("custom_reward_locked") else int(__import__("provider_integrations")._reward_points(payout)))
                text += f"• `{title}` — payout `${payout:.2f}` → member `+{auto_points}` pts\n"
        else:
            text += "No cached CPAGrip offers found.\n"

        text += "\n📋 **Latest conversions**\n"

        if not rows:
            text += "No provider conversions recorded yet."
        else:
            for r in rows[:50]:
                provider = str(r.get("provider", "?")).upper()[:3]
                event_id = str(r.get("event_id", ""))[:10]
                user_id = str(r.get("user_id", ""))
                reward = str(r.get("reward_raw", r.get("provider_reward", "0")))[:12]
                if str(r.get("provider", "")).lower() == "offerwallme":
                    try:
                        from provider_integrations import _offerwallme_reward_points
                        points = _offerwallme_reward_points(r.get("reward_raw", 0), r.get("user_id"))
                    except Exception:
                        points = int(r.get("points", 0) or 0)
                else:
                    points = int(r.get("points", 0) or 0)
                status = str(r.get("status", "1"))[:8]
                offer = str(r.get("offer_title") or r.get("params", {}).get("offer_name") or r.get("params", {}).get("offerName") or "Unknown offer")[:28]
                text += f"• `{provider}|U:{user_id}|{offer}|R:${reward}|+{points}|{status}|{event_id}`\n"

        await query.edit_message_text(
            text[:4000],
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh", callback_data="admin_provider_payouts"), InlineKeyboardButton("🗑 Clear Latest List", callback_data="admin_provider_payouts_clear")],
                [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin")],
            ]),
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("Admin provider payout view failed")
        await query.edit_message_text(
            "❌ **Provider payout data unavailable right now.**",
            reply_markup=admin_back(),
            parse_mode="Markdown",
        )


def _admin_env(name, default=""):
    import os
    return os.getenv(name, default)


def _admin_offerwall_usd(reward_total):
    try:
        unit = _admin_env("OFFERWALLME_REWARD_UNIT", "points").strip().lower()
        value = float(reward_total or 0)
        if unit in {"usd", "dollar", "dollars"}:
            return value
        rate = float(_admin_env("OFFERWALLME_CURRENCY_PER_USD", "200"))
        return value / rate if rate > 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


# ==================================================
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
        title = str(item.get("custom_title") or item.get("title", oid))[:22]
        reward = (int(item.get("custom_reward_points") or 0) if item.get("custom_reward_locked") else 0)
        buttons.append([
            InlineKeyboardButton(f"{state} {title}", callback_data=f"admin_cpa_toggle_{oid}"[:64]),
            InlineKeyboardButton("✏️ Name", callback_data=f"admin_cpa_name_{oid}"[:64]),
            InlineKeyboardButton("💰 Points", callback_data=f"admin_cpa_reward_{oid}"[:64]),
            InlineKeyboardButton("🗑", callback_data=f"admin_cpa_delete_{oid}"[:64]),
        ])
    if not buttons:
        buttons.append([InlineKeyboardButton("🔄 Refresh from CPAGrip", callback_data="admin_cpagrip_refresh")])
    buttons.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin")])
    await query.edit_message_text(
        "🎁 **Special Offer Management**\n\n"
        "✏️ Name and 💰 Points can be customized per offer.\n"
        "🟢 = visible to users\n"
        "🔴 = hidden by admin\n\n"
        "Delete removes the cached offer. A later provider sync may add it again unless the provider no longer supplies it.",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )


async def admin_cpagrip_edit_name(update, context):
    q = update.callback_query
    if not q or not admin_only(q.from_user.id):
        return
    oid = q.data[len("admin_cpa_name_"):]
    context.user_data["admin_action"] = "edit_cpa_offer_name"
    context.user_data["cpa_offer_id"] = oid
    await q.answer()
    await q.edit_message_text("✏️ Send the new offer name:", reply_markup=admin_back())


async def admin_cpagrip_edit_reward(update, context):
    q = update.callback_query
    if not q or not admin_only(q.from_user.id):
        return
    oid = q.data[len("admin_cpa_reward_"):]
    context.user_data["admin_action"] = "edit_cpa_offer_reward"
    context.user_data["cpa_offer_id"] = oid
    await q.answer()
    await q.edit_message_text("💰 Send the new member reward points (any positive number):", reply_markup=admin_back())


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



