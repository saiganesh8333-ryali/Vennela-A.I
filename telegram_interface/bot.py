"""Telegram bot entry point and handlers."""

from __future__ import annotations

import logging
from time import perf_counter
from uuid import uuid4

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from .adapter import VennelaAdapter, VennelaAdapterError
from .config import TelegramConfig, load_config

logger = logging.getLogger(__name__)


def _suppress_sensitive_http_logs() -> None:
    """Prevent HTTP client logs from printing Bot API URLs containing the token."""
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def _log_event(operation: str, request_id: str, **fields: object) -> None:
    details = " ".join(f"{key}={value}" for key, value in fields.items())
    logger.info("[TELEGRAM] %s request_id=%s %s", operation, request_id, details)


def _log_error(stage: str, request_id: str, error: BaseException) -> None:
    logger.error(
        "[TELEGRAM] error stage=%s request_id=%s error_class=%s",
        stage,
        request_id,
        type(error).__name__,
    )


def _authorized(update: Update, config: TelegramConfig) -> bool:
    chat = update.effective_chat
    return chat is not None and chat.id in config.allowed_chat_ids


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    request_id = uuid4().hex
    _log_event("update_received", request_id, command="start")
    config: TelegramConfig = context.application.bot_data["config"]
    if _authorized(update, config) and update.message:
        _log_event("message_accepted", request_id)
        await _reply(update, "Vennela Telegram interface is ready.", request_id)
    else:
        _log_event("message_accepted", request_id, accepted=False)


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    request_id = uuid4().hex
    _log_event("update_received", request_id, command="ping")
    config: TelegramConfig = context.application.bot_data["config"]
    if _authorized(update, config) and update.message:
        _log_event("message_accepted", request_id)
        await _reply(update, "pong", request_id)
    else:
        _log_event("message_accepted", request_id, accepted=False)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    request_id = uuid4().hex
    _log_event("update_received", request_id, command="help")
    config: TelegramConfig = context.application.bot_data["config"]
    if _authorized(update, config) and update.message:
        _log_event("message_accepted", request_id)
        await _reply(
            update,
            "Send a message to chat with Vennela. Commands: /start, /ping, /help.",
            request_id,
        )
    else:
        _log_event("message_accepted", request_id, accepted=False)


async def _reply(update: Update, text: str, request_id: str) -> None:
    if update.message is None:
        return
    started = perf_counter()
    try:
        await update.message.reply_text(text)
    except Exception as exc:
        _log_error("telegram_reply", request_id, exc)
        raise
    _log_event(
        "telegram_reply_sent",
        request_id,
        duration_ms=round((perf_counter() - started) * 1000, 3),
    )


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    request_id = uuid4().hex
    _log_event("update_received", request_id)
    config: TelegramConfig = context.application.bot_data["config"]
    if not _authorized(update, config) or not update.message or not update.effective_chat:
        _log_event("message_accepted", request_id, accepted=False)
        return
    _log_event("message_accepted", request_id, accepted=True)
    adapter: VennelaAdapter = context.application.bot_data["adapter"]
    try:
        reply = await adapter.respond(
            update.message.text or "",
            update.effective_chat.id,
            request_id=request_id,
        )
    except VennelaAdapterError as exc:
        _log_error("vennela_request", request_id, exc)
        reply = "Vennela is temporarily unavailable. Please try again later."
    await _reply(update, reply, request_id)


async def application_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    error = context.error or RuntimeError("Unknown Telegram application error")
    _log_error("telegram_update", uuid4().hex, error)


def build_application(
    config: TelegramConfig | None = None,
    adapter: VennelaAdapter | None = None,
) -> Application:
    config = config or load_config()
    application = Application.builder().token(config.bot_token).build()
    application.bot_data["config"] = config
    application.bot_data["adapter"] = adapter or VennelaAdapter(config)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))
    application.add_error_handler(application_error)
    return application


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    _suppress_sensitive_http_logs()
    application = build_application()
    logger.info("Starting Telegram polling")
    application.run_polling()
    logger.warning("Telegram polling stopped")


if __name__ == "__main__":
    main()
