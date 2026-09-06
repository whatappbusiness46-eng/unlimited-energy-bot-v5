import logging
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_user, update_user, add_balance, add_activity, db
from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)
DEFAULT_REWARD = 0  # No per-referral points; rewards are milestone-only.
DEFAULT_XP = 10
DEFAULT_MILESTONES = {5: 50, 10: 100, 25: 250, 50: 500, 100: 1000}
referral_claims = db["referral_claims"]
referral_milestone_claims = db["referral_milestone_claims"]
try:
    referral_claims.create_index("new_user_id", unique=True, name="referral_new_user_unique")
    referral_milestone_claims.create_index([("user_id", 1), ("milestone", 1)], unique=True, name="referral_milestone_unique")
except Exception:
    logger.exception("Referral index setup warning")

def _safe_int(value, default=0):
    try: return int(value)
    except (TypeError, ValueError): return default

def _get_user(user_id):
    try: return get_user(user_id, create=False)
    except TypeError: return get_user(user_id)

def _settings():
    return db["bot_settings"].find_one({"_id": "main"}) or {}

def _referral_reward():
    return max(0, _safe_int(_settings().get("referral_reward", DEFAULT_REWARD)))

def _referral_xp():
    return max(0, _safe_int(_settings().get("referral_xp", DEFAULT_XP)))

def get_milestones():
    raw = _settings().get("referral_milestones", DEFAULT_MILESTONES)
    if not isinstance(raw, dict): raw = DEFAULT_MILESTONES
    out = {}
    for k, v in raw.items():
        n, r = _safe_int(k), _safe_int(v)
        if n > 0 and r >= 0: out[n] = r
    return dict(sorted(out.items()))

def set_milestone(count, reward):
    count, reward = _safe_int(count), _safe_int(reward)
    if count <= 0 or reward < 0: return False
    settings = _settings(); milestones = get_milestones(); milestones[count] = reward
    return db["bot_settings"].update_one({"_id":"main"},{"$set":{"referral_milestones":{str(k):v for k,v in milestones.items()}}},upsert=True).acknowledged

def delete_milestone(count):
    count = _safe_int(count)
    milestones = get_milestones()
    if count not in milestones: return False
    milestones.pop(count)
    return db["bot_settings"].update_one({"_id":"main"},{"$set":{"referral_milestones":{str(k):v for k,v in milestones.items()}}},upsert=True).acknowledged

def _get_bot_username(context):
    return getattr(context.bot, "username", None) or None

def _referral_link(context, user_id):
    username = _get_bot_username(context)
    return f"https://t.me/{str(username).lstrip('@')}?start=ref_{user_id}" if username else None

def referral_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Get Referral Link", callback_data="referral_link")], [InlineKeyboardButton("📊 My Referrals", callback_data="referral_stats")], [InlineKeyboardButton("🏠 Home", callback_data="home")]])

async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    db_user = _get_user(user.id)
    if not db_user:
        return
    referrals = _safe_int(db_user.get("referrals", 0))
    earned = _safe_int(db_user.get("referral_earn", 0))
    referral_xp = _safe_int(db_user.get("referral_xp", 0))
    pending = _safe_int(db_user.get("pending_referrals", 0))
    link = _referral_link(context, user.id) or "⚠️ Referral link unavailable."

    ms = get_milestones()
    milestone_lines = [
        f"{n} Referrals → +{reward} Points" for n, reward in ms.items()
    ]
    next_ms = next(((n, reward) for n, reward in ms.items() if n > referrals), None)

    if next_ms:
        next_block = (
            f"🎯 **Next Milestone:**\n"
            f"{next_ms[0]} referrals → +{next_ms[1]} Points\n"
            f"Progress: {referrals}/{next_ms[0]}"
        )
    else:
        next_block = "🎯 **Next Milestone:**\nAll configured milestones reached."

    await update.effective_message.reply_text(
        f"👥 **REFERRAL CENTER**\n\n"
        f"🎁 Invite friends and earn rewards!\n\n"
        f"👥 Valid Referrals: {referrals}\n"
        f"⏳ Pending Referrals: {pending}\n"
        f"💰 Referral Earnings: {earned} Points\n"
        f"⭐ Referral XP: {referral_xp}\n\n"
        f"🏆 **REFERRAL MILESTONES**\n"
        f"{chr(10).join(milestone_lines) if milestone_lines else 'No milestones configured.'}\n\n"
        f"{next_block}\n\n"
        f"🔗 **Your Referral Link:**\n`{link}`\n\n"
        f"📢 Share your link with your friends.\n\n"
        f"🎁 Referral rewards are released after the referred user completes a qualifying activity.",
        reply_markup=referral_menu(),
        parse_mode="Markdown",
    )

async def referral_link_callback(update, context):
    q = update.callback_query; await q.answer()
    link = _referral_link(context, q.from_user.id)
    await q.edit_message_text(f"🔗 **Your Referral Link**\n\n`{link or 'Unavailable'}`\n\nInvite friends and earn after their qualifying activity.", reply_markup=referral_menu(), parse_mode="Markdown")

async def referral_stats_callback(update, context):
    q=update.callback_query; await q.answer(); u=_get_user(q.from_user.id) or {}
    ms=get_milestones(); refs=_safe_int(u.get("referrals",0)); earned=_safe_int(u.get("referral_earn",0)); pending=_safe_int(u.get("pending_referrals",0))
    next_ms=next(((n,r) for n,r in ms.items() if n>refs),None)
    nxt=f"{next_ms[0]} referrals → +{next_ms[1]} Points" if next_ms else "All configured milestones reached."
    await q.edit_message_text(f"📊 **MY REFERRALS**\n\n👥 Valid: {refs}\n⏳ Pending: {pending}\n💰 Earnings: {earned} Points\n\n🏆 Next milestone: {nxt}", reply_markup=referral_menu(), parse_mode="Markdown")

def process_referral(new_user_id, referral_id):
    new_user_id, referral_id = _safe_int(new_user_id), _safe_int(referral_id)
    if new_user_id <= 0 or referral_id <= 0 or new_user_id == referral_id: return False
    new_user, referrer = _get_user(new_user_id), _get_user(referral_id)
    if not new_user or not referrer: return False
    if new_user.get("banned") or new_user.get("blacklisted") or referrer.get("banned") or referrer.get("blacklisted"): return False
    if new_user.get("referred_by") is not None: return False
    # Store attribution only. No reward/count is granted at signup.
    result = update_user(new_user_id, {"referred_by": referral_id, "referral_pending": True, "referral_linked_at": int(time.time())})
    if result is False: return False
    try:
        update_user(referral_id, {"pending_referrals": _safe_int(referrer.get("pending_referrals",0)) + 1})
    except Exception: logger.exception("Failed to increment pending referrals")
    return True

def activate_referral(new_user_id, qualifying_activity="task"):
    new_user_id = _safe_int(new_user_id); new_user = _get_user(new_user_id)
    if not new_user or not new_user.get("referral_pending") or not new_user.get("referred_by"): return False
    referrer_id = _safe_int(new_user.get("referred_by")); referrer = _get_user(referrer_id)
    if not referrer or referrer.get("banned") or referrer.get("blacklisted"): return False
    # Count a referral only after qualifying activity, but do not pay a
    # per-referral point bonus. Points are awarded only at milestones.
    reward = 0
    xp = _referral_xp()
    # Claim marker is unique per referred user, preventing duplicate reward
    # when two callbacks arrive at the same time.
    try:
        referral_claims.insert_one({"new_user_id": new_user_id, "referrer_id": referrer_id, "created_at": int(time.time()), "activity": qualifying_activity})
    except DuplicateKeyError:
        return False
    except Exception:
        logger.exception("Referral claim marker failed")
        return False
    try:
        current_refs = _safe_int(referrer.get("referrals",0)) + 1
        current_earn = _safe_int(referrer.get("referral_earn",0)) + reward
        current_xp = _safe_int(referrer.get("referral_xp",0)) + xp
        update_user(referrer_id, {"referrals":current_refs,"referral_earn":current_earn,"referral_xp":current_xp,"pending_referrals":max(0,_safe_int(referrer.get("pending_referrals",0))-1)})
        if xp > 0:
            add_activity(referrer_id, f"👥 Qualified referral XP +{xp}", 0)
        # Milestones are awarded once per threshold.
        awarded = referrer.get("referral_milestones_awarded", [])
        if not isinstance(awarded,list): awarded=[]
        for count, milestone_reward in get_milestones().items():
            if current_refs >= count and count not in awarded and milestone_reward > 0:
                try:
                    referral_milestone_claims.insert_one({"user_id": referrer_id, "milestone": count, "created_at": int(time.time())})
                except DuplicateKeyError:
                    continue
                except Exception:
                    logger.exception("Milestone claim marker failed")
                    continue
                if add_balance(referrer_id, milestone_reward):
                    awarded.append(count)
                    add_activity(referrer_id, f"🏆 Referral milestone {count} +{milestone_reward} Points", milestone_reward)
        update_user(referrer_id, {"referral_milestones_awarded": awarded})
        return True
    except Exception:
        logger.exception("Referral activation failed | new=%s referrer=%s",new_user_id,referrer_id)
        return False

HANDLER_FUNCTIONS={"referral":referral,"referral_link_callback":referral_link_callback,"referral_stats_callback":referral_stats_callback,"process_referral":process_referral,"activate_referral":activate_referral}
__all__=["referral_menu","referral","referral_link_callback","referral_stats_callback","process_referral","activate_referral","get_milestones","set_milestone","delete_milestone","HANDLER_FUNCTIONS"]
