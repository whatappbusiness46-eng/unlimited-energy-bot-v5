# ============================================================
# bot.py
# Unlimited Energy Bot V5
# FINAL APPLICATION ENTRY POINT
# Render Worker + Flask Health Server
# ============================================================

import logging
import os
import threading
import json
from urllib.request import Request as UrlRequest, urlopen as urlopen_request

from flask import Flask, request, jsonify, Response

from telegram import Update

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import BOT_TOKEN
from provider_integrations import process_postback, provider_status, get_offerwall_task_proof

from handlers import (
    start,
    profile,
    balance,
    rank,
    stats,
    leaderboard_command,
    activity,
    dailystatus,
    help_command,
    myid,
)

from callbacks import (
    button_callback,
)

from admin import (
    admin_panel,
    admin_text_handler,
)

from payments import payment_text_handler
from tasks import offerwallme_proof_message_handler

from withdraw import (
    withdraw_text_handler,
)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format=(
        "%(asctime)s | "
        "%(name)s | "
        "%(levelname)s | "
        "%(message)s"
    ),
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ============================================================
# RENDER KEEP-ALIVE
# ============================================================
# Render Free services may spin down after inactivity. Ping the public
# health endpoint before the 15-minute idle window.
# Set KEEPALIVE_URL in Render ENV to your public Render URL if needed.
KEEPALIVE_URL = (
    os.getenv("KEEPALIVE_URL", "https://unlimited-energy-bot-v5.onrender.com").strip().rstrip("/")
    or os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    or os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
)
KEEPALIVE_INTERVAL_SECONDS = 14 * 60


def keepalive_loop():
    if not KEEPALIVE_URL:
        logger.warning("Keep-alive disabled: no public URL configured.")
        return

    health_url = KEEPALIVE_URL + "/health"
    logger.info(
        "Render keep-alive enabled: %s (every %s seconds)",
        health_url,
        KEEPALIVE_INTERVAL_SECONDS,
    )

    threading.Event().wait(30)

    while True:
        try:
            from urllib.request import Request, urlopen

            request = Request(
                health_url,
                headers={
                    "User-Agent": "UnlimitedEnergyBot-KeepAlive/1.0"
                },
            )

            with urlopen(request, timeout=15) as response:
                logger.info("Keep-alive ping: HTTP %s", response.status)

        except Exception as exc:
            logger.warning("Keep-alive ping failed: %s", exc)

        threading.Event().wait(KEEPALIVE_INTERVAL_SECONDS)


# ============================================================
# ENVIRONMENT VALIDATION
# ============================================================

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN environment variable is not set."
    )


# ============================================================
# FLASK HEALTH SERVER
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return """<!doctype html>
<html lang="en">
<head>
    <meta name="offerwall-verification" content="6aa07179373d65cfef066691">
    <meta charset="utf-8">
    <title>Unlimited Energy Bot</title>
</head>
<body>
    Unlimited Energy Bot is running.
</body>
</html>"""


@app.route("/health")
def health():
    return {
        "status": "ok",
        "bot": "Unlimited Energy Bot",
    }


@app.route("/health/providers")
def provider_health():
    return jsonify(provider_status())


@app.route("/proof/<proof_id>", methods=["GET"])
def offerwall_task_proof_proxy(proof_id):
    """Securely proxy Telegram photo proofs without exposing BOT_TOKEN to providers/users."""
    doc = get_offerwall_task_proof(proof_id)
    if not doc:
        return jsonify({"error": "proof_not_found"}), 404
    token = os.getenv("BOT_TOKEN", "").strip()
    file_id = str(doc.get("telegram_file_id") or "").strip()
    if not token or not file_id:
        return jsonify({"error": "proof_unavailable"}), 404
    try:
        meta_req = UrlRequest(
            f"https://api.telegram.org/bot{token}/getFile?file_id={__import__('urllib.parse').parse.quote(file_id)}",
            headers={"User-Agent": "UnlimitedEnergyBot/Final"},
        )
        with urlopen_request(meta_req, timeout=10) as meta_resp:
            meta = json.loads(meta_resp.read().decode("utf-8", errors="replace"))
        file_path = str(((meta or {}).get("result") or {}).get("file_path") or "").strip()
        if not file_path:
            return jsonify({"error": "telegram_file_unavailable"}), 404
        file_req = UrlRequest(
            f"https://api.telegram.org/file/bot{token}/{file_path}",
            headers={"User-Agent": "UnlimitedEnergyBot/Final"},
        )
        with urlopen_request(file_req, timeout=15) as file_resp:
            data = file_resp.read(10 * 1024 * 1024 + 1)
            content_type = str(file_resp.headers.get("Content-Type") or "image/jpeg")
        if len(data) > 10 * 1024 * 1024:
            return jsonify({"error": "proof_too_large"}), 413
        return Response(data, mimetype=content_type.split(";", 1)[0], headers={"Cache-Control": "no-store, max-age=0"})
    except Exception:
        logger.exception("Offerwall proof proxy failed | proof=%s", proof_id)
        return jsonify({"error": "proof_unavailable"}), 502


@app.route("/cpagrip/postback", methods=["GET", "POST"])
def cpagrip_postback():
    """CPAGrip Global Postback endpoint (documented account URL)."""
    return provider_postback("cpagrip")


@app.route("/postback/<provider>", methods=["GET", "POST"])
def provider_postback(provider):
    """Secure S2S conversion endpoint.

    The provider must send a documented user identifier, event/transaction
    identifier, reward/payout and a valid shared-secret or HMAC signature.
    The endpoint is idempotent and will not credit duplicate event IDs.
    """
    payload = {}
    if request.is_json:
        body = request.get_json(silent=True) or {}
        if isinstance(body, dict):
            payload.update(body)
    payload.update(request.args.to_dict(flat=True))
    payload.update(request.form.to_dict(flat=True))

    result = process_postback(provider, payload)
    # Provider postbacks should receive HTTP 200 even when the conversion is
    # rejected; the JSON body still reports the exact reason. This prevents
    # unnecessary provider retries for invalid/duplicate callbacks.
    return jsonify(result), 200


def run_web_server():

    port = int(
        os.getenv(
            "PORT",
            "10000",
        )
    )

    logger.info(
        "Starting Flask health server on port %s",
        port,
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
    )


# ============================================================
# TELEGRAM APPLICATION
# ============================================================

telegram_app = (
    Application.builder()
    .token(BOT_TOKEN)
    .build()
)


# ============================================================
# COMMAND HANDLERS
# ============================================================

telegram_app.add_handler(
    CommandHandler(
        "start",
        start,
    )
)

telegram_app.add_handler(
    CommandHandler(
        "profile",
        profile,
    )
)

telegram_app.add_handler(
    CommandHandler(
        "balance",
        balance,
    )
)

telegram_app.add_handler(
    CommandHandler(
        "rank",
        rank,
    )
)

telegram_app.add_handler(
    CommandHandler(
        "stats",
        stats,
    )
)

telegram_app.add_handler(
    CommandHandler(
        "leaderboard",
        leaderboard_command,
    )
)

telegram_app.add_handler(
    CommandHandler(
        "activity",
        activity,
    )
)

telegram_app.add_handler(
    CommandHandler(
        "dailystatus",
        dailystatus,
    )
)

telegram_app.add_handler(
    CommandHandler(
        "help",
        help_command,
    )
)

telegram_app.add_handler(
    CommandHandler(
        "myid",
        myid,
    )
)


# ============================================================
# ADMIN COMMAND
# ============================================================

telegram_app.add_handler(
    CommandHandler(
        "admin",
        admin_panel,
    )
)


# ============================================================
# TEXT MESSAGE ROUTER
# ============================================================

async def text_message_router(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    # --------------------------------------------------------
    # OFFERWALL.ME TASK PROOF FLOW
    # --------------------------------------------------------
    if await offerwallme_proof_message_handler(update, context):
        return

    # --------------------------------------------------------
    # MEMBERSHIP PAYMENT REFERENCE FLOW
    # --------------------------------------------------------
    if await payment_text_handler(update, context):
        return

    # --------------------------------------------------------
    # WITHDRAWAL FLOW FIRST
    # --------------------------------------------------------

    handled = await withdraw_text_handler(
        update,
        context,
    )

    if handled:
        return

    # --------------------------------------------------------
    # ADMIN TEXT FLOW
    # --------------------------------------------------------

    await admin_text_handler(
        update,
        context,
    )


# ============================================================
# TEXT HANDLER
# ============================================================

telegram_app.add_handler(
    CallbackQueryHandler(
        button_callback
    )
)

telegram_app.add_handler(
    MessageHandler(
        (filters.TEXT | filters.PHOTO) & ~filters.COMMAND,
        text_message_router,
    )
)

# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):

    error = context.error

    logger.error(
        "Telegram application error: %s",
        error,
        exc_info=error,
    )


telegram_app.add_error_handler(
    error_handler
)


# ============================================================
# START TELEGRAM BOT
# ============================================================

def run_bot():

    logger.info(
        "Starting Unlimited Energy Bot..."
    )

    telegram_app.run_polling(
        drop_pending_updates=True,
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    logger.info(
        "Launching Unlimited Energy Bot..."
    )

    # --------------------------------------------------------
    # Start Flask health server
    # --------------------------------------------------------

    web_thread = threading.Thread(
        target=run_web_server,
        name="flask-health-server",
        daemon=True,
    )

    web_thread.start()

    keepalive_thread = threading.Thread(
        target=keepalive_loop,
        name="render-keepalive",
        daemon=True,
    )
    keepalive_thread.start()

    logger.info(
        "Flask health server started."
    )
    # --------------------------------------------------------
    # Start Telegram polling
    # --------------------------------------------------------

    run_bot()
    
