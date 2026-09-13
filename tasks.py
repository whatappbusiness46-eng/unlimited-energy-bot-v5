# ============================================================
# TASK SYSTEM - MongoDB backed, admin managed
# ============================================================
import asyncio
import logging
import os
import time
from urllib.parse import urlparse
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from pymongo.errors import DuplicateKeyError

from database import (
    db, users, get_user, update_user, add_balance, add_activity,
    get_membership_multiplier, use_energy, add_xp,
)
from config import ADMIN_ID, OFFERWALLME_TASK_LIMIT
from provider_integrations import (
    get_offerwallme_tasks, get_cached_offerwallme_tasks, provider_cache_fresh,
    refresh_offerwallme_tasks, submit_offerwallme_task_proof, _offerwallme_reward_points,
    create_offerwall_task_proof, get_offerwall_task_submission, mark_offerwall_task_submission,
    get_cpa_lead_bd_offers, get_cached_cpa_lead_bd_offers, refresh_cpa_lead_bd_offers,
    _cpa_lead_member_reward_points, _cpa_lead_offer_url, _record_provider_pending,
)

logger = logging.getLogger(__name__)
_BACKGROUND_REFRESHING = set()


def _md(value):
    """Escape Telegram Markdown v1 special characters in dynamic task content."""
    text = "" if value is None else str(value)
    return text.replace("\\", "\\\\").replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")

tasks_collection = db["tasks"]
completions_collection = db["task_completions"]
TASK_COOLDOWN = 86400
DEFAULT_REWARD = 10
DEFAULT_XP = 5
DEFAULT_ENERGY = 1
DEFAULT_VERIFICATION = "telegram_join"
# Verification is disabled by default. Set TASK_VERIFICATION_ENABLED=true in Render to enable it.
TASK_VERIFICATION_ENABLED = os.getenv("TASK_VERIFICATION_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
# Private Telegram join tasks use this chat/channel ID (for example: -1001234567890).
# The bot must be an admin/member of that private channel to verify membership.
TASK_PRIVATE_CHAT_ID = os.getenv("TASK_PRIVATE_CHAT_ID", "").strip()

# Short per-user cache prevents the Task Center from fetching the same
# Offerwall.me task list twice during one screen render and reduces repeated
# provider calls when a user opens Tasks again shortly afterwards.
_OFFERWALL_TASK_CACHE = {}
_OFFERWALL_TASK_CACHE_TTL = 45


def _now():
    return int(time.time())


def _safe_int(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


def _ensure_named_index(collection, keys, *, unique=False, name=None):
    """Create an index without failing when MongoDB already has the same key pattern under another name."""
    desired = list(keys)
    indexes = collection.index_information()
    matching = []
    for existing_name, info in indexes.items():
        existing_keys = info.get("key")
        if existing_keys is not None and list(existing_keys) == desired:
            matching.append((existing_name, info))

    # A matching index with the required uniqueness is already sufficient.
    for existing_name, info in matching:
        if bool(info.get("unique", False)) == bool(unique):
            return existing_name

    # Same key pattern but wrong uniqueness: remove the conflicting index first.
    for existing_name, _info in matching:
        if existing_name != "_id_":
            collection.drop_index(existing_name)

    return collection.create_index(desired, unique=unique, name=name)


def ensure_task_indexes():
    try:
        _ensure_named_index(tasks_collection, [("id", 1)], unique=True, name="task_id_unique")
        _ensure_named_index(
            completions_collection,
            [("user_id", 1), ("task_id", 1)],
            unique=True,
            name="user_task_unique",
        )
        _ensure_named_index(
            completions_collection,
            [("user_id", 1), ("status", 1)],
            unique=False,
            name="user_status_idx",
        )
        _ensure_named_index(
            db["offerwall_task_submissions"],
            [("user_id", 1), ("task_id", 1)],
            unique=True,
            name="offerwall_task_submission_unique",
        )
        _ensure_named_index(
            db["offerwall_task_submissions"],
            [("user_id", 1), ("status", 1), ("submitted_at", -1)],
            unique=False,
            name="offerwall_task_submission_status",
        )
        return True
    except Exception:
        logger.exception("task index creation failed")
        return False


ensure_task_indexes()


def seed_default_task():
    # Create disabled task slots only; no fake links or automatic rewards.
    ensure_task_indexes()
    starter_tasks = [
        ("starter_task_01", "📣 Official Channel Task", "Replace URL with your real public Telegram channel.", "", "telegram_join"),
        ("starter_task_02", "🤖 Partner Bot Task", "Replace URL with your real partner bot/deep-link.", "", "manual"),
        ("starter_task_03", "📢 Sponsor Channel Task", "Replace URL with an approved sponsor channel.", "", "telegram_join"),
        ("starter_task_04", "🎯 Community Task", "Replace URL with your real community link.", "", "telegram_join"),
        ("starter_task_05", "⭐ VIP Task Slot", "Configure a real VIP task and keep it under Admin Approval.", "", "manual"),
        ("starter_task_06", "🎁 Promotion Task", "Configure a real promotional task.", "", "manual"),
        ("starter_task_07", "🚀 Partner Task", "Configure a real partner task with an approved destination.", "", "manual"),
        ("starter_task_08", "💎 VIP Partner Task", "Configure a real VIP partner task.", "", "manual"),
    ]
    for tid, title, desc, url, verify in starter_tasks:
        if not tasks_collection.find_one({"id": tid}, {"_id": 1}):
            register_task(tid, title, desc, reward=10, url=url or None, cooldown=0, enabled=False, xp=0, energy=0, task_type="starter", audience="normal", verification_method=verify)


def _normalise_verification(value, url=None):
    value = str(value or "").strip().lower()
    aliases = {"join": "telegram_join", "telegram": "telegram_join", "channel_join": "telegram_join"}
    value = aliases.get(value, value)
    if value not in {"telegram_join", "manual", "click_once"}:
        value = DEFAULT_VERIFICATION if url and "t.me/" in str(url) else "manual"
    return value


def register_task(task_id: str, title: str, description: str = "", reward: int = DEFAULT_REWARD,
                  url: Optional[str] = None, cooldown: int = TASK_COOLDOWN, enabled: bool = True,
                  xp: int = DEFAULT_XP, energy: int = DEFAULT_ENERGY,
                  task_type: str = "telegram", audience: str = "normal",
                  verification_method: str = DEFAULT_VERIFICATION) -> bool:
    task_id = str(task_id).strip()
    if not task_id or len(task_id) > 50:
        return False
    audience = str(audience or "normal").strip().lower()
    if audience not in {"normal", "vip", "both"}:
        return False
    verification_method = _normalise_verification(verification_method, url)
    doc = {
        "id": task_id,
        "title": str(title or task_id)[:120],
        "description": str(description or "")[:1000],
        "reward": max(0, _safe_int(reward)),
        "url": url,
        "cooldown": max(0, _safe_int(cooldown, TASK_COOLDOWN)),
        "enabled": bool(enabled),
        "xp": max(0, _safe_int(xp, DEFAULT_XP)),
        "energy": max(0, _safe_int(energy, DEFAULT_ENERGY)),
        "task_type": str(task_type or "telegram")[:40],
        "audience": audience,
        "verification_method": verification_method,
        "updated_at": _now(),
    }
    try:
        tasks_collection.update_one(
            {"id": task_id}, {"$set": doc, "$setOnInsert": {"created_at": _now()}}, upsert=True
        )
        return True
    except Exception:
        logger.exception("register task failed")
        return False


def get_tasks(include_disabled=False, user_id=None):
    q = {} if include_disabled else {"enabled": True}
    tasks = list(tasks_collection.find(q, {"_id": 0}).sort("created_at", 1))
    if user_id is None:
        return tasks
    vip = bool((db["users"].find_one({"user_id": int(user_id)}, {"vip": 1, "vip_expire": 1}) or {}).get("vip"))
    # Use the central VIP status helper when possible so expired VIP is not treated as active.
    try:
        from database import get_vip_status
        vip = bool(get_vip_status(user_id).get("active"))
    except Exception:
        pass
    return [t for t in tasks if t.get("audience", "normal") in ({"vip", "both"} if vip else {"normal", "both"})]


def get_task(task_id):
    return tasks_collection.find_one({"id": str(task_id)}, {"_id": 0})


def set_task_enabled(task_id, enabled):
    return tasks_collection.update_one({"id": str(task_id)}, {"$set": {"enabled": bool(enabled), "updated_at": _now()}}).modified_count > 0


def delete_task(task_id):
    return tasks_collection.delete_one({"id": str(task_id)}).deleted_count > 0


def _completed_map(user):
    value = user.get("task_history", {})
    return dict(value) if isinstance(value, dict) else {}


def _is_vip(user_id):
    try:
        from database import get_vip_status
        return bool(get_vip_status(user_id).get("active"))
    except Exception:
        return False


def task_visible(user_id, task):
    if not task or not task.get("enabled", True):
        return False
    audience = task.get("audience", "normal")
    return audience in ({"vip", "both"} if _is_vip(user_id) else {"normal", "both"})


def task_available(user_id, task_id):
    user = get_user(user_id, create=False)
    task = get_task(task_id)
    if not user or user.get("banned") or user.get("blacklisted") or not task_visible(user_id, task):
        return False
    # Permanent completion wins over all cooldown logic.
    completion = completions_collection.find_one({"user_id": int(user_id), "task_id": str(task_id)})
    if completion and completion.get("status") in {"rewarded", "pending"}:
        return False
    if str(task_id) in {str(x) for x in user.get("completed_tasks", [])}:
        return False
    last = _safe_int(_completed_map(user).get(str(task_id)), 0)
    return not last or _now() - last >= max(0, _safe_int(task.get("cooldown"), TASK_COOLDOWN))


def _daily_count(user):
    now = _now(); reset = _safe_int(user.get("task_day_started"), 0)
    if not reset or now - reset >= 86400:
        return 0, now
    return _safe_int(user.get("daily_task_count"), 0), reset


async def _verify_telegram_join(bot, user_id, url):
    """Verify Telegram membership for public links and configured private invite links."""
    if not url:
        return False
    parsed = urlparse(str(url).strip())
    if parsed.netloc.lower().replace("www.", "") not in {"t.me", "telegram.me"}:
        return False
    path = parsed.path.strip("/")
    if not path:
        return False

    # Private invite links (t.me/+HASH or t.me/joinchat/HASH) do not expose
    # a chat identifier. Use TASK_PRIVATE_CHAT_ID for the actual channel ID.
    if path.startswith("+") or path.startswith("joinchat/"):
        if not TASK_PRIVATE_CHAT_ID:
            logger.warning("Private Telegram task needs TASK_PRIVATE_CHAT_ID")
            return False
        chat_id = TASK_PRIVATE_CHAT_ID
    else:
        chat_id = "@" + path.split("/")[0].lstrip("@")

    try:
        member = await bot.get_chat_member(chat_id, int(user_id))
        return member.status in {"member", "administrator", "creator"}
    except Exception:
        logger.exception("telegram task verification failed for chat %s", chat_id)
        return False


def _reserve_completion(user_id, task_id):
    doc = {"user_id": int(user_id), "task_id": str(task_id), "status": "pending", "created_at": _now()}
    try:
        completions_collection.insert_one(doc)
        return True, "new"
    except DuplicateKeyError:
        existing = completions_collection.find_one({"user_id": int(user_id), "task_id": str(task_id)})
        if existing and existing.get("status") == "rewarded":
            return False, "already"
        # Never let two concurrent requests both proceed from the same pending record.
        # A stale reservation is recoverable after a short safety window.
        if existing and existing.get("status") == "pending":
            age = _now() - _safe_int(existing.get("created_at"), _now())
            if age < 600:
                return False, "in_progress"
            completions_collection.delete_one({"_id": existing.get("_id"), "status": "pending"})
            try:
                completions_collection.insert_one(doc)
                return True, "new"
            except DuplicateKeyError:
                return False, "in_progress"
        return False, "already"
    except Exception:
        logger.exception("task completion reservation failed")
        return False, "error"


def _vip_manual_review_required(user_id, task):
    # VIP task claims are always admin-reviewed. For a BOTH task, only VIP users are reviewed.
    audience = str(task.get("audience", "normal")).strip().lower()
    return audience == "vip" or (audience == "both" and _is_vip(user_id))


def _manual_reward(user_id, task):
    reward = max(0, _safe_int(task.get("reward"), 0))
    try:
        reward = int(round(reward * max(1.0, float(get_membership_multiplier(user_id)))))
    except Exception:
        pass
    return reward


def request_vip_task_review(user_id, task_id):
    user = get_user(user_id, create=False); task = get_task(task_id)
    if not user or not task or user.get("banned") or user.get("blacklisted") or not task_visible(user_id, task):
        return False, "Unavailable."
    if not _vip_manual_review_required(user_id, task):
        return False, "This task is auto-verified for Normal members."
    if not task_available(user_id, task_id):
        existing = completions_collection.find_one({"user_id": int(user_id), "task_id": str(task_id)})
        if existing and existing.get("status") == "pending":
            return False, "Your task is already waiting for Admin approval."
        return False, "Task already completed."
    reserved, state = _reserve_completion(user_id, task_id)
    if not reserved:
        return False, "Your task is already waiting for Admin approval." if state == "in_progress" else "Task already completed."
    completions_collection.update_one(
        {"user_id": int(user_id), "task_id": str(task_id)},
        {"$set": {"status": "pending", "submitted_at": _now(), "reward_requested": _manual_reward(user_id, task)}}
    )
    return True, "Pending"


def approve_task_completion(user_id, task_id, admin_id):
    try:
        if int(admin_id) != int(ADMIN_ID):
            return False, "Admin only."
    except Exception:
        return False, "Admin only."
    task = get_task(task_id); user = get_user(user_id, create=False)
    if not task or not user:
        return False, "Task or user not found."
    record = completions_collection.find_one({"user_id": int(user_id), "task_id": str(task_id), "status": "pending"})
    if not record:
        return False, "No pending completion found."
    reward = _manual_reward(user_id, task)
    if reward:
        add_balance(user_id, reward)
    xp = _safe_int(task.get("xp"), 0)
    if xp:
        add_xp(user_id, xp)
    now = _now()
    user = get_user(user_id, create=False) or {}
    history = _completed_map(user); history[str(task_id)] = now
    completed = list({*map(str, user.get("completed_tasks", [])), str(task_id)})
    count, reset = _daily_count(user)
    update_user(user_id, {"task_history": history, "completed_tasks": completed, "daily_task_count": count + 1, "task_day_started": reset})
    completions_collection.update_one({"_id": record["_id"], "status": "pending"}, {"$set": {"status": "rewarded", "reward": reward, "approved_at": now, "approved_by": int(admin_id)}})
    try:
        from referral import activate_referral
        activate_referral(user_id, "task")
    except Exception:
        logger.exception("Referral activation hook failed")
    try: add_activity(user_id, f"VIP task approved: {task.get('title')}", reward)
    except Exception: pass
    try:
        from database import increment_campaign_score
        from config import ACTIVE_CAMPAIGN_TASK_SCORE
        increment_campaign_score(user_id, task_delta=ACTIVE_CAMPAIGN_TASK_SCORE)
    except Exception:
        logger.exception("Active campaign task score update failed")
    return True, f"Approved +{reward} Points"


def reject_task_completion(user_id, task_id, admin_id, reason="Rejected"):
    try:
        if int(admin_id) != int(ADMIN_ID):
            return False, "Admin only."
    except Exception:
        return False, "Admin only."
    record = completions_collection.find_one({"user_id": int(user_id), "task_id": str(task_id), "status": "pending"})
    if not record:
        return False, "No pending completion found."
    completions_collection.update_one({"_id": record["_id"], "status": "pending"}, {"$set": {"status": "rejected", "rejected_at": _now(), "rejected_by": int(admin_id), "reason": str(reason or "Rejected")[:300]}})
    return True, "Rejected"


def complete_task(user_id, task_id, bot=None):
    user = get_user(user_id, create=False); task = get_task(task_id)
    if not user or not task or user.get("banned") or user.get("blacklisted") or not task_visible(user_id, task):
        return False, "Unavailable."
    if not task_available(user_id, task_id):
        return False, "Task already completed."

    if _vip_manual_review_required(user_id, task):
        return request_vip_task_review(user_id, task_id)
    verification = _normalise_verification(task.get("verification_method"), task.get("url"))
    if verification == "telegram_join":
        if bot is None:
            return False, "Verification is temporarily unavailable."
        import asyncio
        try:
            verified = asyncio.get_event_loop().run_until_complete(_verify_telegram_join(bot, user_id, task.get("url")))
        except RuntimeError:
            # Called from an async handler: caller should use complete_task_async.
            return False, "Verification is temporarily unavailable."
        if not verified:
            return False, "Please complete the Telegram join task first."
    elif TASK_VERIFICATION_ENABLED and verification == "manual":
        return False, "This task requires admin/provider verification and cannot be auto-verified."

    settings = db["bot_settings"].find_one({"_id": "main"}) or {}
    daily_limit = max(1, _safe_int(settings.get("daily_task_limit"), 20))
    count, reset = _daily_count(user)
    if count >= daily_limit:
        return False, "Daily task limit reached."
    energy_cost = max(0, _safe_int(task.get("energy"), 1))
    if energy_cost and not use_energy(user_id, energy_cost):
        return False, "Not enough Energy."
    reserved, state = _reserve_completion(user_id, task_id)
    if not reserved:
        return False, "Task already completed."
    reward = max(0, _safe_int(task.get("reward"), 0))
    try:
        reward = int(round(reward * max(1.0, float(get_membership_multiplier(user_id)))))
    except Exception:
        pass
    history = _completed_map(user); history[str(task_id)] = _now()
    update_user(user_id, {"task_history": history, "completed_tasks": list({*map(str, user.get("completed_tasks", [])), str(task_id)}), "daily_task_count": count + 1, "task_day_started": reset})
    if reward:
        add_balance(user_id, reward)
    if _safe_int(task.get("xp"), 0):
        add_xp(user_id, _safe_int(task.get("xp"), 0))
    completions_collection.update_one({"user_id": int(user_id), "task_id": str(task_id)}, {"$set": {"status": "rewarded", "reward": reward, "completed_at": _now()}})
    try:
        from referral import activate_referral
        activate_referral(user_id, "task")
    except Exception:
        logger.exception("Referral activation hook failed")
    try: add_activity(user_id, f"Task completed: {task.get('title')}", reward)
    except Exception: pass
    try:
        from database import increment_campaign_score
        from config import ACTIVE_CAMPAIGN_TASK_SCORE
        increment_campaign_score(user_id, task_delta=ACTIVE_CAMPAIGN_TASK_SCORE)
    except Exception:
        logger.exception("Active campaign task score update failed")
    return True, "OK"


async def complete_task_async(user_id, task_id, bot):
    user = get_user(user_id, create=False); task = get_task(task_id)
    if not user or not task or user.get("banned") or user.get("blacklisted") or not task_visible(user_id, task):
        return False, "Unavailable."
    if not task_available(user_id, task_id):
        return False, "Task already completed."
    if _vip_manual_review_required(user_id, task):
        return request_vip_task_review(user_id, task_id)
    verification = _normalise_verification(task.get("verification_method"), task.get("url"))
    if verification == "telegram_join" and not await _verify_telegram_join(bot, user_id, task.get("url")):
        return False, "Please complete the Telegram join task first."
    if TASK_VERIFICATION_ENABLED and verification == "manual":
        return False, "This task requires admin/provider verification and cannot be auto-verified."
    settings = db["bot_settings"].find_one({"_id": "main"}) or {}
    daily_limit = max(1, _safe_int(settings.get("daily_task_limit"), 20))
    count, reset = _daily_count(user)
    if count >= daily_limit: return False, "Daily task limit reached."
    reserved, state = _reserve_completion(user_id, task_id)
    if not reserved:
        return False, "Task already completed." if state == "already" else "Task verification is already in progress. Please try again shortly."
    energy_cost = max(0, _safe_int(task.get("energy"), 1))
    if energy_cost and not use_energy(user_id, energy_cost):
        if state == "new":
            completions_collection.delete_one({"user_id": int(user_id), "task_id": str(task_id), "status": "pending"})
        return False, "Not enough Energy."
    reward = max(0, _safe_int(task.get("reward"), 0))
    try: reward = int(round(reward * max(1.0, float(get_membership_multiplier(user_id)))))
    except Exception: pass
    completed = list({*map(str, user.get("completed_tasks", [])), str(task_id)})
    update_user(user_id, {"task_history": {**_completed_map(user), str(task_id): _now()}, "completed_tasks": completed, "daily_task_count": count + 1, "task_day_started": reset})
    if reward: add_balance(user_id, reward)
    xp = _safe_int(task.get("xp"), 0)
    if xp: add_xp(user_id, xp)
    completions_collection.update_one({"user_id": int(user_id), "task_id": str(task_id)}, {"$set": {"status": "rewarded", "reward": reward, "completed_at": _now()}})
    try:
        from referral import activate_referral; activate_referral(user_id, "task")
    except Exception: logger.exception("Referral activation hook failed")
    try: add_activity(user_id, f"Task completed: {task.get('title')}", reward)
    except Exception: pass
    try:
        from database import increment_campaign_score
        from config import ACTIVE_CAMPAIGN_TASK_SCORE
        increment_campaign_score(user_id, task_delta=ACTIVE_CAMPAIGN_TASK_SCORE)
    except Exception:
        logger.exception("Active campaign task score update failed")
    return True, "OK"


def _offerwall_task_category(task):
    """Classify provider tasks using provider metadata first, then title/text keywords."""
    if not isinstance(task, dict):
        return "other"
    raw = " ".join(str(task.get(k) or "") for k in ("offer_type", "task_type", "type", "category", "vertical", "title", "description", "instructions", "platform")).lower()
    if any(k in raw for k in ("video", "watch ad", "rewarded ad", "reward video", "ad view", "watch video")):
        return "video"
    if any(k in raw for k in ("install", "app install", "download app", "mobile app", "android app", "ios app", "cpi")):
        return "app"
    if any(k in raw for k in ("signup", "sign up", "register", "registration", "create account", "lead", "join", "follow", "like", "subscribe", "visit", "click", "simple task")):
        return "easy"
    if any(k in raw for k in ("survey", "questionnaire", "poll")):
        return "survey"
    return "other"


def _offerwall_task_category_label(category):
    return {
        "easy": "🟢 Easy Tasks",
        "app": "📱 App Install",
        "video": "🎬 Video Ads",
        "survey": "📝 Surveys",
        "other": "💰 Other Tasks",
    }.get(str(category), "💰 Other Tasks")


def _offerwall_category_tasks(user_id, category):
    tasks = _get_offerwall_tasks_cached(user_id)
    return [t for t in tasks if _offerwall_task_category(t) == category]


def _get_offerwall_tasks_cached(user_id):
    try:
        tasks = get_cached_offerwallme_tasks(int(user_id))
        return list(tasks or [])
    except Exception:
        return []


async def _refresh_tasks_in_background(query, user_id: int):
    key = int(user_id)
    if key in _BACKGROUND_REFRESHING:
        return
    _BACKGROUND_REFRESHING.add(key)
    try:
        await asyncio.to_thread(refresh_offerwallme_tasks, user_id)
        if query and query.message:
            db_user = get_user(user_id, create=False)
            if not db_user or db_user.get("banned") or db_user.get("blacklisted"):
                return
            task_list = get_tasks(user_id=user_id)
            count, _ = _daily_count(db_user)
            settings = db["bot_settings"].find_one({"_id":"main"}) or {}
            limit = max(1, _safe_int(settings.get("daily_task_limit"), 20))
            offerwall_tasks = _get_offerwall_tasks_cached(user_id)
            normal = [t for t in task_list if t.get("audience","normal") in {"normal","both"}]
            vip = [t for t in task_list if t.get("audience","normal") in {"vip","both"}]
            text = "🎯 **TASK CENTER**\n\nSelect a task category below."
            await query.edit_message_text(text, reply_markup=tasks_menu(user_id, offerwall_tasks=offerwall_tasks), parse_mode="Markdown")
    except Exception:
        logger.exception("Background task refresh failed | user=%s", user_id)
    finally:
        _BACKGROUND_REFRESHING.discard(key)


def tasks_menu(user_id=None, offerwall_tasks=None, offerwall_category=None):
    buttons=[]
    for task in get_tasks(user_id=user_id):
        available = task_available(user_id, task["id"]) if user_id else True
        buttons.append([InlineKeyboardButton(f"{'🎯' if available else '✅'} {_md(task.get('title',''))} (+{_safe_int(task.get('reward'),0)})", callback_data=f"task_{task['id']}")])
    if user_id:
        # Keep the provider areas separate and clean:
        # BD Advance Tasks = CPAlead BD offers
        # Rewards Tasks = Offerwall.me categories (the old task buttons).
        buttons.append([InlineKeyboardButton("🇧🇩 BD Advance Tasks", callback_data="cpalead_tasks")])
        buttons.append([InlineKeyboardButton("🎁 Rewards Tasks", callback_data="reward_tasks")])
    buttons.append([InlineKeyboardButton("🏠 Home", callback_data="home")])
    return InlineKeyboardMarkup(buttons)


async def tasks_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user; message = update.effective_message
    if not user or not message: return
    db_user=get_user(user.id, create=False)
    if not db_user or db_user.get("banned") or db_user.get("blacklisted"):
        await message.reply_text("🚫 Your account is restricted."); return
    task_list=get_tasks(user_id=user.id); count,_=_daily_count(db_user); settings=db["bot_settings"].find_one({"_id":"main"}) or {}; limit=max(1,_safe_int(settings.get("daily_task_limit"),20))
    offerwall_tasks = _get_offerwall_tasks_cached(user.id)
    if not provider_cache_fresh("offerwallme_tasks", user.id):
        try:
            if update.callback_query:
                context.application.create_task(_refresh_tasks_in_background(update.callback_query, user.id))
            else:
                context.application.create_task(asyncio.to_thread(refresh_offerwallme_tasks, user.id))
        except Exception:
            pass
    normal=[t for t in task_list if t.get("audience","normal") in {"normal","both"}]
    vip=[t for t in task_list if t.get("audience","normal") in {"vip","both"}]
    if not task_list and not offerwall_tasks:
        text=("📋 **TASK CENTER**\n\n" + ("⏳ Loading latest tasks...\n\nPlease wait a moment; the task list is being refreshed." if not provider_cache_fresh("offerwallme_tasks", user.id) else "No tasks are available for your membership right now."))
    else:
        text = "🎯 **TASK CENTER**\n\nSelect a task category below."
    markup = tasks_menu(user.id, offerwall_tasks=offerwall_tasks)
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            await message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await message.reply_text(text, reply_markup=markup, parse_mode="Markdown")


async def task_callback(update, context):
    q=update.callback_query
    if not q or not str(q.data).startswith("task_"): return
    await q.answer(); tid=str(q.data)[5:]; task=get_task(tid)
    if not task or not task_visible(q.from_user.id, task): await q.edit_message_text("⚠️ Task not found or unavailable."); return
    buttons=[]
    if task.get("url"): buttons.append([InlineKeyboardButton("🚀 Open Task", url=task["url"])])
    verification = _normalise_verification(task.get("verification_method"), task.get("url"))
    if _vip_manual_review_required(q.from_user.id, task):
        buttons.append([InlineKeyboardButton("📨 Submit for Admin Approval", callback_data=f"task_complete_{tid}")])
    elif verification in {"telegram_join", "click_once"}:
        label = "🎁 Claim 10 Points" if verification == "click_once" else "✅ Verify Task"
        buttons.append([InlineKeyboardButton(label, callback_data=f"task_complete_{tid}")])
    buttons.append([InlineKeyboardButton("⬅️ Tasks", callback_data="tasks"), InlineKeyboardButton("🏠 Home", callback_data="home")])
    audience = str(task.get("audience", "normal")).upper()
    await q.edit_message_text(f"🎯 **{_md(task.get('title',''))}**\n\n{_md(task.get('description',''))}\n\n💰 Reward: {_safe_int(task.get('reward'),0)} Points\n🏷 Audience: {_md(audience)}\n🔐 Verification: {_md(task.get('verification_method','telegram_join'))}", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")


async def task_complete_callback(update, context):
    q=update.callback_query
    if not q or not str(q.data).startswith("task_complete_"): return
    await q.answer(); tid=str(q.data)[len("task_complete_"):]; task=get_task(tid)
    if not task: await q.edit_message_text("⚠️ Task not found."); return
    ok,msg=await complete_task_async(q.from_user.id,tid,context.bot)
    if ok and _vip_manual_review_required(q.from_user.id, task):
        text = f"📨 **TASK SUBMITTED**\n\n🎯 {_md(task.get('title',''))}\n\nYour VIP task has been sent to Admin for approval.\n💰 Reward will be credited after approval."
    else:
        text = f"🎉 **TASK COMPLETED!**\n\n🎯 {_md(task.get('title',''))}\n💰 Reward credited successfully." if ok else f"❌ **Task not completed**\n\n{msg}"
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Tasks",callback_data="tasks")],[InlineKeyboardButton("🏠 Home",callback_data="home")]]), parse_mode="Markdown")


async def cpalead_tasks_callback(update, context):
    q = update.callback_query
    if not q or q.data != "cpalead_tasks":
        return
    await q.answer()
    user_id = int(q.from_user.id)
    offers = list(get_cached_cpa_lead_bd_offers(user_id) or [])
    if not offers:
        try:
            offers = list(await asyncio.to_thread(refresh_cpa_lead_bd_offers, user_id) or [])
        except Exception:
            logger.exception("CPAlead BD task refresh failed | user=%s", user_id)
            offers = []
    lines = ["🇧🇩 **BD Advance Tasks**", "", "Complete the task genuinely. Reward is credited after verified provider conversion.", ""]
    buttons = []
    for offer in offers[:20]:
        oid = str(offer.get("offer_id") or "").strip()
        if not oid:
            continue
        reward = _cpa_lead_member_reward_points(offer.get("provider_reward", 0), user_id)
        title = str(offer.get("title") or "BD Task").strip()
        buttons.append([InlineKeyboardButton(f"🎯 {title[:30]} (+{reward})", callback_data=f"cpalead_{oid}")])
    if not buttons:
        lines.append("😔 No BD tasks are available right now.")
    buttons.append([InlineKeyboardButton("⬅️ Tasks", callback_data="tasks"), InlineKeyboardButton("🏠 Home", callback_data="home")])
    await q.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")


async def rewards_tasks_callback(update, context):
    """Show Offerwall.me tasks using the previous category-button layout."""
    q = update.callback_query
    if not q or q.data != "reward_tasks":
        return
    await q.answer()
    user_id = int(q.from_user.id)

    tasks = _get_offerwall_tasks_cached(user_id)
    if not tasks or not provider_cache_fresh("offerwallme_tasks", user_id):
        try:
            fresh = await asyncio.to_thread(refresh_offerwallme_tasks, user_id)
            if fresh is not None:
                tasks = list(fresh or [])
            else:
                tasks = _get_offerwall_tasks_cached(user_id)
        except Exception:
            logger.exception("Offerwall.me Rewards Tasks refresh failed | user=%s", user_id)
            tasks = _get_offerwall_tasks_cached(user_id)

    category_order = ["easy", "app", "video", "survey", "other"]
    buttons = []
    for category in category_order:
        category_tasks = [t for t in tasks if _offerwall_task_category(t) == category]
        label = _offerwall_task_category_label(category)
        buttons.append([InlineKeyboardButton(
            f"{label} ({len(category_tasks)})" if category_tasks else label,
            callback_data=f"owcat_{category}",
        )])

    text = (
        "🎁 **REWARDS TASKS**\n\n"
        "Choose a task type below.\n"
        "Rewards are credited after verified Offerwall.me conversion.\n\n"
        f"📋 Available Tasks: {len(tasks)}"
    )
    buttons.append([InlineKeyboardButton("⬅️ Tasks", callback_data="tasks"), InlineKeyboardButton("🏠 Home", callback_data="home")])
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")


async def cpalead_task_callback(update, context):
    q = update.callback_query
    if not q or not str(q.data).startswith("cpalead_") or q.data == "cpalead_tasks":
        return
    await q.answer()
    offer_id = str(q.data)[len("cpalead_"):]
    offers = list(get_cached_cpa_lead_bd_offers(q.from_user.id) or [])
    offer = next((x for x in offers if str(x.get("offer_id")) == offer_id), None)
    if not offer:
        try:
            offers = list(await asyncio.to_thread(refresh_cpa_lead_bd_offers, int(q.from_user.id)) or [])
            offer = next((x for x in offers if str(x.get("offer_id")) == offer_id), None)
        except Exception:
            offer = None
    if not offer:
        await q.edit_message_text("⚠️ This BD task is no longer available.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BD Advance Tasks", callback_data="cpalead_tasks")]]))
        return
    reward = _cpa_lead_member_reward_points(offer.get("provider_reward", 0), q.from_user.id)
    title = str(offer.get("title") or "BD Task")
    description = str(offer.get("description") or "").replace("\n", "\n").strip()
    url = _cpa_lead_offer_url(offer, q.from_user.id)
    _record_provider_pending("cpalead", q.from_user.id, offer_id, title, reward, offer.get("provider_reward", 0))
    text = f"🎯 **{_md(title)}**\n\n"
    if description:
        text += f"{_md(description)}\n\n"
    text += f"💰 Reward: +{reward} Points\n🇧🇩 Type: BD Advance Task\n\n⏳ Status: Pending — complete the task. Points will be added automatically after provider verification."
    buttons = []
    if url:
        buttons.append([InlineKeyboardButton("🚀 Open Task", url=url)])
    buttons.append([InlineKeyboardButton("⬅️ BD Advance Tasks", callback_data="cpalead_tasks"), InlineKeyboardButton("🏠 Home", callback_data="home")])
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")


async def offerwallme_category_callback(update, context):
    q = update.callback_query
    if not q or not str(q.data).startswith("owcat_"):
        return
    await q.answer()
    category = str(q.data)[len("owcat_"):]
    allowed = {"easy", "app", "video", "survey", "other"}
    if category not in allowed:
        return
    tasks = _offerwall_category_tasks(q.from_user.id, category)
    label = _offerwall_task_category_label(category)
    lines = [f"{label}", "", "Complete genuine tasks. Rewards are credited only after verified provider conversion.", ""]
    buttons = []
    if tasks:
        for task in tasks[:OFFERWALLME_TASK_LIMIT]:
            task_id = str(task.get("id") or "")
            if not task_id:
                continue
            title = str(task.get("title") or "Reward Task")
            reward = _offerwallme_reward_points(task.get("reward", task.get("payout", task.get("amount", 0))), q.from_user.id)
            buttons.append([InlineKeyboardButton(f"🎯 {title[:28]} (+{reward})", callback_data=f"owtask_{task_id}")])
    else:
        lines.append("😔 No matching offers are available for you right now.")
        if category == "video":
            lines.append("Video offers depend on the current Offerwall.me inventory, country and device.")
    lines += ["", "Provider inventory changes automatically; a task may disappear after it is completed or expires."]
    buttons.append([InlineKeyboardButton("⬅️ Tasks", callback_data="tasks"), InlineKeyboardButton("🏠 Home", callback_data="home")])
    await q.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")


async def offerwallme_task_callback(update, context):
    q = update.callback_query
    if not q or not str(q.data).startswith("owtask_"):
        return
    await q.answer()
    task_id = str(q.data)[len("owtask_"):]
    try:
        tasks = _get_offerwall_tasks_cached(q.from_user.id)
    except Exception:
        tasks = []
    task = next((t for t in tasks if str(t.get("id")) == task_id), None)
    if not task:
        await q.edit_message_text("⚠️ This reward task is no longer available.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Tasks", callback_data="tasks")]]))
        return

    # No screenshot/proof step: opening a provider task creates one pending
    # conversion slot. The actual reward is credited only when Offerwall.me
    # sends a verified postback for this user. Keep only the latest pending
    # task to avoid ambiguous conversion matching.
    try:
        reward_raw = str(task.get("reward", task.get("payout", task.get("amount", 0))) or "0")
        db["offerwall_task_submissions"].update_many(
            {"user_id": int(q.from_user.id), "status": "pending"},
            {"$set": {"status": "abandoned", "abandoned_at": int(time.time())}},
        )
        mark_offerwall_task_submission(
            q.from_user.id, task_id, "pending",
            submitted_at=int(time.time()),
            provider_reward_raw=reward_raw,
            task_title=str(task.get("title") or "")[:200],
            proof_kind="none",
            proof_text="",
        )
        _record_provider_pending(
            "offerwallme", q.from_user.id, task_id, str(task.get("title") or "Reward Task"),
            _offerwallme_reward_points(reward_raw, q.from_user.id), reward_raw
        )
    except Exception:
        logger.exception("Could not create Offerwall.me pending task slot | user=%s task=%s", q.from_user.id, task_id)

    submission = get_offerwall_task_submission(q.from_user.id, task_id)
    submission_status = str((submission or {}).get("status") or "pending").lower()
    reward = _offerwallme_reward_points(task.get("reward", task.get("payout", task.get("amount", 0))), q.from_user.id)

    def _display_text(value):
        return (str(value or "").replace("\\n", "\n").replace("<p>", "").replace("</p>", "").strip())

    instructions = _display_text(task.get("instructions") or task.get("description"))
    context.user_data["offerwallme_task_preview"] = task_id
    context.user_data.pop("offerwallme_pending_task", None)
    text = f"🎯 **{_md(_display_text(task.get('title','Offerwall Task')))}**\n\n"
    description = _display_text(task.get("description"))
    if description:
        text += f"{_md(description)}\n\n"
    if instructions:
        text += f"📋 **Instructions:**\n{_md(instructions)}\n\n"
    category = _offerwall_task_category(task)
    category_label = _offerwall_task_category_label(category)
    platform = str(task.get("platform") or "").strip()
    text += f"💰 Reward: +{reward} Points\n🏷 Type: {_md(category_label)}"
    if platform:
        text += f"\n📱 Platform: {_md(platform)}"
    text += "\n\n⏳ **Status:** Pending — complete the task. Your Points will be added automatically after provider verification."

    buttons = []
    task_url = str(task.get("url") or task.get("link") or "").strip()
    if task_url:
        buttons.append([InlineKeyboardButton("🚀 Open Task", url=task_url)])
    if submission_status == "rewarded":
        text = text.replace("⏳ **Status:** Pending — complete the task. Your Points will be added automatically after provider verification.", "✅ **Status:** Verified & Rewarded — Points have been added.")
    buttons.append([InlineKeyboardButton("⬅️ Tasks", callback_data="tasks"), InlineKeyboardButton("🏠 Home", callback_data="home")])
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")


async def offerwallme_task_proof_callback(update, context):
    q = update.callback_query
    if q:
        await q.answer("Proof is not required. Just complete the task; verified rewards are automatic.", show_alert=True)


async def offerwallme_proof_message_handler(update, context):
    # Offerwall.me provider tasks no longer require user-submitted screenshots/proof.
    return False


HANDLER_FUNCTIONS={"tasks":tasks_page,"task_callback":task_callback,"task_complete_callback":task_complete_callback,"rewards_tasks_callback":rewards_tasks_callback,"cpalead_tasks_callback":cpalead_tasks_callback,"cpalead_task_callback":cpalead_task_callback,"offerwallme_category_callback":offerwallme_category_callback,"offerwallme_task_callback":offerwallme_task_callback,"offerwallme_task_proof_callback":offerwallme_task_proof_callback}
__all__=["register_task","get_tasks","get_task","set_task_enabled","delete_task","task_available","complete_task","complete_task_async","request_vip_task_review","approve_task_completion","reject_task_completion","tasks_menu","tasks_page","task_callback","task_complete_callback","rewards_tasks_callback","cpalead_tasks_callback","cpalead_task_callback","offerwallme_category_callback","offerwallme_task_callback","offerwallme_task_proof_callback","offerwallme_proof_message_handler","HANDLER_FUNCTIONS","ensure_task_indexes"]
