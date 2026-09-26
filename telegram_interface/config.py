"""Configuration for the isolated Telegram interface."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


class ConfigurationError(ValueError):
    """Raised when required Telegram interface configuration is invalid."""


_ENV_FILE = Path(__file__).resolve().with_name(".env")


def _load_local_env() -> dict[str, str]:
    """Read Telegram interface settings from the package-local .env file."""
    if not _ENV_FILE.is_file():
        return {}

    values: dict[str, str] = {}
    for raw_line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if not separator or not key.strip():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str
    allowed_chat_ids: frozenset[int]
    vennela_api_base_url: str = ""
    vennela_chat_enabled: bool = False
    request_timeout_seconds: float = 120.0
    webhook_url: str = ""

    @property
    def chat_url(self) -> str:
        return f"{self.vennela_api_base_url.rstrip('/')}/chat"


def _parse_chat_ids(value: str) -> frozenset[int]:
    ids: set[int] = set()
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            ids.add(int(item))
        except ValueError as exc:
            raise ConfigurationError("TELEGRAM_ALLOWED_CHAT_IDS must contain integers") from exc
    return frozenset(ids)


def load_config(env: dict[str, str] | None = None) -> TelegramConfig:
    """Load Telegram-only settings from environment variables."""
    source = os.environ if env is None else env
    if env is None:
        source = {**_load_local_env(), **source}
    token = source.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise ConfigurationError("TELEGRAM_BOT_TOKEN is required")

    allowed_chat_ids = _parse_chat_ids(source.get("TELEGRAM_ALLOWED_CHAT_IDS", ""))
    if not allowed_chat_ids:
        raise ConfigurationError("TELEGRAM_ALLOWED_CHAT_IDS must contain at least one chat ID")

    try:
        timeout = float(source.get("TELEGRAM_REQUEST_TIMEOUT_SECONDS", "120"))
    except ValueError as exc:
        raise ConfigurationError("TELEGRAM_REQUEST_TIMEOUT_SECONDS must be a number") from exc
    if timeout <= 0:
        raise ConfigurationError("TELEGRAM_REQUEST_TIMEOUT_SECONDS must be positive")

    enabled = source.get("VENNELA_CHAT_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    api_base_url = source.get("VENNELA_API_BASE_URL", "").strip().rstrip("/")
    if enabled and not api_base_url:
        raise ConfigurationError(
            "VENNELA_API_BASE_URL is required when VENNELA_CHAT_ENABLED is enabled"
        )
    if api_base_url:
        parsed_url = urlsplit(api_base_url)
        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.hostname
            or parsed_url.username
            or parsed_url.password
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise ConfigurationError("VENNELA_API_BASE_URL must be a valid HTTP(S) base URL")

    webhook_url = source.get("TELEGRAM_WEBHOOK_URL", "").strip().rstrip("/")
    if webhook_url:
        parsed_webhook_url = urlsplit(webhook_url)
        if (
            parsed_webhook_url.scheme != "https"
            or not parsed_webhook_url.hostname
            or parsed_webhook_url.username
            or parsed_webhook_url.password
            or parsed_webhook_url.query
            or parsed_webhook_url.fragment
            or parsed_webhook_url.path != "/telegram/webhook"
        ):
            raise ConfigurationError(
                "TELEGRAM_WEBHOOK_URL must be an HTTPS URL ending in /telegram/webhook"
            )

    return TelegramConfig(
        bot_token=token,
        allowed_chat_ids=allowed_chat_ids,
        vennela_api_base_url=api_base_url,
        vennela_chat_enabled=enabled,
        request_timeout_seconds=timeout,
        webhook_url=webhook_url,
    )
