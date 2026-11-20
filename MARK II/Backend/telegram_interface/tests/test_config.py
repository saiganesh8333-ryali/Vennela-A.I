import pytest

from telegram_interface.config import ConfigurationError, load_config


def test_load_config_requires_token():
    with pytest.raises(ConfigurationError, match="TELEGRAM_BOT_TOKEN"):
        load_config({})


def test_load_config_parses_isolated_settings():
    config = load_config(
        {
            "TELEGRAM_BOT_TOKEN": "not-a-real-token",
            "TELEGRAM_ALLOWED_CHAT_IDS": "123, -45",
            "VENNELA_CHAT_ENABLED": "true",
            "VENNELA_API_BASE_URL": "https://vennela.example",
            "TELEGRAM_WEBHOOK_URL": "https://vennela.example/telegram/webhook",
        }
    )
    assert config.allowed_chat_ids == frozenset({123, -45})
    assert config.vennela_chat_enabled is True
    assert config.chat_url == "https://vennela.example/chat"
    assert config.request_timeout_seconds == 120
    assert config.webhook_url == "https://vennela.example/telegram/webhook"


def test_load_config_rejects_invalid_chat_id():
    with pytest.raises(ConfigurationError, match="CHAT_IDS"):
        load_config({"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_ALLOWED_CHAT_IDS": "abc"})


def test_load_config_requires_api_url_when_forwarding_is_enabled():
    with pytest.raises(ConfigurationError, match="VENNELA_API_BASE_URL"):
        load_config(
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "TELEGRAM_ALLOWED_CHAT_IDS": "123",
                "VENNELA_CHAT_ENABLED": "true",
            }
        )


def test_load_config_rejects_invalid_api_url():
    with pytest.raises(ConfigurationError, match="valid HTTP"):
        load_config(
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "TELEGRAM_ALLOWED_CHAT_IDS": "123",
                "VENNELA_CHAT_ENABLED": "true",
                "VENNELA_API_BASE_URL": "file:///tmp/vennela",
            }
        )


@pytest.mark.parametrize(
    "webhook_url",
    (
        "http://vennela.example/telegram/webhook",
        "https://vennela.example/wrong-path",
        "https://vennela.example/prefix/telegram/webhook",
        "https://user:pass@vennela.example/telegram/webhook",
    ),
)
def test_load_config_rejects_invalid_webhook_url(webhook_url):
    with pytest.raises(ConfigurationError, match="TELEGRAM_WEBHOOK_URL"):
        load_config(
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "TELEGRAM_ALLOWED_CHAT_IDS": "123",
                "TELEGRAM_WEBHOOK_URL": webhook_url,
            }
        )
