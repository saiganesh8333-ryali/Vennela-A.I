"""Configuration and environment management for Vennela Web Intelligence."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class WebIntelligenceSettings:
    """Settings controlling web intelligence execution, providers, timeouts and caching."""

    tavily_api_key: str | None = None
    search_timeout_seconds: float = 15.0
    page_fetch_timeout_seconds: float = 10.0
    max_search_results_per_query: int = 5
    max_pages_to_retrieve: int = 3
    max_page_content_bytes: int = 250_000
    user_agent: str = "VennelaWebHunt/0.1 (+https://vennela.ai; bot)"
    cache_enabled: bool = True
    cache_ttl_seconds: float = 600.0
    telemetry_enabled: bool = True

    @classmethod
    def from_env(cls, env_path: Path | None = None) -> "WebIntelligenceSettings":
        load_dotenv(env_path or PROJECT_ENV_FILE, override=False)
        return cls(
            tavily_api_key=os.getenv("TAVILY_API_KEY") or None,
            search_timeout_seconds=max(0.1, _float("WEB_SEARCH_TIMEOUT_SECONDS", 15.0)),
            page_fetch_timeout_seconds=max(0.1, _float("WEB_PAGE_TIMEOUT_SECONDS", 10.0)),
            max_search_results_per_query=max(1, _int("WEB_MAX_SEARCH_RESULTS", 5)),
            max_pages_to_retrieve=max(0, _int("WEB_MAX_PAGES_TO_RETRIEVE", 3)),
            max_page_content_bytes=max(1024, _int("WEB_MAX_PAGE_CONTENT_BYTES", 250_000)),
            user_agent=os.getenv("WEB_USER_AGENT", "VennelaWebHunt/0.1 (+https://vennela.ai; bot)"),
            cache_enabled=_bool("WEB_CACHE_ENABLED", True),
            cache_ttl_seconds=max(0.0, _float("WEB_CACHE_TTL_SECONDS", 600.0)),
            telemetry_enabled=_bool("WEB_TELEMETRY_ENABLED", True),
        )
