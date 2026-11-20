import logging
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from telegram import Bot, Message

import app as backend
from telegram_interface.bot import text_message
from telegram_interface.config import TelegramConfig


BOT_TOKEN = "123456:TEST_TOKEN_NOT_A_SECRET"
WEBHOOK_SECRET = backend._telegram_secret_token(BOT_TOKEN)


def telegram_update(chat_id=42):
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "date": 1_700_000_000,
            "chat": {"id": chat_id, "type": "private"},
            "from": {
                "id": chat_id,
                "is_bot": False,
                "first_name": "Test",
            },
            "text": "hello",
        },
    }


class FakeAdapter:
    def __init__(self):
        self.calls = []

    async def respond(self, message, chat_id, request_id=None):
        self.calls.append((message, chat_id, request_id))
        return "Vennela reply"


class FakeTelegramApplication:
    def __init__(self, config):
        self.bot = Bot(token=BOT_TOKEN)
        self.adapter = FakeAdapter()
        self.bot_data = {"config": config, "adapter": self.adapter}
        self.processed_updates = []

    async def process_update(self, update):
        self.processed_updates.append(update)
        await text_message(update, SimpleNamespace(application=self))


@pytest.fixture
def client():
    config = TelegramConfig(BOT_TOKEN, frozenset({42}))
    telegram_application = FakeTelegramApplication(config)
    backend._telegram_application = telegram_application
    backend._telegram_webhook_secret = WEBHOOK_SECRET
    try:
        yield TestClient(backend.app), telegram_application
    finally:
        backend._telegram_application = None
        backend._telegram_webhook_secret = None


def test_webhook_dispatches_authorized_update_without_exposing_secret(client, monkeypatch):
    seen_replies = []

    async def reply_text(message, text, *args, **kwargs):
        seen_replies.append(text)

    monkeypatch.setattr(Message, "reply_text", reply_text)
    test_client, telegram_application = client
    response = test_client.post(
        "/telegram/webhook",
        json=telegram_update(),
        headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert len(telegram_application.processed_updates) == 1
    assert telegram_application.adapter.calls[0][:2] == ("hello", 42)
    assert seen_replies == ["Vennela reply"]
    assert BOT_TOKEN not in response.text
    assert WEBHOOK_SECRET not in response.text


def test_webhook_ignores_unauthorized_update_without_calling_adapter(client, monkeypatch):
    seen_replies = []

    async def reply_text(message, text, *args, **kwargs):
        seen_replies.append(text)

    monkeypatch.setattr(Message, "reply_text", reply_text)
    test_client, telegram_application = client
    response = test_client.post(
        "/telegram/webhook",
        json=telegram_update(chat_id=99),
        headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
    )

    assert response.status_code == 200
    assert telegram_application.adapter.calls == []
    assert seen_replies == []


def test_webhook_rejects_invalid_secret_without_leaking_bot_token(client):
    test_client, _ = client
    response = test_client.post(
        "/telegram/webhook",
        json=telegram_update(),
        headers={"X-Telegram-Bot-Api-Secret-Token": BOT_TOKEN},
    )

    assert response.status_code == 401
    assert BOT_TOKEN not in response.text


@pytest.mark.asyncio
async def test_fastapi_startup_and_shutdown_manage_webhook_application(
    monkeypatch,
    caplog,
):
    from telegram import Update

    calls = []

    class FakeBot:
        async def set_webhook(self, **kwargs):
            calls.append(("set_webhook", kwargs))

    class FakeApplication:
        def __init__(self):
            self.bot = FakeBot()
            self.initialized = False
            self.running = False

        async def initialize(self):
            self.initialized = True
            calls.append(("initialize", None))

        async def start(self):
            self.running = True
            calls.append(("start", None))

        async def stop(self):
            self.running = False
            calls.append(("stop", None))

        async def shutdown(self):
            self.initialized = False
            calls.append(("shutdown", None))

    class FakeScheduler:
        async def start(self):
            calls.append(("scheduler_start", None))

        async def stop(self):
            calls.append(("scheduler_stop", None))

    fake_application = FakeApplication()
    scheduler = FakeScheduler()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "42")
    monkeypatch.setenv("VENNELA_CHAT_ENABLED", "true")
    monkeypatch.setenv("VENNELA_API_BASE_URL", "https://vennela.example")
    monkeypatch.setenv(
        "TELEGRAM_WEBHOOK_URL",
        "https://vennela.example/telegram/webhook",
    )
    monkeypatch.setattr(
        "telegram_interface.bot.build_application",
        lambda config: fake_application,
    )
    monkeypatch.setattr(backend, "get_reminder_scheduler", lambda: scheduler)
    monkeypatch.setattr(backend, "_reminder_scheduler", scheduler)

    await backend.startup_event()
    assert logging.getLogger("httpx").level >= logging.WARNING
    assert logging.getLogger("httpcore").level >= logging.WARNING
    assert [name for name, _ in calls] == [
        "scheduler_start",
        "initialize",
        "start",
        "set_webhook",
    ]
    webhook_args = next(args for name, args in calls if name == "set_webhook")
    assert webhook_args["url"] == "https://vennela.example/telegram/webhook"
    assert webhook_args["allowed_updates"] == Update.ALL_TYPES
    assert webhook_args["secret_token"] == WEBHOOK_SECRET

    await backend.shutdown_event()
    assert [name for name, _ in calls][-3:] == [
        "stop",
        "shutdown",
        "scheduler_stop",
    ]
    assert BOT_TOKEN not in caplog.text
    assert WEBHOOK_SECRET not in caplog.text
