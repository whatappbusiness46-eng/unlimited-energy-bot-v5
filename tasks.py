# ============================================================
# TASK SYSTEM - MongoDB backed, admin managed
# ============================================================
import logging
import time
from typing import Any, Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db, get_user, update_user, add_balance, add_activity, get_membership_multiplier

logger = logging.getLogger(__name__)
tasks_collection = db["tasks"]
TASK_COOLDOWN = 86400
DEFAULT_REWARD = 10
DEFAULT_XP = 5
DEFAULT_ENERGY = 1


def _now(): return int(time.time())
def _safe_int(v, d=0):
    try: return int(v)
    except (TypeError, ValueError): return d


def ensure_task_indexes():
    """Ensure the task id index exists without IndexOptionsConflict.

    Older deployments may have the same key pattern named differently
    (for example ``id_1``).  MongoDB rejects creating a second index with
    the same key pattern but a different name, so inspect existing indexes
    first and only create/repair what is actually needed.
    """
    try:
        indexes = tasks_collection.index_information()
        for name, info in indexes.items():
            key = info.get("key")
            if key == [("id", 1)]:
                # Reuse an existing unique index. If it is non-unique,
                # replace it so duplicate task IDs cannot be created.
                if info.get("unique", False):
                    return name
                if name != "_id_":
                    tasks_collection.drop_index(name)
                break
        return tasks_collection.create_index(
            [("id", 1)],
            unique=True,
            name="task_id_unique",
        )
    except Exception:
        logger.exception("task index creation failed")
        return None


ensure_task_indexes()

def seed_default_task():
    # No fake/test task is inserted. Admin creates real tasks.
    ensure_task_indexes()


def register_task(task_id: str, title: str, description: str = "", reward: int = DEFAULT_REWARD,
                  url: Optional[str] = None, cooldown: int = TASK_COOLDOWN, enabled: bool = True,
                  xp: int = DEFAULT_XP, energy: int = DEFAULT_ENERGY) -> bool:
    task_id = str(task_id).strip()
    if not task_id or len(task_id) > 50: return False
    doc = {"id": task_id, "title": str(title or task_id)[:120], "description": str(description or "")[:1000],
           "reward": max(0, _safe_int(reward)), "url": url, "cooldown": max(0, _safe_int(cooldown, TASK_COOLDOWN)),
           "enabled": bool(enabled), "xp": max(0, _safe_int(xp, DEFAULT_XP)), "energy": max(0, _safe_int(energy, DEFAULT_ENERGY)),
           "updated_at": _now()}
    try:
        # created_at must exist only in $setOnInsert. Putting the same field
        # in both $set and $setOnInsert causes MongoDB WriteError code 40.
        tasks_collection.update_one(
            {"id": task_id},
            {"$set": doc, "$setOnInsert": {"created_at": _now()}},
            upsert=True,
        )
        return True
    except Exception:
        logger.exception("register task failed")
        return False


def get_tasks(include_disabled=False):
    q = {} if include_disabled else {"enabled": True}
    return list(tasks_collection.find(q, {"_id": 0}).sort("created_at", 1))


def get_task(task_id):
    return tasks_collection.find_one({"id": str(task_id)}, {"_id": 0})


def set_task_enabled(task_id, enabled):
    return tasks_collection.update_one({"id": str(task_id)}, {"$set": {"enabled": bool(enabled), "updated_at": _now()}}).modified_count > 0


def delete_task(task_id):
    return tasks_collection.delete_one({"id": str(task_id)}).deleted_count > 0


def _completed_map(user):
    value = user.get("task_history", {})
    return dict(value) if isinstance(value, dict) else {}


def task_available(user_id, task_id):
    user = get_user(user_id, create=False)
    task = get_task(task_id)
    if not user or user.get("banned") or user.get("blacklisted") or not task or not task.get("enabled", True): return False
    last = _safe_int(_completed_map(user).get(str(task_id)), 0)
    return not last or _now() - last >= max(0, _safe_int(task.get("cooldown"), TASK_COOLDOWN))


def _daily_count(user):
    now = _now(); reset = _safe_int(user.get("task_day_started"), 0)
    if not reset or now - reset >= 86400: return 0, now
    return _safe_int(user.get("daily_task_count"), 0), reset


def complete_task(user_id, task_id):
    user = get_user(user_id, create=False); task = get_task(task_id)
    if not user or not task or not task.get("enabled", True) or user.get("banned") or user.get("blacklisted"): return False, "Unavailable."
    settings = db["bot_settings"].find_one({"_id": "main"}) or {}
    daily_limit = max(1, _safe_int(settings.get("daily_task_limit"), 20))
    count, reset = _daily_count(user)
    if count >= daily_limit: return False, "Daily task limit reached."
    if not task_available(user_id, task_id): return False, "Task is on cooldown."
    energy_cost = max(0, _safe_int(task.get("energy"), 1))
    if energy_cost:
        # use database's atomic energy helper if available
        from database import use_energy
        if not use_energy(user_id, energy_cost): return False, "Not enough Energy."
    reward = max(0, _safe_int(task.get("reward"), 0)); xp = max(0, _safe_int(task.get("xp"), 0))
    try:
        reward = int(round(reward * max(1.0, float(get_membership_multiplier(user_id)))))
    except Exception:
        pass
    history = _completed_map(user); history[str(task_id)] = _now()
    update_user(user_id, {"task_history": history, "daily_task_count": count + 1, "task_day_started": reset})
    if reward: add_balance(user_id, reward)
    if xp:
        from database import add_xp
        add_xp(user_id, xp)
    try:
        from referral import activate_referral
        activate_referral(user_id, "task")
    except Exception:
        logger.exception("Referral activation hook failed")
    try: add_activity(user_id, f"Task completed: {task.get('title')}", reward)
    except Exception: pass
    return True, "OK"


def tasks_menu(user_id=None):
    buttons=[]
    for task in get_tasks():
        available = task_available(user_id, task["id"]) if user_id else True
        buttons.append([InlineKeyboardButton(f"{'🎯' if available else '⏳'} {task['title']} (+{task.get('reward',0)})", callback_data=f"task_{task['id']}")])
    buttons.append([InlineKeyboardButton("🏠 Home", callback_data="home")])
    return InlineKeyboardMarkup(buttons)

async def tasks_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user; message = update.effective_message
    if not user or not message: return
    db_user=get_user(user.id, create=False)
    if not db_user or db_user.get("banned") or db_user.get("blacklisted"):
        await message.reply_text("🚫 Your account is restricted."); return
    task_list=get_tasks(); count,_=_daily_count(db_user); settings=db["bot_settings"].find_one({"_id":"main"}) or {}; limit=max(1,_safe_int(settings.get("daily_task_limit"),20))
    if not task_list: text="📋 **TASK CENTER**\n\nNo tasks are available right now."
    else:
        lines=["📋 **TASK CENTER**","",f"📊 Daily Tasks: {count}/{limit}","","Complete an available task:"]
        for t in task_list: lines.append(f"{'🟢' if task_available(user.id,t['id']) else '🔴'} {t['title']} — +{t.get('reward',0)} Points")
        text="\n".join(lines)
    await message.reply_text(text, reply_markup=tasks_menu(user.id), parse_mode="Markdown")

async def task_callback(update, context):
    q=update.callback_query
    if not q or not str(q.data).startswith("task_"): return
    await q.answer(); tid=str(q.data)[5:]; task=get_task(tid)
    if not task: await q.edit_message_text("⚠️ Task not found."); return
    buttons=[]
    if task.get("url"): buttons.append([InlineKeyboardButton("🚀 Open Task", url=task["url"])])
    buttons.append([InlineKeyboardButton("✅ Verify Task", callback_data=f"task_complete_{tid}")])
    buttons.append([InlineKeyboardButton("⬅️ Tasks", callback_data="tasks"), InlineKeyboardButton("🏠 Home", callback_data="home")])
    await q.edit_message_text(f"🎯 **{task['title']}**\n\n{task.get('description','')}\n\n💰 Reward: {task.get('reward',0)} Points\n⭐ XP: {task.get('xp',0)}\n⚡ Energy: {task.get('energy',0)}", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

async def task_complete_callback(update, context):
    q=update.callback_query
    if not q or not str(q.data).startswith("task_complete_"): return
    await q.answer(); tid=str(q.data)[len("task_complete_"):]; task=get_task(tid)
    if not task: await q.edit_message_text("⚠️ Task not found."); return
    ok,msg=complete_task(q.from_user.id,tid)
    await q.edit_message_text((f"🎉 **TASK COMPLETED!**\n\n🎯 {task['title']}\n💰 +{task.get('reward',0)} Points" if ok else f"❌ **Task not completed**\n\n{msg}"), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Tasks",callback_data="tasks")],[InlineKeyboardButton("🏠 Home",callback_data="home")]]), parse_mode="Markdown")

HANDLER_FUNCTIONS={"tasks":tasks_page,"task_callback":task_callback,"task_complete_callback":task_complete_callback}
__all__=["register_task","get_tasks","get_task","set_task_enabled","delete_task","task_available","complete_task","tasks_menu","tasks_page","task_callback","task_complete_callback","HANDLER_FUNCTIONS","ensure_task_indexes"]
