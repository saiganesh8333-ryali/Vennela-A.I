"""Small, safe structured logging helpers for backend request tracing."""

from __future__ import annotations

import json
import logging
import re
from typing import Any


logger = logging.getLogger("vennela.backend")
_SECRET_PATTERN = re.compile(
    r"(authorization|api[_-]?key|token|password|secret)\s*[:=]\s*[^\s,}]+",
    re.IGNORECASE,
)


def safe_value(value: Any) -> str:
    """Return a bounded value with common credentials removed."""
    text = str(value)
    text = _SECRET_PATTERN.sub(r"\1=[REDACTED]", text)
    return text[:300]


def log_event(layer: str, operation: str, **fields: Any) -> None:
    """Emit one machine-readable event without prompt or credential contents."""
    event = {
        "layer": layer,
        "operation": operation,
        **{key: safe_value(value) for key, value in fields.items() if value is not None},
    }
    logger.info("[%s] %s | %s", layer.upper(), operation, json.dumps(event, sort_keys=True))


def log_failure(layer: str, operation: str, error: BaseException, **fields: Any) -> None:
    fields.setdefault("status", "failed")
    fields.setdefault("error_type", type(error).__name__)
    log_event(
        layer,
        operation,
        **fields,
    )
