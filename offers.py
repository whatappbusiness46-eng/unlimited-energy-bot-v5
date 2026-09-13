# ============================================================
# OFFERS SYSTEM
# Live provider-backed offers. No client-side "Claim Reward".
# Rewards are credited only after a verified provider postback.
# ============================================================

import asyncio
import logging
import os
import time
from config import CPAGRIP_DEFAULT_USER_REWARD_POINTS, CPAGRIP_OFFER_LIMIT
from html import escape as html_escape
from typing import Any, Dict, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import get_user
from provider_integrations import (
    get_provider_offers, get_cached_provider_offers, provider_cache_fresh,
    refresh_provider_offers, _reward_points, _record_provider_pending,
)

logger = logging.getLogger(__name__)
_BACKGROUND_REFRESHING = set()

# Legacy/manual offers remain available for migration, but they are
# display-only unless a real provider postback is configured.
OFFERS: Dict[str, Dict[str, Any]] = {}


def _get_user(user_id):
    try:
        return get_user(user_id, create=False)
    except TypeError:
        return get_user(user_id)


def _blocked(user):
    return bool(
        not user or user.get("banned", False) or user.get("blacklisted", False)
    )


def register_offer(
    offer_id: str,
    title: str,
    description: str = "",
    reward: int = 0,
    url: Optional[str] = None,
    enabled: bool = True,
    cooldown: int = 86400,
):
    offer_id = str(offer_id).strip()
    if not offer_id:
        return False
    OFFERS[offer_id] = {
        "id": offer_id,
        "title": str(title or offer_id),
        "description": str(description or ""),
        "reward": int(reward or 0),
        "url": url,
        "enabled": bool(enabled),
        "cooldown": max(0, int(cooldown or 0)),
    }
    return True


def get_offer(offer_id):
    offer = OFFERS.get(str(offer_id))
    return dict(offer) if offer else None


def get_offers(include_disabled=False):
    return [
        dict(x) for x in OFFERS.values()
        if include_disabled or x.get("enabled", True)
    ]


def _provider_offer_key(provider: str, offer_id: str) -> str:
    # Keep callback data compact.
    return f"{provider}:{offer_id}"


def _parse_provider_offer_key(value: str):
    if ":" not in value:
        return None, None
    provider, offer_id = value.split(":", 1)
    return provider, offer_id


def _live_offers(user_id: int) -> list:
    try:
        return get_provider_offers(user_id)
    except Exception:
        logger.exception("Live offer sync failed | user=%s", user_id)
        return []


def _cached_live_offers(user_id: int) -> list:
    try:
        return list(get_cached_provider_offers(user_id) or [])
    except Exception:
        return []


async def _refresh_offers_in_background(query, user_id: int):
    key = int(user_id)
    if key in _BACKGROUND_REFRESHING:
        return
    _BACKGROUND_REFRESHING.add(key)
    try:
        await asyncio.to_thread(refresh_provider_offers, user_id)
        if query.message:
            live = _cached_live_offers(user_id) or []
            if live:
                lines = [
                    "🎁 **LIVE OFFERS**", "",
                    "Complete an offer normally. Your reward is credited only after the provider confirms the conversion.", "",
                ]
                for item in live[:CPAGRIP_OFFER_LIMIT]:
                    reward = _member_reward(item)
                    lines.append(f"• {html_escape(str(item.get('custom_title') or item.get('title', 'Special Offer')))} — Earn +{reward} Points")
                try:
                    await query.edit_message_text("\n".join(lines), reply_markup=offers_menu(user_id), parse_mode="HTML")
                except Exception:
                    pass
            else:
                try:
                    await query.edit_message_text("🎁 **OFFERS**\n\nNo live offers are available right now.", reply_markup=offers_menu(user_id), parse_mode="HTML")
                except Exception:
                    pass
    except Exception:
        logger.exception("Background offer refresh failed | user=%s", user_id)
    finally:
        _BACKGROUND_REFRESHING.discard(key)


def _member_reward(item):
    if item.get("custom_reward_locked"):
        try:
            return max(0, int(item.get("custom_reward_points", 0)))
        except (TypeError, ValueError):
            pass
    return max(0, int(_reward_points(item.get("provider_reward", 0))))


def offers_menu(user_id: int):
    keyboard = []
    live = _cached_live_offers(user_id)
    for item in live[:CPAGRIP_OFFER_LIMIT]:
        provider = str(item.get("provider", "provider"))
        offer_id = str(item.get("offer_id", ""))
        title = str(item.get("custom_title") or item.get("title") or "Special Offer")
        reward = _member_reward(item)
        label = f"🎁 {title[:28]} • +{reward} pts"
        callback = f"provider_offer_{_provider_offer_key(provider, offer_id)}"
        if len(callback) <= 64:
            keyboard.append([
                InlineKeyboardButton(label, callback_data=callback)
            ])

    if not keyboard:
        keyboard.append([
            InlineKeyboardButton("🔄 Refresh Offers", callback_data="offers")
        ])

    keyboard.append([
        InlineKeyboardButton("🏠 Home", callback_data="home")
    ])
    return InlineKeyboardMarkup(keyboard)


async def offers_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return

    db_user = _get_user(user.id)
    if _blocked(db_user):
        await message.reply_text("🚫 Your account is restricted.")
        return

    live = _cached_live_offers(user.id)
    if not provider_cache_fresh("cpagrip_offers", user.id):
        try:
            if update.callback_query:
                context.application.create_task(_refresh_offers_in_background(update.callback_query, user.id))
            else:
                # Message-based opens still get an immediate page; the next callback refreshes the list.
                context.application.create_task(asyncio.to_thread(refresh_provider_offers, user.id))
        except Exception:
            pass

    if not live:
        text = (
            "🎁 **OFFERS**\n\n"
            + ("⏳ Loading latest offers...\n\nPlease wait a moment; the offer list is being refreshed." if not provider_cache_fresh("cpagrip_offers", user.id) else "No live offers are available right now.\n\nAdmin must configure the provider API and postback.")
        )
    else:
        lines = [
            "🎁 **LIVE OFFERS**",
            "",
            "Complete an offer normally. Your reward is credited "
            "only after the provider confirms the conversion.",
            "",
        ]
        for item in live[:CPAGRIP_OFFER_LIMIT]:
            lines.append(
                f"• {html_escape(str(item.get('custom_title') or item.get('title', 'Special Offer')))} — "
                f"Earn +{int(item.get('custom_reward_points') or _reward_points(item.get('provider_reward', 0)))} Points"
            )
        text = "\n".join(lines)

    markup = offers_menu(user.id)
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
        except Exception:
            await message.reply_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await message.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def provider_offer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    data = str(query.data or "")
    prefix = "provider_offer_"
    if not data.startswith(prefix):
        return

    await query.answer()
    provider, offer_id = _parse_provider_offer_key(data[len(prefix):])
    if not provider or not offer_id:
        await query.edit_message_text("⚠️ Invalid offer.")
        return

    items = _cached_live_offers(query.from_user.id)
    offer = next(
        (
            x for x in items
            if str(x.get("provider")) == provider
            and str(x.get("offer_id")) == offer_id
        ),
        None,
    )

    if not offer:
        await query.edit_message_text(
            "⚠️ This offer is no longer available.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Offers", callback_data="offers")],
                [InlineKeyboardButton("🏠 Home", callback_data="home")],
            ]),
        )
        return

    url = str(offer.get("url") or "")
    if not url:
        await query.edit_message_text("⚠️ Offer link unavailable.")
        return

    title = html_escape(str(offer.get("custom_title") or offer.get("title") or "Offer"))
    description = html_escape(str(offer.get("description") or "")).strip()
    reward_points = _member_reward(offer) or 200
    if reward_points <= 0:
        reward_points = 200
    _record_provider_pending(
        provider, query.from_user.id, offer_id,
        str(offer.get("custom_title") or offer.get("title") or "Offer"),
        reward_points, offer.get("provider_reward", 0)
    )
    # Provider payout is intentionally hidden from members. Member-facing reward is fixed/configured.
    detail_lines = [
        "🎁 <b>OFFER DETAILS</b>",
        "",
        f"📌 {title}",
        f"💰 Your reward: +{reward_points} Points",
    ]
    if description:
        detail_lines += ["", description]
    detail_lines += [
        "",
        "Complete the offer according to its instructions. "
        "⏳ Status: Pending — waiting for provider verification. "
        "Your Points will be added automatically after a verified conversion callback.",
    ]
    await query.edit_message_text(
        "\n".join(detail_lines),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Start Offer", url=url)],
            [InlineKeyboardButton("⬅️ Offers", callback_data="offers")],
            [InlineKeyboardButton("🏠 Home", callback_data="home")],
        ]),
        parse_mode="HTML",
    )


# Legacy callbacks are retained but can never self-credit a user.
async def offer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer("This offer system now uses verified provider conversions.", show_alert=True)


async def offer_claim_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer(
            "❌ Manual claiming is disabled. Complete the offer and wait for provider verification.",
            show_alert=True,
        )


HANDLER_FUNCTIONS = {
    "offers": offers_page,
    "provider_offer_callback": provider_offer_callback,
    "offer_callback": offer_callback,
    "offer_claim_callback": offer_claim_callback,
}

__all__ = [
    "OFFERS",
    "register_offer",
    "get_offer",
    "get_offers",
    "offers_menu",
    "offers_page",
    "provider_offer_callback",
    "offer_callback",
    "offer_claim_callback",
    "HANDLER_FUNCTIONS",
]
