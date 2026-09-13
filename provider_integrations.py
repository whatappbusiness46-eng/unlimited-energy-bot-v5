# provider_integrations.py
# CPAGrip + Offerwall.me live earning + verified postback integration.

import hashlib
import hmac
import json
import xml.etree.ElementTree as ET
import logging
import os
import secrets
import time
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from database import db, add_balance, add_activity, get_user, record_transaction, remove_balance, get_membership_multiplier

logger = logging.getLogger(__name__)

_PROVIDER_CACHE_TTL = max(10, int(os.getenv("PROVIDER_LIST_CACHE_TTL_SECONDS", "45")))
_provider_cache = {}

def _cache_get(key):
    entry = _provider_cache.get(key)
    if not entry:
        return None
    if time.time() - float(entry.get("ts", 0)) >= _PROVIDER_CACHE_TTL:
        return None
    return list(entry.get("items", []))


def _cache_get_stale(key):
    entry = _provider_cache.get(key)
    if not entry:
        return None
    return list(entry.get("items", []))


def _cache_fresh(key):
    entry = _provider_cache.get(key)
    return bool(entry and time.time() - float(entry.get("ts", 0)) < _PROVIDER_CACHE_TTL)

def _cache_set(key, items):
    _provider_cache[key] = {"ts": time.time(), "items": list(items)}
    return list(items)

def _cache_clear(prefix=None, user_id=None):
    if prefix is None:
        _provider_cache.clear()
        return
    for key in list(_provider_cache):
        if key[0] == prefix and (user_id is None or key[1] == int(user_id)):
            _provider_cache.pop(key, None)

provider_offers = db["provider_offers"]
provider_events = db["provider_events"]
provider_disabled_offers = db["provider_disabled_offers"]
offerwall_task_proofs = db["offerwall_task_proofs"]
provider_pending = db["provider_pending"]

try:
    provider_offers.create_index([("provider", 1), ("offer_id", 1)],
                                 unique=True, name="provider_offer_unique")
    provider_events.create_index([("provider", 1), ("event_id", 1)],
                                 unique=True, name="provider_event_unique")
    provider_disabled_offers.create_index([("provider", 1), ("offer_id", 1)],
                                          unique=True, name="provider_disabled_offer_unique")
    offerwall_task_proofs.create_index([("proof_id", 1)], unique=True, name="offerwall_task_proof_unique")
    offerwall_task_proofs.create_index([("user_id", 1), ("task_id", 1), ("created_at", -1)], name="offerwall_task_proof_user_task")
    provider_pending.create_index([("provider", 1), ("user_id", 1), ("offer_id", 1)], name="provider_pending_lookup")
    provider_pending.create_index([("provider", 1), ("user_id", 1), ("created_at", -1)], name="provider_pending_user_time")
    db["offerwall_task_submissions"].create_index([("user_id", 1), ("task_id", 1)], unique=True, name="offerwall_task_submission_unique")
    db["offerwall_task_submissions"].create_index([("user_id", 1), ("status", 1), ("submitted_at", -1)], name="offerwall_task_submission_status")
except Exception:
    logger.exception("Provider indexes could not be created.")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _enabled(provider: str) -> bool:
    return bool(_env(f"{provider.upper()}_ENABLED", "true").lower() in {"1", "true", "yes", "on"})


def _json_request(url: str, *, method="GET", params=None, headers=None,
                  body=None, timeout=15):
    params = params or {}
    headers = {"User-Agent": "UnlimitedEnergyBot/Final", **(headers or {})}

    if method.upper() == "GET" and params:
        parsed = urlparse(url)
        current = parse_qs(parsed.query, keep_blank_values=True)
        for key, value in params.items():
            current[key] = [str(value)]
        url = urlunparse(parsed._replace(query=urlencode(current, doseq=True)))

    data = None
    if method.upper() != "GET":
        data = json.dumps(body or {}).encode()
        headers.setdefault("Content-Type", "application/json")

    req = Request(url, data=data, headers=headers, method=method.upper())
    with urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw



def create_offerwall_task_proof(user_id: int, task_id: str, telegram_file_id: str, caption: str = ""):
    """Register a Telegram photo proof behind a random public proxy URL.

    The Telegram bot token never leaves the server or appears in the provider-facing URL.
    """
    proof_id = secrets.token_urlsafe(24).replace("-", "_").replace(".", "_")
    doc = {
        "proof_id": proof_id,
        "user_id": int(user_id),
        "task_id": str(task_id),
        "telegram_file_id": str(telegram_file_id),
        "caption": str(caption or "")[:1000],
        "created_at": int(time.time()),
    }
    offerwall_task_proofs.insert_one(doc)
    base = _env("PUBLIC_BASE_URL") or _env("KEEPALIVE_URL") or _env("RENDER_EXTERNAL_URL") or "https://unlimited-energy-bot-v5.onrender.com"
    return f"{base.rstrip('/')}/proof/{proof_id}", proof_id


def get_offerwall_task_proof(proof_id: str):
    if not proof_id:
        return None
    doc = offerwall_task_proofs.find_one({"proof_id": str(proof_id).strip()}, {"_id": 0})
    if not doc:
        return None
    # Proof URLs are short-lived and should not become a permanent file host.
    if int(time.time()) - int(doc.get("created_at", 0) or 0) > 30 * 24 * 3600:
        offerwall_task_proofs.delete_one({"proof_id": str(proof_id).strip()})
        return None
    return doc


def mark_offerwall_task_submission(user_id: int, task_id: str, status: str, **extra):
    doc = {"status": str(status), "updated_at": int(time.time())}
    doc.update(extra)
    return db["offerwall_task_submissions"].update_one(
        {"user_id": int(user_id), "task_id": str(task_id)},
        {"$set": doc, "$setOnInsert": {"user_id": int(user_id), "task_id": str(task_id), "created_at": int(time.time())}},
        upsert=True,
    )


def get_offerwall_task_submission(user_id: int, task_id: str):
    return db["offerwall_task_submissions"].find_one(
        {"user_id": int(user_id), "task_id": str(task_id)}, {"_id": 0}
    )


def _mark_offerwall_submission_from_postback(user_id: int, reward_raw: Any, event_id: str, points: int, offer_type: str = "", offer_name: str = ""):
    """Best-effort match of a verified conversion to a pending task submission.

    Offerwall.me postbacks may not include task_id, so only match a unique/latest pending
    submission for the same user and raw reward. Never invent a task association.
    """
    submissions = db["offerwall_task_submissions"]
    # Offerwall.me may use different labels for task/app/video conversions.
    # If the user has one pending provider task, safely associate the verified
    # postback with that latest task; reward is still controlled by the signed
    # provider callback, never by the client.
    pending_query = {"user_id": int(user_id), "status": "pending"}
    pending = list(submissions.find(
        pending_query,
        {"_id": 0},
    ).sort("submitted_at", -1).limit(10))
    if not pending:
        return None
    raw = str(reward_raw)
    normalized_name = str(offer_name or "").strip().lower()
    matches = [x for x in pending if str(x.get("provider_reward_raw", "")) == raw]
    if normalized_name:
        named = [x for x in matches if normalized_name == str(x.get("task_title", "")).strip().lower()]
        if named:
            matches = named
    target = matches[0] if matches else (pending[0] if len(pending) == 1 else None)
    if not target:
        return None
    submissions.update_one(
        {"user_id": int(user_id), "task_id": str(target.get("task_id")), "status": "pending"},
        {"$set": {"status": "rewarded", "provider_event_id": str(event_id), "reward_points": int(points), "approved_at": int(time.time())}},
    )
    return str(target.get("task_id"))


def _record_provider_pending(provider: str, user_id: int, offer_id: str = "", title: str = "", reward_points: int = 0, reward_raw: Any = ""):
    """Record that a member has started a provider task and is awaiting S2S verification."""
    try:
        now = int(time.time())
        provider_pending.update_one(
            {"provider": str(provider), "user_id": int(user_id), "offer_id": str(offer_id or "")},
            {"$set": {
                "provider": str(provider), "user_id": int(user_id), "offer_id": str(offer_id or ""),
                "title": str(title or "")[:200], "reward_points": int(reward_points or 0),
                "reward_raw": str(reward_raw), "status": "pending", "updated_at": now,
            }, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    except Exception:
        logger.exception("Provider pending record failed | provider=%s user=%s offer=%s", provider, user_id, offer_id)


def _mark_provider_pending_rewarded(provider: str, user_id: int, event_id: str, points: int, offer_id: str = ""):
    """Mark the matching pending provider task as verified/rewarded."""
    try:
        q = {"provider": str(provider), "user_id": int(user_id), "status": "pending"}
        if offer_id:
            q["offer_id"] = str(offer_id)
        result = provider_pending.update_one(
            q, {"$set": {"status": "rewarded", "provider_event_id": str(event_id), "credited_points": int(points), "verified_at": int(time.time())}}
        )
        return bool(result.modified_count)
    except Exception:
        logger.exception("Provider pending reward update failed | provider=%s user=%s", provider, user_id)
        return False


def _notify_user_verified(user_id: int, provider: str, points: int, title: str = ""):
    """Send a verified-reward notification using the configured BOT_TOKEN only."""
    token = _env("BOT_TOKEN")
    if not token:
        logger.warning("BOT_TOKEN unavailable for reward notification | user=%s", user_id)
        return False
    provider_label = {"cpalead": "CPAlead", "cpagrip": "CPAGrip", "offerwallme": "Offerwall.me"}.get(str(provider), str(provider))
    safe_title = str(title or "Task").replace("<", "&lt;").replace(">", "&gt;")[:120]
    text = (
        "🎉 <b>Task Verified!</b>\n\n"
        f"🎯 {safe_title}\n"
        f"💰 <b>+{int(points)} Points</b> added to your balance.\n"
        f"✅ Verified by {provider_label}."
    )
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urlencode({"chat_id": str(int(user_id)), "text": text, "parse_mode": "HTML"}).encode("utf-8")
        req = Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "UnlimitedEnergyBot/RewardNotify"}, method="POST")
        with urlopen(req, timeout=5) as response:
            return 200 <= int(getattr(response, "status", 200)) < 300
    except Exception:
        logger.exception("Reward notification failed | provider=%s user=%s", provider, user_id)
        return False


def _offerwallme_credentials():
    return _env("OFFERWALLME_API_KEY"), _env("OFFERWALLME_BEARER_TOKEN")


def _offerwallme_public_ip():
    configured = _env("OFFERWALLME_DEFAULT_IP")
    if configured and configured not in {"0.0.0.0", "127.0.0.1"}:
        return configured
    cache = getattr(_offerwallme_public_ip, "_cache", None)
    now = time.time()
    if cache and now - cache.get("ts", 0) < 3600 and cache.get("ip"):
        return cache["ip"]
    try:
        req = Request("https://api.ipify.org", headers={"User-Agent": "UnlimitedEnergyBot/Final"})
        with urlopen(req, timeout=5) as response:
            ip = response.read().decode("utf-8", errors="replace").strip()
        if ip:
            _offerwallme_public_ip._cache = {"ip": ip, "ts": now}
            return ip
    except Exception:
        logger.warning("Offerwall.me public IP lookup failed", exc_info=True)
    return configured or "127.0.0.1"


def _offerwallme_request(endpoint: str, user_id: int, *, method="GET", body=None):
    api_key, bearer = _offerwallme_credentials()
    if not api_key or not bearer:
        return {"status": 0, "error": "missing_offerwallme_credentials"}
    params = {
        "api": api_key,
        "id": str(user_id),
        "ip": _offerwallme_public_ip(),
        "token": bearer,
        "country": _env("OFFERWALLME_COUNTRY", "BD").upper(),
    }
    endpoint = str(endpoint or "").strip()
    if not endpoint:
        return {"status": 0, "error": "missing_endpoint"}
    if method.upper() == "POST":
        payload = dict(body or {})
        payload.update(params)
        return _json_request(endpoint, method="POST", body=payload)
    return _json_request(endpoint, method="GET", params=params)


def _offerwallme_list(payload):
    """Extract provider items from common Offerwall.me response envelopes."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("offers", "tasks", "shortlinks", "results", "items", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    for key in ("offers", "tasks", "shortlinks", "results", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def _offerwallme_form_request(endpoint: str, params: Dict[str, Any]):
    """POST form data for Offerwall.me PHP endpoints.

    PHP task endpoints commonly read fields from ``$_POST``; JSON-only POSTs
    can therefore look empty even though the same fields were supplied.
    """
    endpoint = str(endpoint or "").strip()
    headers = {
        "User-Agent": "UnlimitedEnergyBot/Final",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = urlencode({str(k): str(v) for k, v in (params or {}).items() if v is not None}).encode("utf-8")
    req = Request(endpoint, data=data, headers=headers, method="POST")
    with urlopen(req, timeout=15) as response:
        raw = response.read().decode("utf-8", errors="replace")
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw


def get_offerwallme_offers(user_id: int, force_refresh: bool = False):
    if not _enabled("offerwallme"):
        return []
    cache_key = ("offerwallme_offers", int(user_id))
    cached = None if force_refresh else _cache_get(cache_key)
    if cached is not None:
        return cached
    payload = _offerwallme_request(
        _env("OFFERWALLME_OFFERS_API_URL", "https://offerwall.me/offerapi.php"),
        user_id,
    )
    result = []
    for raw in _offerwallme_list(payload):
        if not isinstance(raw, dict):
            continue
        offer_id = _first(raw, ("id", "offer_id", "offerId"))
        url = _first(raw, ("url", "link", "tracking_url"))
        if not offer_id or not url:
            continue
        result.append({
            "provider": "offerwallme",
            "offer_id": str(offer_id),
            "title": str(_first(raw, ("title", "name"), "Offerwall.me Offer")),
            "description": str(_first(raw, ("description", "desc"), "") or ""),
            "url": str(url),
            "provider_reward": _first(raw, ("reward", "payout"), 0),
            "category": str(_first(raw, ("category", "provider", "type"), "") or ""),
            "platform": str(_first(raw, ("devices", "device", "platform"), "") or ""),
            "updated_at": int(time.time()),
        })
    return _cache_set(cache_key, result)


def sync_offerwallme_offers(user_id: int) -> int:
    offers = get_offerwallme_offers(user_id)
    for offer in offers:
        provider_offers.update_one(
            {"provider": "offerwallme", "offer_id": offer["offer_id"]},
            {"$set": offer},
            upsert=True,
        )
    return len(offers)


def get_offerwallme_tasks(user_id: int, force_refresh: bool = False):
    if not _enabled("offerwallme"):
        return []
    cache_key = ("offerwallme_tasks", int(user_id))
    cached = None if force_refresh else _cache_get(cache_key)
    if cached is not None:
        return cached
    payload = _offerwallme_request(
        _env("OFFERWALLME_TASKS_API_URL", "https://offerwall.me/taskapi.php"),
        user_id,
    )
    result = []
    for raw in _offerwallme_list(payload):
        if not isinstance(raw, dict):
            continue
        task_id = _first(raw, ("id", "task_id", "taskId"))
        if not task_id:
            continue
        task_url = _first(
            raw,
            ("url", "link", "task_url", "taskUrl", "tracking_url", "click_url", "offer_url"),
            "",
        )
        reward = _first(
            raw,
            (
                "reward", "payout", "amount", "points", "value",
                "user_reward", "userReward", "reward_points", "rewardPoints",
            ),
            0,
        )
        title = str(_first(raw, ("title", "name", "task_title", "taskTitle"), "Offerwall Task") or "Offerwall Task")
        description = str(_first(raw, ("description", "desc", "details", "task_description"), "") or "")
        instructions = str(_first(raw, ("instructions", "instruction", "steps"), "") or "")
        offer_type = str(_first(raw, ("offer_type", "offerType", "task_type", "taskType", "type", "category", "vertical"), "") or "")
        platform = str(_first(raw, ("platform", "device", "devices", "os"), "") or "")
        result.append(
            dict(
                raw,
                title=title,
                description=description,
                instructions=instructions,
                proof_type=str(_first(raw, ("proof_type", "proofType", "proof", "verification_type"), "Text") or "Text"),
                proof_text=str(_first(raw, ("proof_text", "proofText", "proof_instruction", "proofInstruction"), "Submit the required proof") or "Submit the required proof"),
                id=str(task_id),
                reward=reward,
                url=str(task_url or ""),
                offer_type=offer_type,
                platform=platform,
            )
        )
    return _cache_set(cache_key, result)


def submit_offerwallme_task_proof(user_id: int, task_id: str, proof: str):
    if not _enabled("offerwallme"):
        return {"ok": False, "error": "provider_disabled"}

    api_key, bearer = _offerwallme_credentials()
    if not api_key or not bearer:
        return {"ok": False, "error": "missing_offerwallme_credentials"}

    endpoint = _env("OFFERWALLME_TASK_SUBMIT_API_URL", "https://offerwall.me/tasksubmit.php")
    proof_value = str(proof or "").strip()
    params = {
        "api": api_key,
        "id": str(user_id),
        "ip": _offerwallme_public_ip(),
        "token": bearer,
        "country": _env("OFFERWALLME_COUNTRY", "BD").upper(),
        "task_id": str(task_id),
        "proof": proof_value,
    }
    # Keep the canonical fields above and also expose the proof URL separately
    # when the Telegram image resolver produced one. This is harmless for PHP
    # endpoints that ignore unknown POST fields and lets providers that expect
    # a URL consume the image proof directly.
    if proof_value.startswith("proof_url:"):
        params["proof_url"] = proof_value.split(":", 1)[1].strip()
        params["proof_type"] = "image"

    try:
        payload = _offerwallme_form_request(endpoint, params)
    except Exception as exc:
        logger.exception("Offerwall.me task proof request failed | user=%s task=%s", user_id, task_id)
        return {"ok": False, "error": "request_failed", "detail": str(exc)}

    if isinstance(payload, dict):
        status = str(payload.get("status") or "").strip().lower()
        ok_value = payload.get("ok")
        ok = bool(ok_value) or status in {"200", "success", "approved", "pending", "submitted", "1", "true"}
        return {
            "ok": ok,
            "raw": payload,
            **({k: payload[k] for k in ("message", "status") if k in payload}),
        }

    text = str(payload or "").strip().lower()
    ok = any(token in text for token in ("success", "approved", "pending", "submitted", "received"))
    return {"ok": ok, "raw": payload, "message": str(payload or "")}


def get_offerwallme_shortlinks(user_id: int, force_refresh: bool = False):
    if not _enabled("offerwallme"):
        return []
    cache_key = ("offerwallme_shortlinks", int(user_id))
    cached = None if force_refresh else _cache_get(cache_key)
    if cached is not None:
        return cached
    payload = _offerwallme_request(
        _env("OFFERWALLME_SHORTLINKS_API_URL", "https://offerwall.me/slapi.php"),
        user_id,
    )
    result = []
    for raw in _offerwallme_list(payload):
        if not isinstance(raw, dict):
            continue
        link_id = _first(raw, ("id", "shortlink_id", "shortlinkId"))
        url = _first(raw, ("url", "link", "tracking_url", "shortlink"))
        if not link_id or not url:
            continue
        result.append({
            "provider": "offerwallme",
            "id": str(link_id),
            "title": str(_first(raw, ("title", "name"), "Offerwall.me Shortlink")),
            "description": str(_first(raw, ("description", "desc"), "") or ""),
            "url": str(url),
            "reward": _first(raw, ("reward", "points", "amount"), 0),
            "interval": _first(raw, ("interval", "cooldown"), 0),
        })
    return _cache_set(cache_key, result)


def _first(data, keys, default=None):
    if not isinstance(data, dict):
        return default
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return default


def _extract_offer_list(payload):
    """Extract offers from JSON or CPAGrip RSS/XML feeds.

    CPAGrip documents RSS/XML offer feeds as supported feed formats, so the
    parser accepts both common JSON envelopes and RSS <item> entries.
    """
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("offers", "data", "results", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                for subkey in ("offers", "items", "results"):
                    if isinstance(value.get(subkey), list):
                        return value[subkey]
        return []
    if not isinstance(payload, str):
        return []

    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return []

    def text(node, *names):
        for child in list(node):
            tag = child.tag.rsplit("}", 1)[-1].lower()
            if tag in names and child.text:
                return child.text.strip()
        return ""

    items = []
    # CPAGrip's documented RSS feed uses <offers><offer>...</offer></offers>
    # rather than a standard RSS <item> envelope. Accept both formats.
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1].lower()
        if tag not in {"item", "offer"}:
            continue
        raw = {
            "title": text(node, "title", "name", "offer_title"),
            "description": text(node, "description", "desc", "details"),
            "link": text(
                node,
                "offerlink", "offer_link", "link", "url",
                "click_url", "tracking_url"
            ),
            "offer_id": text(
                node,
                "offer_id", "offerid", "id", "guid", "offerid"
            ),
            "payout": text(
                node,
                "payout", "reward", "amount", "commission", "revenue"
            ),
            "category": text(node, "category", "vertical", "type"),
            "platform": text(node, "platform", "device", "os"),
        }
        if raw["offer_id"] or raw["link"] or raw["title"]:
            items.append(raw)
    return items


def _with_tracking_id(url: str, user_id: int) -> str:
    """Attach CPAGrip's documented tracking_id/subid to an offer URL."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query["tracking_id"] = [str(user_id)]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def _normalise_offer(raw, user_id):
    offer_id = _first(raw, ("offer_id", "id", "offerId", "campaign_id", "campaignId"))
    title = _first(raw, ("title", "name", "offer_name", "offerName"), "CPAGrip Offer")
    url = _first(raw, ("url", "link", "click_url", "tracking_url", "offer_url"))
    if not offer_id or not url:
        return None
    try:
        payout = float(_first(raw, ("payout", "amount", "revenue", "commission", "reward"), 0))
    except (TypeError, ValueError):
        payout = 0.0
    return {
        "provider": "cpagrip",
        "offer_id": str(offer_id),
        "title": str(title),
        "description": str(_first(raw, ("description", "desc", "details"), "") or ""),
        "url": _with_tracking_id(
            str(url).replace("{user_id}", str(user_id)).replace("{uid}", str(user_id)),
            user_id,
        ),
        "provider_reward": payout,
        "category": str(_first(raw, ("category", "vertical", "type"), "") or ""),
        "platform": str(_first(raw, ("platform", "device", "os"), "") or ""),
        "updated_at": int(time.time()),
    }


def sync_cpagrip_offers(user_id: int) -> int:
    if not _enabled("cpagrip"):
        return 0
    template = _env("CPAGRIP_OFFERS_API_URL")
    if not template:
        return 0

    url = template.replace("{user_id}", str(user_id))
    url = url.replace("{uid}", str(user_id))
    url = url.replace("{api_key}", _env("CPAGRIP_API_KEY"))

    params = {}
    if "?" not in url:
        # Only send this if the configured endpoint has not already
        # supplied its own user parameter.
        params["user_id"] = user_id

    try:
        payload = _json_request(url, params=params)
        count = 0
        for raw in _extract_offer_list(payload):
            if not isinstance(raw, dict):
                continue
            offer = _normalise_offer(raw, user_id)
            if not offer:
                continue
            key = {"provider": "cpagrip", "offer_id": offer["offer_id"]}
            existing = provider_offers.find_one(key, {"_id": 0, "custom_reward_locked": 1}) or {}
            update = {"$set": offer}
            if not existing.get("custom_reward_locked", False):
                update["$unset"] = {"custom_reward_points": ""}
            provider_offers.update_one(key, update, upsert=True)
            count += 1
        if count == 0:
            logger.warning("CPAGrip feed returned no parseable offers | user=%s | url=%s", user_id, url.split("?")[0])
        _cache_clear("cpagrip_offers", user_id)
        return count
    except Exception:
        logger.exception("CPAGrip offer sync failed | user=%s", user_id)
        return 0



def _cpa_lead_member_reward_points(payout, user_id=None):
    try:
        payout_d = Decimal(str(payout))
        share = Decimal(_env("CPALEAD_USER_REWARD_PERCENT", "40"))
        rate = Decimal(_env("CPALEAD_POINTS_PER_USD", _env("REWARD_POINTS_PER_USD", "1000")))
        if payout_d <= 0 or share <= 0 or rate <= 0:
            return 0
        points = int((payout_d * share / Decimal("100") * rate).quantize(Decimal("1")))
        if user_id is not None:
            try:
                mult = Decimal(str(get_membership_multiplier(int(user_id))))
                if mult > 0:
                    points = int((Decimal(points) * mult).quantize(Decimal("1")))
            except Exception:
                pass
        return max(1, points)
    except (InvalidOperation, ValueError, TypeError):
        return 0


def _cpa_lead_offer_url(item, user_id):
    url = str(item.get("link") or item.get("url") or "").strip()
    if not url:
        return ""
    parsed = urlparse(url)
    q = parse_qs(parsed.query, keep_blank_values=True)
    q["subid"] = [str(int(user_id))]
    return urlunparse(parsed._replace(query=urlencode(q, doseq=True)))


def _sync_cpa_lead_bd_offers(user_id: int):
    if not _enabled("cpalead"):
        return []
    publisher_id = _env("CPALEAD_PUBLISHER_ID")
    if not publisher_id:
        return []
    limit = max(1, min(100, int(_env("CPALEAD_BD_TASK_LIMIT", "20"))))
    url = "https://www.cpalead.com/api/offers"
    fields = "id,title,description,long_description,link,preview_link,amount,payout_currency,payout_type,countries,payouts_per_country,events,conversion_mode,verification_method,device,offer_rank"
    try:
        # CPAlead's current Publisher Offers API supports country/device/type filters.
        # Keep the tracking link returned by CPAlead; only add our Telegram subid later.
        payload = _json_request(
            url,
            params={
                "id": publisher_id,
                "country": "BD",
                # Do not use device=user here because the request originates
                # from the Render server, not the Telegram user's device.
                # Fetch all device types and let CPAlead's returned tracking
                # link perform the correct offer targeting.
                "type": "cpa,cpi,cpe",
                "limit": limit,
                "fields": fields,
            },
            timeout=12,
        )
        raw = []
        if isinstance(payload, list):
            raw = payload
        elif isinstance(payload, dict):
            raw = payload.get("offers") or payload.get("data") or payload.get("results") or []
            if isinstance(raw, dict):
                raw = raw.get("offers") or raw.get("data") or raw.get("results") or []
        out = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            oid = str(item.get("id") or "").strip()
            link = str(item.get("link") or "").strip()
            if not oid or not link:
                continue
            payout = item.get("amount", 0)
            # CPAlead currently returns payouts_per_country as a BD-keyed map,
            # but older responses may return a list of country rows. Support both.
            country_payouts = item.get("payouts_per_country") or {}
            if isinstance(country_payouts, dict):
                payout = country_payouts.get("BD", country_payouts.get("bd", payout))
            elif isinstance(country_payouts, list):
                for row in country_payouts:
                    if isinstance(row, dict) and str(row.get("country") or row.get("country_iso") or "").upper() == "BD":
                        payout = row.get("amount", payout)
                        break
            doc = {
                "provider": "cpalead",
                "offer_id": oid,
                "title": str(item.get("title") or "BD Task"),
                "description": str(item.get("description") or item.get("long_description") or ""),
                "url": link,
                "provider_reward": float(payout or 0),
                "payout_currency": str(item.get("payout_currency") or "USD"),
                "payout_type": str(item.get("payout_type") or "CPA"),
                "countries": item.get("countries") or ["BD"],
                "events": item.get("events") or [],
                "updated_at": int(time.time()),
            }
            out.append(doc)
            provider_offers.update_one({"provider":"cpalead", "offer_id":oid}, {"$set":doc}, upsert=True)
        _cache_set(("cpalead_bd_offers", int(user_id)), out)
        return out
    except Exception:
        logger.exception("CPAlead BD offer sync failed | user=%s", user_id)
        return _cache_get_stale(("cpalead_bd_offers", int(user_id))) or []


def get_cpa_lead_bd_offers(user_id: int, force_refresh=False):
    key=("cpalead_bd_offers", int(user_id))
    cached=None if force_refresh else _cache_get(key)
    if cached is not None:
        return cached
    return _sync_cpa_lead_bd_offers(user_id)


def get_cached_cpa_lead_bd_offers(user_id: int):
    return _cache_get_stale(("cpalead_bd_offers", int(user_id)))


def refresh_cpa_lead_bd_offers(user_id: int):
    _cache_clear("cpalead_bd_offers", user_id)
    return get_cpa_lead_bd_offers(user_id, force_refresh=True)

def get_provider_offers(user_id: int, providers: Optional[Iterable[str]] = None, force_refresh: bool = False):
    providers = [p.lower() for p in (providers or ("cpagrip", "cpalead"))]
    providers = [p for p in providers if p in {"cpagrip", "cpalead"} and _enabled(p)]
    if not providers:
        return []
    cache_key = ("provider_offers", int(user_id), tuple(providers))
    cached = None if force_refresh else _cache_get(cache_key)
    if cached is not None:
        return cached
    for provider in providers:
        if provider == "cpagrip":
            sync_cpagrip_offers(user_id)
        elif provider == "cpalead":
            _sync_cpa_lead_bd_offers(user_id)
    disabled = {str(x["offer_id"]) for x in provider_disabled_offers.find({"provider": {"$in": providers}}, {"offer_id": 1})}
    docs = provider_offers.find({"provider": {"$in": providers}}, {"_id": 0}).sort("updated_at", -1).limit(100)
    result = [dict(x) for x in docs if str(x.get("offer_id")) not in disabled]
    # The public Offers page reads its short-lived cache through
    # get_cached_provider_offers(). Keep that cache populated after a live
    # provider sync; otherwise the provider can return offers successfully
    # while the UI still says "No live offers".
    if "cpagrip" in providers:
        _cache_set(("cpagrip_offers", int(user_id)), result)
    return _cache_set(cache_key, result)


def set_provider_offer_enabled(provider: str, offer_id: str, enabled: bool):
    provider, offer_id = provider.lower().strip(), str(offer_id).strip()
    if provider not in {"cpagrip", "offerwallme"} or not offer_id:
        return False
    if enabled:
        provider_disabled_offers.delete_one({"provider": provider, "offer_id": offer_id})
    else:
        provider_disabled_offers.update_one(
            {"provider": provider, "offer_id": offer_id},
            {"$set": {"provider": provider, "offer_id": offer_id, "updated_at": int(time.time())}},
            upsert=True,
        )
    return True


def delete_provider_offer(provider: str, offer_id: str):
    provider, offer_id = provider.lower().strip(), str(offer_id).strip()
    if provider not in {"cpagrip", "offerwallme"} or not offer_id:
        return False
    provider_offers.delete_one({"provider": provider, "offer_id": offer_id})
    provider_disabled_offers.delete_one({"provider": provider, "offer_id": offer_id})
    return True


def _reward_points(reward):
    """Calculate the CPAGrip member reward from the real provider payout.

    CPAGrip payout values are treated as USD. The member receives the
    configured percentage of that payout, converted with REWARD_POINTS_PER_USD.
    The old fixed 200-point value remains only as a safe fallback when a
    provider payout is missing/invalid, so existing offers never break.
    """
    try:
        payout = Decimal(str(reward))
        share = Decimal(_env("CPAGRIP_USER_REWARD_PERCENT", "40"))
        rate = Decimal(_env("REWARD_POINTS_PER_USD", "1000"))
        if payout > 0 and share > 0 and rate > 0:
            points = int((payout * share / Decimal("100") * rate).quantize(Decimal("1")))
            if points > 0:
                return points
    except (InvalidOperation, ValueError, TypeError):
        pass
    try:
        fallback = int(_env("CPAGRIP_DEFAULT_USER_REWARD_POINTS", "200"))
    except (TypeError, ValueError):
        fallback = 200
    return max(1, fallback)


def _verify_postback(provider: str, params: Dict[str, Any]) -> bool:
    """Verify provider S2S callback using the provider's documented password.

    CPAGrip's Global Postback sends a POST field named ``password``. It does
    not document an HMAC signature in the supplied integration specification,
    so we do not require one.
    """
    provider = provider.upper()
    secret = _env(f"{provider}_POSTBACK_PASSWORD") or _env(f"{provider}_POSTBACK_SECRET")
    if not secret:
        return False
    supplied = str(params.get("password") or "").strip()
    return bool(supplied) and hmac.compare_digest(supplied, secret)


def _offerwallme_reward_points(reward_raw: Any, user_id: int = None) -> int:
    """Convert Offerwall.me's placement-currency reward into member points.

    The publisher placement currently uses ``Points`` as its currency, so the
    provider's ``reward`` value is treated as placement points by default.
    ``OFFERWALLME_REWARD_UNIT=usd`` can be used only if the placement/API is
    actually configured to return USD. Members receive the configured share;
    VIP membership multipliers are applied only after that base share.
    """
    try:
        reward = Decimal(str(reward_raw))
        share = Decimal(_env("OFFERWALLME_USER_REWARD_PERCENT", "40"))
        unit = _env("OFFERWALLME_REWARD_UNIT", "points").lower()
        rate = Decimal(_env("OFFERWALLME_POINTS_PER_USD", "1000"))
        if reward <= 0 or share <= 0:
            return 0

        if unit in {"usd", "dollar", "dollars"}:
            if rate <= 0:
                return 0
            base_points = reward * rate
        else:
            # Offerwall.me placement currency is Points by default.
            base_points = reward

        points = int((base_points * share / Decimal("100")).quantize(Decimal("1")))
        if user_id is not None:
            try:
                multiplier = Decimal(str(get_membership_multiplier(int(user_id))))
                if multiplier > 0:
                    points = int((Decimal(points) * multiplier).quantize(Decimal("1")))
            except (ValueError, TypeError, InvalidOperation):
                pass
        return max(1, points)
    except (InvalidOperation, ValueError, TypeError):
        return 0


def _offerwallme_signature_valid(params: Dict[str, Any]) -> bool:
    """Verify Offerwall.me's documented MD5 postback signature.

    Formula from Offerwall.me documentation:
        md5(subId + transId + reward + secretKey)
    """
    secret = _env("OFFERWALLME_POSTBACK_SECRET")
    if not secret:
        return False

    sub_id = params.get("subId")
    trans_id = params.get("transId")
    reward = params.get("reward")
    supplied = str(params.get("signature") or "").strip().lower()
    if sub_id in (None, "") or trans_id in (None, "") or reward in (None, "") or not supplied:
        return False

    raw = f"{sub_id}{trans_id}{reward}{secret}"
    expected = hashlib.md5(raw.encode("utf-8")).hexdigest().lower()
    return hmac.compare_digest(supplied, expected)


def _process_offerwallme_postback(params: Dict[str, Any]):
    if not _enabled("offerwallme"):
        return {"ok": False, "error": "provider_disabled"}
    if not _env("OFFERWALLME_POSTBACK_SECRET"):
        return {"ok": False, "error": "missing_postback_secret"}

    # Offerwall.me uses these exact parameter names.
    user_raw = params.get("subId")
    trans_id = str(params.get("transId") or "").strip()
    reward_raw = params.get("reward")
    status = str(params.get("status") or "").strip()

    if user_raw in (None, ""):
        return {"ok": False, "error": "missing_user"}
    try:
        user_id = int(str(user_raw).strip())
    except (TypeError, ValueError):
        return {"ok": False, "error": "invalid_user_id"}
    if not get_user(user_id, create=False):
        return {"ok": False, "error": "user_not_found"}

    if not trans_id:
        return {"ok": False, "error": "missing_transaction_id"}
    if reward_raw in (None, ""):
        return {"ok": False, "error": "missing_reward"}

    if not _offerwallme_signature_valid(params):
        return {"ok": False, "error": "invalid_signature"}

    event_id = trans_id
    existing = provider_events.find_one({"provider": "offerwallme", "event_id": event_id})

    # Offerwall.me status 2 is reserved for chargebacks/reversals.
    if status == "2":
        if not existing:
            return {"ok": True, "message": "reversal_ignored_unknown_event"}
        if existing.get("status") == "2" or existing.get("reversed_at"):
            return {"ok": True, "message": "duplicate_reversal_ignored"}

        points = int(existing.get("points") or 0)
        removed = remove_balance(user_id, points) if points > 0 else 0
        debt = max(0, points - int(removed or 0))
        if debt:
            db["users"].update_one({"user_id": int(user_id)}, {"$inc": {"provider_debt": debt}})
            try:
                record_transaction(user_id, "offerwallme_reversal_debt", debt, event_id, metadata={"provider": "offerwallme"})
            except Exception:
                logger.exception("Offerwall.me reversal debt transaction failed | event=%s", event_id)
        provider_events.update_one(
            {"_id": existing["_id"]},
            {"$set": {"status": "2", "reversed_at": int(time.time()), "reversal_removed": int(removed or 0), "reversal_debt": debt}},
        )
        return {"ok": True, "message": "reversal_recorded", "removed": int(removed or 0), "debt": debt}

    if status not in {"", "1"}:
        return {"ok": True, "message": "ignored_status"}

    if existing:
        return {"ok": True, "message": "duplicate_ignored"}

    points = _offerwallme_reward_points(reward_raw, user_id)
    if points <= 0:
        return {"ok": False, "error": "invalid_reward"}

    event_doc = {
        "provider": "offerwallme",
        "event_id": event_id,
        "user_id": user_id,
        "reward_raw": str(reward_raw),
        "points": points,
        "status": "1",
        "received_at": int(time.time()),
        "params": {str(k): str(v) for k, v in params.items()},
    }
    try:
        provider_events.insert_one(event_doc)
    except Exception as exc:
        if "duplicate" in str(exc).lower() or "e11000" in str(exc).lower():
            return {"ok": True, "message": "duplicate_ignored"}
        logger.exception("Offerwall.me event insert failed")
        return {"ok": False, "error": "event_store_failed"}

    if not add_balance(user_id, points):
        provider_events.delete_one({"provider": "offerwallme", "event_id": event_id})
        return {"ok": False, "error": "credit_failed"}

    try:
        record_transaction(user_id, "offerwallme_conversion", points, event_id)
    except Exception:
        logger.exception("Offerwall.me transaction record failed | event=%s", event_id)
    try:
        add_activity(user_id, "💸 Offerwall.me conversion", points)
    except Exception:
        logger.exception("Offerwall.me activity log failed | user=%s", user_id)
    matched_task_id = _mark_offerwall_submission_from_postback(user_id, reward_raw, event_id, points, params.get("offer_type"), params.get("offer_name"))
    offer_title = str(params.get("offer_name") or params.get("offer_type") or "Rewards Task")
    _mark_provider_pending_rewarded("offerwallme", user_id, event_id, points, str(params.get("offer_id") or params.get("offerId") or ""))
    _notify_user_verified(user_id, "offerwallme", points, offer_title)

    return {"ok": True, "message": "credited", "provider": "offerwallme", "event_id": event_id, "user_id": user_id, "points": points, **({"task_id": matched_task_id} if matched_task_id else {})}

def process_postback(provider: str, params: Dict[str, Any]):
    provider = str(provider).lower().strip()
    if provider == "offerwallme":
        return _process_offerwallme_postback(params)
    if provider == "cpalead":
        if not _enabled("cpalead"):
            return {"ok": False, "error": "provider_disabled"}
        secret = _env("CPALEAD_POSTBACK_PASSWORD")
        supplied = str(params.get("password") or "").strip()
        if secret and (not supplied or not hmac.compare_digest(supplied, secret)):
            return {"ok": False, "error": "invalid_signature"}
        user_raw = params.get("subid") or params.get("sub_id") or params.get("user_id")
        if user_raw in (None, ""):
            return {"ok": False, "error": "missing_user"}
        try:
            user_id = int(str(user_raw).strip())
        except (TypeError, ValueError):
            return {"ok": False, "error": "invalid_user_id"}
        if not get_user(user_id, create=False):
            return {"ok": False, "error": "user_not_found"}
        event_id = str(params.get("lead_id") or params.get("transaction_id") or params.get("event_id") or "").strip()
        if not event_id:
            return {"ok": False, "error": "missing_event_id"}
        payout_raw = params.get("payout") if params.get("payout") not in (None, "") else params.get("event_payout", params.get("amount", 0))
        try:
            payout = Decimal(str(payout_raw))
        except Exception:
            return {"ok": False, "error": "invalid_payout"}
        status = str(params.get("status") or params.get("event") or "approved").lower()
        existing = provider_events.find_one({"provider":"cpalead", "event_id":event_id})
        reversal = status in {"2","reversed","reverse","chargeback","charged_back","reject","rejected"} or payout < 0
        if reversal:
            if not existing:
                return {"ok": True, "message": "reversal_ignored_unknown_event"}
            if existing.get("reversed_at") or str(existing.get("status")) in {"2","reversed","reverse","chargeback","charged_back","reject","rejected"}:
                return {"ok": True, "message": "duplicate_reversal_ignored"}
            points = int(existing.get("points") or 0)
            removed = remove_balance(user_id, points) if points > 0 else 0
            debt=max(0, points-int(removed or 0))
            if debt:
                db["users"].update_one({"user_id":int(user_id)}, {"$inc":{"provider_debt":debt}})
            provider_events.update_one({"_id":existing["_id"]}, {"$set":{"status":"2","reversed_at":int(time.time()),"reversal_removed":int(removed or 0),"reversal_debt":debt}})
            return {"ok":True,"message":"reversal_recorded","removed":int(removed or 0),"debt":debt}
        if existing:
            return {"ok": True, "message": "duplicate_ignored"}
        points = _cpa_lead_member_reward_points(payout, user_id)
        if points <= 0:
            return {"ok": False, "error": "invalid_reward"}
        offer_id = str(params.get("campaign_id") or params.get("offer_id") or "").strip()
        offer_title = str(params.get("campaign_name") or params.get("offer_name") or "BD Task")
        doc={"provider":"cpalead","event_id":event_id,"user_id":user_id,"offer_id":offer_id,"offer_title":offer_title,"provider_reward":float(payout),"reward_raw":str(payout_raw),"points":points,"status":"approved","country":str(params.get("country_iso") or "BD"),"received_at":int(time.time()),"params":{str(k):str(v) for k,v in params.items()}}
        try:
            provider_events.insert_one(doc)
        except Exception as exc:
            if "duplicate" in str(exc).lower() or "e11000" in str(exc).lower():
                return {"ok":True,"message":"duplicate_ignored"}
            return {"ok":False,"error":"event_store_failed"}
        if not add_balance(user_id, points):
            provider_events.delete_one({"provider":"cpalead","event_id":event_id})
            return {"ok":False,"error":"credit_failed"}
        try:
            record_transaction(user_id,"cpalead_conversion",points,event_id,metadata={"provider":"cpalead","offer_id":offer_id,"payout":str(payout_raw)})
            add_activity(user_id,"🇧🇩 CPAlead task conversion",points)
        except Exception:
            logger.exception("CPAlead transaction/activity failed | event=%s",event_id)
        _mark_provider_pending_rewarded("cpalead", user_id, event_id, points, offer_id)
        _notify_user_verified(user_id, "cpalead", points, offer_title)
        return {"ok":True,"message":"credited","provider":"cpalead","event_id":event_id,"user_id":user_id,"points":points}
    if provider != "cpagrip" or not _enabled("cpagrip"):
        return {"ok": False, "error": "provider_disabled"}

    event_id = str(
        params.get("event_id") or params.get("transaction_id") or params.get("transactionid") or
        params.get("trans_id") or params.get("transId") or params.get("txn") or
        params.get("conversion_id") or params.get("lead_id") or ""
    ).strip()
    user_raw = (params.get("tracking_id") or params.get("subid") or params.get("sub_id") or
                params.get("user_id") or params.get("uid"))
    reward_raw = params.get("reward") if params.get("reward") not in (None, "") else params.get("payout", params.get("amount", 0))
    status = str(params.get("status") or params.get("event") or "approved").lower()

    if user_raw in (None, ""):
        return {"ok": False, "error": "missing_user"}
    if not event_id:
        fingerprint = "|".join([
            str(params.get("tracking_id", "")),
            str(params.get("offer_id", "")),
            str(params.get("payout", "")),
            str(params.get("status", "")),
        ])
        event_id = "cpagrip:" + hashlib.sha256(fingerprint.encode()).hexdigest()

    try:
        user_id = int(str(user_raw))
    except (TypeError, ValueError):
        return {"ok": False, "error": "invalid_user_id"}
    if not get_user(user_id, create=False):
        return {"ok": False, "error": "user_not_found"}
    if not _verify_postback(provider, params):
        return {"ok": False, "error": "invalid_signature"}
    if status in {"2", "reversed", "reverse", "chargeback", "charged_back", "reject", "rejected"}:
        existing = provider_events.find_one({"provider": provider, "event_id": event_id})
        if not existing:
            return {"ok": True, "message": "reversal_ignored_unknown_event"}
        if existing.get("status") in {"2", "reversed", "reverse", "chargeback", "charged_back", "reject", "rejected"} or existing.get("reversed_at"):
            return {"ok": True, "message": "duplicate_reversal_ignored"}
        points = int(existing.get("points") or 0)
        removed = remove_balance(user_id, points) if points > 0 else 0
        debt = max(0, points - int(removed or 0))
        if debt:
            db["users"].update_one({"user_id": int(user_id)}, {"$inc": {"provider_debt": debt}})
            try:
                record_transaction(user_id, "cpagrip_reversal_debt", debt, event_id, metadata={"provider": "cpagrip"})
            except Exception:
                logger.exception("CPAGrip reversal debt transaction failed | event=%s", event_id)
        provider_events.update_one({"_id": existing["_id"]}, {"$set": {"status": status, "reversed_at": int(time.time()), "reversal_removed": int(removed or 0), "reversal_debt": debt}})
        return {"ok": True, "message": "reversal_recorded", "removed": int(removed or 0), "debt": debt}
    points = _reward_points(reward_raw)
    if points <= 0:
        return {"ok": False, "error": "invalid_reward"}

    offer_id = str(
        params.get("offer_id") or params.get("offerid") or params.get("offerId") or
        params.get("campaign_id") or params.get("campaignId") or ""
    ).strip()
    offer_doc = None
    if offer_id:
        offer_doc = provider_offers.find_one(
            {"provider": "cpagrip", "offer_id": offer_id},
            {"_id": 0, "title": 1, "custom_title": 1, "provider_reward": 1, "offer_id": 1},
        )
    offer_title = str((offer_doc or {}).get("custom_title") or (offer_doc or {}).get("title") or
                      params.get("offer_name") or params.get("offerName") or "Unknown offer")
    event_doc = {
        "provider": provider, "event_id": event_id, "user_id": user_id,
        "offer_id": offer_id, "offer_title": offer_title,
        "provider_reward": float((offer_doc or {}).get("provider_reward") or reward_raw or 0),
        "reward_raw": str(reward_raw), "points": points, "status": status,
        "received_at": int(time.time()),
        "params": {str(k): str(v) for k, v in params.items()},
    }
    try:
        provider_events.insert_one(event_doc)
    except Exception as exc:
        if "duplicate" in str(exc).lower() or "e11000" in str(exc).lower():
            return {"ok": True, "message": "duplicate_ignored"}
        logger.exception("Provider event insert failed")
        return {"ok": False, "error": "event_store_failed"}
    if not add_balance(user_id, points):
        provider_events.delete_one({"provider": provider, "event_id": event_id})
        return {"ok": False, "error": "credit_failed"}
    try:
        record_transaction(user_id, "cpagrip_conversion", points, event_id)
    except Exception:
        logger.exception("Transaction record failed | event=%s", event_id)
    try:
        add_activity(user_id, "💸 CPAGrip conversion", points)
    except Exception:
        logger.exception("Activity log failed | user=%s", user_id)
    _mark_provider_pending_rewarded(provider, user_id, event_id, points, offer_id)
    _notify_user_verified(user_id, provider, points, offer_title)
    return {"ok": True, "message": "credited", "provider": provider, "event_id": event_id, "user_id": user_id, "points": points}




def get_cached_provider_offers(user_id: int):
    return _cache_get_stale(("cpagrip_offers", int(user_id)))


def get_cached_offerwallme_tasks(user_id: int):
    return _cache_get_stale(("offerwallme_tasks", int(user_id)))


def get_cached_offerwallme_shortlinks(user_id: int):
    return _cache_get_stale(("offerwallme_shortlinks", int(user_id)))


def provider_cache_fresh(kind: str, user_id: int) -> bool:
    return _cache_fresh((str(kind), int(user_id)))


def refresh_provider_offers(user_id: int):
    _cache_clear("cpagrip_offers", user_id)
    _cache_clear("provider_offers", user_id)
    return get_provider_offers(user_id, force_refresh=True)


def refresh_offerwallme_tasks(user_id: int):
    _cache_clear("offerwallme_tasks", user_id)
    return get_offerwallme_tasks(user_id, force_refresh=True)


def refresh_offerwallme_shortlinks(user_id: int):
    _cache_clear("offerwallme_shortlinks", user_id)
    return get_offerwallme_shortlinks(user_id, force_refresh=True)


def provider_status():
    return {
        "cpagrip": _enabled("cpagrip") and bool(_env("CPAGRIP_OFFERS_API_URL")),
        "cpagrip_postback": bool(_env("CPAGRIP_POSTBACK_PASSWORD") or _env("CPAGRIP_POSTBACK_SECRET")),
        "offerwallme": _enabled("offerwallme"),
        "cpalead": _enabled("cpalead") and bool(_env("CPALEAD_PUBLISHER_ID")),
        "cpalead_postback": bool(_env("CPALEAD_POSTBACK_PASSWORD")),
        "offerwallme_postback": bool(_env("OFFERWALLME_POSTBACK_SECRET")),
        "offerwallme_points_per_usd": _env("OFFERWALLME_POINTS_PER_USD", "1000"),
        "offerwallme_reward_unit": _env("OFFERWALLME_REWARD_UNIT", "points"),
        "offerwallme_currency_per_usd": _env("OFFERWALLME_CURRENCY_PER_USD", "200"),
        "offerwallme_user_reward_percent": _env("OFFERWALLME_USER_REWARD_PERCENT", "40"),
        "reward_points_per_usd": _env("REWARD_POINTS_PER_USD", "1000"),
    }
