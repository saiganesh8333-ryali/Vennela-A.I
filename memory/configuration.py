"""Deterministic configuration for Smart Memory decisions."""

from __future__ import annotations

from enum import Enum

from .models import MemoryDomain


class MemoryLifecycle(str, Enum):
    CANDIDATE = "candidate"
    PERSISTENT = "persistent"
    TEMPORARY = "temporary"


PERSISTENT_SCORE_THRESHOLD = 0.40
PREFERENCE_SCORE_THRESHOLD = 0.20
MAX_MEMORY_INPUT_LENGTH = 5000

EXPLICIT_MEMORY_MARKERS = (
    "remember",
    "don't forget",
    "do not forget",
    "my name is",
    "call me",
    "keep this in mind",
)

TRANSIENT_MARKERS = (
    "hello",
    "hi",
    "hey",
    "thanks",
    "thank you",
    "what is",
    "what's",
    "who is",
    "who's",
    "how do i",
    "how can i",
    "can you",
    "could you",
    "please explain",
)

CORE_MARKERS = (
    "vennela core",
    "system architecture",
    "system policy",
    "core knowledge",
)


def normalize_domain(value: str | MemoryDomain | None) -> MemoryDomain:
    """Return a validated domain, defaulting to Boss Personal."""
    if value is None:
        return MemoryDomain.BOSS_PERSONAL
    if isinstance(value, MemoryDomain):
        return value
    try:
        return MemoryDomain(str(value).strip().lower())
    except ValueError as exc:
        raise ValueError("invalid memory domain") from exc


def infer_domain(text: str, requested: str | MemoryDomain | None = None) -> MemoryDomain:
    """Infer a domain only from explicit core language or an explicit override."""
    if requested is not None:
        return normalize_domain(requested)
    lowered = text.lower()
    if any(marker in lowered for marker in CORE_MARKERS):
        return MemoryDomain.VENNELA_CORE
    return MemoryDomain.BOSS_PERSONAL


def has_explicit_memory_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in EXPLICIT_MEMORY_MARKERS)


def is_transient_input(text: str) -> bool:
    lowered = text.lower().strip()
    if lowered.endswith("?"):
        return True
    return any(lowered == marker or lowered.startswith(marker + " ") for marker in TRANSIENT_MARKERS)
