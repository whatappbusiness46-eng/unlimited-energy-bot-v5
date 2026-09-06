# ============================================================
# bot.py
# Unlimited Energy Bot V2
# FINAL APPLICATION ENTRY POINT
# Render Worker + Flask Health Server
# ============================================================

import logging
import os
import threading

from flask import Flask, request, jsonify

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
from provider_integrations import process_postback, provider_status

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
    return "Unlimited Energy Bot is running."


@app.route("/health")
def health():
    return {
        "status": "ok",
        "bot": "Unlimited Energy Bot",
    }


@app.route("/health/providers")
def provider_health():
    return jsonify(provider_status())


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
    status_code = 200 if result.get("ok") else 400
    # Plain text is friendlier for most CPA networks.
    return jsonify(result), status_code


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
        filters.TEXT & ~filters.COMMAND,
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

    logger.info(
        "Flask health server started."
    )
    # --------------------------------------------------------
    # Start Telegram polling
    # --------------------------------------------------------

    run_bot()
    
