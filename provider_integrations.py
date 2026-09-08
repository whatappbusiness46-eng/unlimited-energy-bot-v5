# provider_integrations.py
# CPAGrip + Offerwall.me live earning + verified postback integration.

import hashlib
import hmac
import json
import xml.etree.ElementTree as ET
import logging
import os
import time
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from database import db, add_balance, add_activity, get_user, record_transaction, remove_balance, get_membership_multiplier

logger = logging.getLogger(__name__)

provider_offers = db["provider_offers"]
provider_events = db["provider_events"]
provider_disabled_offers = db["provider_disabled_offers"]

try:
    provider_offers.create_index([("provider", 1), ("offer_id", 1)],
                                 unique=True, name="provider_offer_unique")
    provider_events.create_index([("provider", 1), ("event_id", 1)],
                                 unique=True, name="provider_event_unique")
    provider_disabled_offers.create_index([("provider", 1), ("offer_id", 1)],
                                          unique=True, name="provider_disabled_offer_unique")
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
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, list):
        return data
    for key in ("offers", "tasks", "shortlinks", "results", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def get_offerwallme_offers(user_id: int):
    if not _enabled("offerwallme"):
        return []
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
    return result


def sync_offerwallme_offers(user_id: int) -> int:
    offers = get_offerwallme_offers(user_id)
    for offer in offers:
        provider_offers.update_one(
            {"provider": "offerwallme", "offer_id": offer["offer_id"]},
            {"$set": offer},
            upsert=True,
        )
    return len(offers)


def get_offerwallme_tasks(user_id: int):
    if not _enabled("offerwallme"):
        return []
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
        result.append(dict(raw, id=str(task_id)))
    return result


def submit_offerwallme_task_proof(user_id: int, task_id: str, proof: str):
    if not _enabled("offerwallme"):
        return {"ok": False, "error": "provider_disabled"}
    payload = _offerwallme_request(
        _env("OFFERWALLME_TASK_SUBMIT_API_URL", "https://offerwall.me/tasksubmit.php"),
        user_id,
        method="POST",
        body={"task_id": str(task_id), "proof": str(proof or "")},
    )
    if isinstance(payload, dict):
        status = payload.get("status")
        ok = bool(payload.get("ok")) or status in {200, "200", "success", "approved", "pending"}
        return {"ok": ok, "raw": payload, **({k: payload[k] for k in ("message", "status") if k in payload})}
    return {"ok": False, "raw": payload}


def get_offerwallme_shortlinks(user_id: int):
    if not _enabled("offerwallme"):
        return []
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
    return result

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
        payout = float(_first(raw, ("reward", "payout", "amount", "points"), 0))
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
            provider_offers.update_one(
                {"provider": "cpagrip", "offer_id": offer["offer_id"]},
                {"$set": offer},
                upsert=True,
            )
            count += 1
        if count == 0:
            logger.warning("CPAGrip feed returned no parseable offers | user=%s | url=%s", user_id, url.split("?")[0])
        return count
    except Exception:
        logger.exception("CPAGrip offer sync failed | user=%s", user_id)
        return 0


def get_provider_offers(user_id: int, providers: Optional[Iterable[str]] = None):
    providers = [p.lower() for p in (providers or ("cpagrip", "offerwallme"))]
    providers = [p for p in providers if p in {"cpagrip", "offerwallme"} and _enabled(p)]
    if "cpagrip" in providers:
        sync_cpagrip_offers(user_id)
    if "offerwallme" in providers:
        sync_offerwallme_offers(user_id)
    if not providers:
        return []
    disabled = {
        (str(x.get("provider")), str(x.get("offer_id")))
        for x in provider_disabled_offers.find(
            {"provider": {"$in": providers}}, {"provider": 1, "offer_id": 1}
        )
    }
    docs = provider_offers.find(
        {"provider": {"$in": providers}}, {"_id": 0}
    ).sort("updated_at", -1).limit(100)
    return [
        dict(x) for x in docs
        if (str(x.get("provider")), str(x.get("offer_id"))) not in disabled
    ]


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
    """Return the member reward for a verified provider conversion.

    Provider payout is never exposed as the member reward. Keep the member
    reward independently configurable, defaulting to 200 points.
    """
    try:
        points = int(_env("CPAGRIP_DEFAULT_USER_REWARD_POINTS", "200"))
    except (TypeError, ValueError):
        points = 200
    return max(1, points)


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
    """Convert Offerwall.me payout to the configured member reward.

    Offerwall.me's Amount is treated as USD payout. The member receives only
    OFFERWALLME_USER_REWARD_PERCENT of that amount, converted by
    OFFERWALLME_POINTS_PER_USD. Provider payout is never shown as member pay.
    """
    try:
        reward = Decimal(str(reward_raw))
        share = Decimal(_env("OFFERWALLME_USER_REWARD_PERCENT", "40"))
        rate = Decimal(_env("OFFERWALLME_POINTS_PER_USD", "1000"))
        if reward <= 0 or share <= 0 or rate <= 0:
            return 0
        points = int((reward * share / Decimal("100") * rate).quantize(Decimal("1")))
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
        if points > 0 and remove_balance(user_id, points):
            provider_events.update_one(
                {"_id": existing["_id"]},
                {"$set": {"status": "2", "reversed_at": int(time.time())}},
            )
            return {"ok": True, "message": "reversal_recorded"}
        return {"ok": False, "error": "reversal_credit_not_available"}

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
        record_transaction(user_id, points, "offerwallme_conversion", event_id)
    except Exception:
        logger.exception("Offerwall.me transaction record failed | event=%s", event_id)
    try:
        add_activity(user_id, "💸 Offerwall.me conversion", points)
    except Exception:
        logger.exception("Offerwall.me activity log failed | user=%s", user_id)

    return {"ok": True, "message": "credited", "provider": "offerwallme", "event_id": event_id, "user_id": user_id, "points": points}

def process_postback(provider: str, params: Dict[str, Any]):
    provider = str(provider).lower().strip()
    if provider == "offerwallme":
        return _process_offerwallme_postback(params)
    if provider != "cpagrip" or not _enabled("cpagrip"):
        return {"ok": False, "error": "provider_disabled"}

    event_id = str(
        params.get("event_id") or params.get("transaction_id") or
        params.get("txn") or params.get("conversion_id") or ""
    ).strip()
    user_raw = params.get("tracking_id") or params.get("user_id") or params.get("uid") or params.get("subid") or params.get("sub_id")
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
    if status in {"reversed", "chargeback", "reject", "rejected"}:
        existing = provider_events.find_one({"provider": provider, "event_id": event_id})
        if not existing:
            return {"ok": True, "message": "reversal_ignored_unknown_event"}
        provider_events.update_one({"_id": existing["_id"]}, {"$set": {"status": status, "reversed_at": int(time.time())}})
        return {"ok": True, "message": "reversal_recorded"}
    points = _reward_points(reward_raw)
    if points <= 0:
        return {"ok": False, "error": "invalid_reward"}
    event_doc = {"provider": provider, "event_id": event_id, "user_id": user_id, "reward_raw": str(reward_raw), "points": points, "status": status, "received_at": int(time.time()), "params": {str(k): str(v) for k, v in params.items()}}
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
        record_transaction(user_id, points, "cpagrip_conversion", event_id)
    except Exception:
        logger.exception("Transaction record failed | event=%s", event_id)
    try:
        add_activity(user_id, "💸 CPAGrip conversion", points)
    except Exception:
        logger.exception("Activity log failed | user=%s", user_id)
    return {"ok": True, "message": "credited", "provider": provider, "event_id": event_id, "user_id": user_id, "points": points}



def shorten_with_provider(provider: str, long_url: str, alias: str = "", ad_type: int = 1) -> dict:
    """Create a short URL using the documented ShrtFly or ShrinkMe API.

    This only creates/returns the short URL. Neither provider's documented
    API supplies a completion callback, so this function never credits a user.
    """
    provider = str(provider or "").strip().lower()
    long_url = str(long_url or "").strip()
    alias = str(alias or "").strip()
    if not long_url:
        return {"ok": False, "error": "missing_url"}

    if provider == "shrtfly":
        token = _env("SHRTFLY_API_TOKEN")
        endpoint = _env("SHRTFLY_API_URL", "https://shrtfly.com/api")
        if not token:
            return {"ok": False, "error": "missing_shrtfly_token"}
        params = {"api": token, "type": int(ad_type or 1), "url": long_url, "format": "json"}
        if alias:
            params["alias"] = alias
        try:
            payload = _json_request(endpoint, params=params)
            if isinstance(payload, dict) and payload.get("status") == "success":
                result = payload.get("result") or {}
                short = result.get("shorten_url")
                if short:
                    return {"ok": True, "provider": provider, "short_url": short, "raw": payload}
            return {"ok": False, "provider": provider, "error": str((payload or {}).get("result", "API error")) if isinstance(payload, dict) else "API error", "raw": payload}
        except Exception as exc:
            logger.exception("ShrtFly API failed")
            return {"ok": False, "provider": provider, "error": str(exc)}

    if provider == "shrinkme":
        token = _env("SHRINKME_API_KEY")
        endpoint = _env("SHRINKME_API_URL", "https://shrinkme.io/api")
        if not token:
            return {"ok": False, "error": "missing_shrinkme_token"}
        params = {"api": token, "url": long_url, "format": "json"}
        if alias:
            params["alias"] = alias
        try:
            payload = _json_request(endpoint, params=params)
            if isinstance(payload, dict) and payload.get("status") == "success":
                short = payload.get("shortenedUrl")
                if short:
                    return {"ok": True, "provider": provider, "short_url": short, "raw": payload}
            message = payload.get("message", "API error") if isinstance(payload, dict) else "API error"
            return {"ok": False, "provider": provider, "error": str(message), "raw": payload}
        except Exception as exc:
            logger.exception("ShrinkMe API failed")
            return {"ok": False, "provider": provider, "error": str(exc)}

    return {"ok": False, "error": "unsupported_provider"}

def provider_status():
    return {
        "cpagrip": _enabled("cpagrip") and bool(_env("CPAGRIP_OFFERS_API_URL")),
        "cpagrip_postback": bool(_env("CPAGRIP_POSTBACK_PASSWORD") or _env("CPAGRIP_POSTBACK_SECRET")),
        "offerwallme": _enabled("offerwallme"),
        "offerwallme_postback": bool(_env("OFFERWALLME_POSTBACK_SECRET")),
        "offerwallme_points_per_usd": _env("OFFERWALLME_POINTS_PER_USD", "1000"),
        "offerwallme_user_reward_percent": _env("OFFERWALLME_USER_REWARD_PERCENT", "40"),
        "reward_points_per_usd": _env("REWARD_POINTS_PER_USD", "1000"),
    }
