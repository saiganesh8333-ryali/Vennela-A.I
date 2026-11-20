"""Structured logging and telemetry for Web Intelligence with zero-leak guarantees."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re
import time
from typing import Any

# Patterns to mask sensitive tokens, bearer keys, and api keys
SECRET_PATTERNS = [
    re.compile(r"(tvly-[A-Za-z0-9_\-]+)", re.IGNORECASE),
    re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]+", re.IGNORECASE),
    re.compile(r"(api[_-]?key[\"'\s:=]+)[\"']?([A-Za-z0-9_\-]+)[\"']?", re.IGNORECASE),
    re.compile(r"(key=)[^&\s]+", re.IGNORECASE),
    re.compile(r"(sk-[A-Za-z0-9_\-]+)", re.IGNORECASE),
]


def sanitize(text: str) -> str:
    """Mask any potential secrets or sensitive tokens from logs and error text."""
    if not isinstance(text, str):
        return str(text)
    sanitized = text
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub(r"[REDACTED]", sanitized)
    return sanitized


logger = logging.getLogger("vennela.web_intelligence")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [VennelaWebHunt] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def log_info(message: str, **kwargs: Any) -> None:
    safe_msg = sanitize(message)
    if kwargs:
        safe_kwargs = {k: sanitize(str(v)) for k, v in kwargs.items()}
        logger.info("%s | %s", safe_msg, safe_kwargs)
    else:
        logger.info(safe_msg)


def log_warning(message: str, **kwargs: Any) -> None:
    safe_msg = sanitize(message)
    if kwargs:
        safe_kwargs = {k: sanitize(str(v)) for k, v in kwargs.items()}
        logger.warning("%s | %s", safe_msg, safe_kwargs)
    else:
        logger.warning(safe_msg)


def log_error(message: str, **kwargs: Any) -> None:
    safe_msg = sanitize(message)
    if kwargs:
        safe_kwargs = {k: sanitize(str(v)) for k, v in kwargs.items()}
        logger.error("%s | %s", safe_msg, safe_kwargs)
    else:
        logger.error(safe_msg)


@dataclass
class TelemetryTracker:
    """Tracks execution metrics and operational diagnostics for a hunt request."""

    started_at: float = field(default_factory=time.perf_counter)
    search_queries_count: int = 0
    results_found_count: int = 0
    results_filtered_count: int = 0
    pages_retrieved_count: int = 0
    pages_failed_count: int = 0
    cache_hits: int = 0
    errors: list[str] = field(default_factory=list)

    def record_error(self, message: str) -> None:
        safe = sanitize(message)
        self.errors.append(safe)
        log_warning("Telemetry captured error", error=safe)

    @property
    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self.started_at) * 1000

    def summary(self) -> dict[str, Any]:
        return {
            "elapsed_ms": round(self.elapsed_ms, 2),
            "search_queries_count": self.search_queries_count,
            "results_found_count": self.results_found_count,
            "results_filtered_count": self.results_filtered_count,
            "pages_retrieved_count": self.pages_retrieved_count,
            "pages_failed_count": self.pages_failed_count,
            "cache_hits": self.cache_hits,
            "errors_count": len(self.errors),
        }
