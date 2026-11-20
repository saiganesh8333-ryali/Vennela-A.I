import logging
from types import SimpleNamespace

import pytest

from telegram_interface.bot import build_application, help_command, main, ping, start, text_message
from telegram_interface.config import TelegramConfig


class FakeMessage:
    def __init__(self):
        self.replies = []
        self.text = "hello"

    async def reply_text(self, value):
        self.replies.append(value)


@pytest.mark.asyncio
async def test_unauthorized_chat_is_ignored():
    message = FakeMessage()
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=99),
        message=message,
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={"config": TelegramConfig("token", frozenset({42}))}
        )
    )
    await ping(update, context)
    await text_message(update, context)
    assert message.replies == []


@pytest.mark.asyncio
async def test_authorized_text_uses_adapter():
    message = FakeMessage()
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=42),
        message=message,
    )

    class Adapter:
        async def respond(self, text, chat_id, request_id=None):
            assert (text, chat_id) == ("hello", 42)
            assert request_id
            return "reply"

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "config": TelegramConfig("token", frozenset({42})),
                "adapter": Adapter(),
            }
        )
    )
    await text_message(update, context)
    assert message.replies == ["reply"]


@pytest.mark.asyncio
async def test_authorized_commands_reply():
    config = TelegramConfig("token", frozenset({42}))

    def make_context():
        return SimpleNamespace(
            application=SimpleNamespace(bot_data={"config": config})
        )

    for handler, expected in (
        (start, "Vennela Telegram interface is ready."),
        (ping, "pong"),
        (help_command, "Send a message to chat with Vennela. Commands: /start, /ping, /help."),
    ):
        message = FakeMessage()
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=42),
            message=message,
        )
        await handler(update, make_context())
        assert message.replies == [expected]


def test_application_registers_expected_handlers():
    application = build_application(TelegramConfig("token", frozenset({42})))
    assert len(application.handlers[0]) == 4
    assert {handler.commands for handler in application.handlers[0][:3]} == {
        frozenset({"start"}),
        frozenset({"ping"}),
        frozenset({"help"}),
    }


def test_main_reaches_blocking_polling(monkeypatch):
    calls = []

    class FakeApplication:
        def run_polling(self):
            calls.append("run_polling")

    monkeypatch.setattr("telegram_interface.bot.build_application", lambda: FakeApplication())
    main()
    assert calls == ["run_polling"]
    assert logging.getLogger("httpx").level >= logging.WARNING
    assert logging.getLogger("httpcore").level >= logging.WARNING
