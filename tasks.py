# ============================================================
# TASK SYSTEM - MongoDB backed, admin managed
# ============================================================
import logging
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

logger = logging.getLogger(__name__)
tasks_collection = db["tasks"]
completions_collection = db["task_completions"]
TASK_COOLDOWN = 86400
DEFAULT_REWARD = 10
DEFAULT_XP = 5
DEFAULT_ENERGY = 1
DEFAULT_VERIFICATION = "telegram_join"


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
        return True
    except Exception:
        logger.exception("task index creation failed")
        return False


ensure_task_indexes()


def seed_default_task():
    # No fake/test task is inserted. Admin creates real tasks.
    ensure_task_indexes()


def _normalise_verification(value, url=None):
    value = str(value or "").strip().lower()
    aliases = {"join": "telegram_join", "telegram": "telegram_join", "channel_join": "telegram_join"}
    value = aliases.get(value, value)
    if value not in {"telegram_join", "manual"}:
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
    if completions_collection.find_one({"user_id": int(user_id), "task_id": str(task_id), "status": "rewarded"}):
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
    """Verify membership for public Telegram channel/group links."""
    if not url:
        return False
    parsed = urlparse(str(url).strip())
    if parsed.netloc.lower().replace("www.", "") not in {"t.me", "telegram.me"}:
        return False
    path = parsed.path.strip("/")
    if not path or path.startswith("+") or path.startswith("joinchat/"):
        return False
    username = "@" + path.split("/")[0].lstrip("@")
    try:
        member = await bot.get_chat_member(username, int(user_id))
        return member.status in {"member", "administrator", "creator"}
    except Exception:
        logger.exception("telegram task verification failed")
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


def complete_task(user_id, task_id, bot=None):
    user = get_user(user_id, create=False); task = get_task(task_id)
    if not user or not task or user.get("banned") or user.get("blacklisted") or not task_visible(user_id, task):
        return False, "Unavailable."
    if not task_available(user_id, task_id):
        return False, "Task already completed."

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
    elif verification == "manual":
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
    return True, "OK"


async def complete_task_async(user_id, task_id, bot):
    user = get_user(user_id, create=False); task = get_task(task_id)
    if not user or not task or user.get("banned") or user.get("blacklisted") or not task_visible(user_id, task):
        return False, "Unavailable."
    if not task_available(user_id, task_id):
        return False, "Task already completed."
    verification = _normalise_verification(task.get("verification_method"), task.get("url"))
    if verification == "telegram_join" and not await _verify_telegram_join(bot, user_id, task.get("url")):
        return False, "Please complete the Telegram join task first."
    if verification == "manual":
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
    return True, "OK"


def tasks_menu(user_id=None):
    buttons=[]
    for task in get_tasks(user_id=user_id):
        available = task_available(user_id, task["id"]) if user_id else True
        buttons.append([InlineKeyboardButton(f"{'🎯' if available else '✅'} {task['title']} (+{task.get('reward',0)})", callback_data=f"task_{task['id']}")])
    buttons.append([InlineKeyboardButton("🏠 Home", callback_data="home")])
    return InlineKeyboardMarkup(buttons)


async def tasks_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user; message = update.effective_message
    if not user or not message: return
    db_user=get_user(user.id, create=False)
    if not db_user or db_user.get("banned") or db_user.get("blacklisted"):
        await message.reply_text("🚫 Your account is restricted."); return
    task_list=get_tasks(user_id=user.id); count,_=_daily_count(db_user); settings=db["bot_settings"].find_one({"_id":"main"}) or {}; limit=max(1,_safe_int(settings.get("daily_task_limit"),20))
    if not task_list: text="📋 **TASK CENTER**\n\nNo tasks are available for your membership right now."
    else:
        lines=["📋 **TASK CENTER**", "", f"📊 Daily Tasks: {count}/{limit}", "", "Complete an available task:"]
        for t in task_list: lines.append(f"{'🟢' if task_available(user.id,t['id']) else '✅'} {t['title']} — +{t.get('reward',0)} Points")
        text="\n".join(lines)
    await message.reply_text(text, reply_markup=tasks_menu(user.id), parse_mode="Markdown")


async def task_callback(update, context):
    q=update.callback_query
    if not q or not str(q.data).startswith("task_"): return
    await q.answer(); tid=str(q.data)[5:]; task=get_task(tid)
    if not task or not task_visible(q.from_user.id, task): await q.edit_message_text("⚠️ Task not found or unavailable."); return
    buttons=[]
    if task.get("url"): buttons.append([InlineKeyboardButton("🚀 Open Task", url=task["url"])])
    if task.get("verification_method", DEFAULT_VERIFICATION) == "telegram_join":
        buttons.append([InlineKeyboardButton("✅ Verify Task", callback_data=f"task_complete_{tid}")])
    buttons.append([InlineKeyboardButton("⬅️ Tasks", callback_data="tasks"), InlineKeyboardButton("🏠 Home", callback_data="home")])
    audience = str(task.get("audience", "normal")).upper()
    await q.edit_message_text(f"🎯 **{task['title']}**\n\n{task.get('description','')}\n\n💰 Reward: {task.get('reward',0)} Points\n🏷 Audience: {audience}\n🔐 Verification: {task.get('verification_method','telegram_join')}", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")


async def task_complete_callback(update, context):
    q=update.callback_query
    if not q or not str(q.data).startswith("task_complete_"): return
    await q.answer(); tid=str(q.data)[len("task_complete_"):]; task=get_task(tid)
    if not task: await q.edit_message_text("⚠️ Task not found."); return
    ok,msg=await complete_task_async(q.from_user.id,tid,context.bot)
    await q.edit_message_text((f"🎉 **TASK COMPLETED!**\n\n🎯 {task['title']}\n💰 Reward credited successfully." if ok else f"❌ **Task not completed**\n\n{msg}"), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Tasks",callback_data="tasks")],[InlineKeyboardButton("🏠 Home",callback_data="home")]]), parse_mode="Markdown")


HANDLER_FUNCTIONS={"tasks":tasks_page,"task_callback":task_callback,"task_complete_callback":task_complete_callback}
__all__=["register_task","get_tasks","get_task","set_task_enabled","delete_task","task_available","complete_task","complete_task_async","tasks_menu","tasks_page","task_callback","task_complete_callback","HANDLER_FUNCTIONS","ensure_task_indexes"]
