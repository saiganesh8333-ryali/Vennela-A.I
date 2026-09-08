"""Canonical contracts for the Memory Layer."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Any, FrozenSet, Mapping, Optional
from uuid import uuid4


class MemoryDomain(str, Enum):
    BOSS_PERSONAL = "boss_personal"
    VENNELA_CORE = "vennela_core"
    SESSION = "session"


class MemoryCategory(str, Enum):
    PROFILE = "Profile"
    PREFERENCE = "Preference"
    INTEREST = "Interest"
    GOAL = "Goal"
    PROJECT = "Project"
    SKILL = "Skill"
    FACT = "Fact"
    TASK = "Task"
    EVENT = "Event"
    RELATIONSHIP = "Relationship"


class MemoryStatus(str, Enum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    STALE = "stale"
    ARCHIVED = "archived"
    DELETED = "deleted"


_ALLOWED_TRANSITIONS = {
    MemoryStatus.CANDIDATE: frozenset({
        MemoryStatus.ACTIVE, MemoryStatus.STALE, MemoryStatus.ARCHIVED,
        MemoryStatus.DELETED,
    }),
    MemoryStatus.ACTIVE: frozenset({
        MemoryStatus.STALE, MemoryStatus.ARCHIVED, MemoryStatus.DELETED,
    }),
    MemoryStatus.STALE: frozenset({
        MemoryStatus.ARCHIVED, MemoryStatus.ACTIVE, MemoryStatus.DELETED,
    }),
    MemoryStatus.ARCHIVED: frozenset({MemoryStatus.ACTIVE, MemoryStatus.DELETED}),
    MemoryStatus.DELETED: frozenset(),
}


def normalize_utc(value: datetime | str | None, *, default_now: bool = False) -> datetime | None:
    """Normalize accepted timestamp inputs to an aware UTC datetime."""
    if value is None:
        return datetime.now(timezone.utc) if default_now else None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("invalid ISO-8601 timestamp") from exc
    if not isinstance(value, datetime):
        raise TypeError("timestamp must be a datetime, ISO-8601 string, or None")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    authenticated: bool = True
    scopes: FrozenSet[str] = frozenset()
    session_id: Optional[str] = None


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    owner_id: str
    domain: MemoryDomain
    category: MemoryCategory
    content: Any
    source: str = "conversation"
    confidence: float = 0.5
    importance: float = 0.0
    status: MemoryStatus = MemoryStatus.CANDIDATE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime | str | None = None
    last_accessed_at: datetime | str | None = None
    expires_at: datetime | str | None = None
    session_id: Optional[str] = None
    embedding: Optional[list[float]] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        try:
            domain = self.domain if isinstance(self.domain, MemoryDomain) else MemoryDomain(self.domain)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid memory domain") from exc
        try:
            category = self.category if isinstance(self.category, MemoryCategory) else MemoryCategory(self.category)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid memory category") from exc
        try:
            status = self.status if isinstance(self.status, MemoryStatus) else MemoryStatus(self.status)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid memory status") from exc
        if not isinstance(self.memory_id, str) or not self.memory_id.strip():
            raise ValueError("memory_id is required")
        if not isinstance(self.owner_id, str) or not self.owner_id.strip():
            raise ValueError("owner_id is required")
        if self.content is None or self.content == "" or self.content == {} or self.content == []:
            raise ValueError("content must not be empty")
        try:
            json.dumps(self.content)
        except (TypeError, ValueError) as exc:
            raise ValueError("content must be JSON serializable") from exc
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source is required")
        for name, value in (("confidence", self.confidence), ("importance", self.importance)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        if domain is MemoryDomain.SESSION and not self.session_id:
            raise ValueError("session_id is required for session memory")
        if domain is not MemoryDomain.SESSION and self.session_id is not None:
            raise ValueError("session_id is only valid for session memory")
        if self.embedding is not None:
            if not isinstance(self.embedding, list) or any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                for value in self.embedding
            ):
                raise ValueError("embedding must be a list of numbers")
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary")
        if any(key in self.metadata for key in (
            "profile", "short_term", "long_term", "episodic", "importance", "embeddings",
        )):
            raise ValueError("metadata must not contain a memory snapshot")
        try:
            json.dumps(self.metadata)
        except (TypeError, ValueError) as exc:
            raise ValueError("metadata must be JSON serializable") from exc
        created = normalize_utc(self.created_at, default_now=True)
        updated = normalize_utc(self.updated_at) or created
        object.__setattr__(self, "domain", domain)
        object.__setattr__(self, "category", category)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "created_at", created)
        object.__setattr__(self, "updated_at", updated)
        object.__setattr__(self, "last_accessed_at", normalize_utc(self.last_accessed_at))
        object.__setattr__(self, "expires_at", normalize_utc(self.expires_at))

    @property
    def active(self) -> bool:
        """Compatibility view for the pre-lifecycle boolean contract."""
        return self.status is MemoryStatus.ACTIVE

    def transition(self, status: MemoryStatus) -> "MemoryRecord":
        target = status if isinstance(status, MemoryStatus) else MemoryStatus(status)
        if target not in _ALLOWED_TRANSITIONS[self.status]:
            raise ValueError(f"invalid memory status transition: {self.status.value} -> {target.value}")
        return self.with_updates(status=target)

    def with_updates(self, **changes: Any) -> "MemoryRecord":
        from dataclasses import replace
        changes.setdefault("updated_at", datetime.now(timezone.utc))
        return replace(self, **changes)

    def to_dict(self) -> dict:
        return {
            "memory_id": self.memory_id,
            "owner_id": self.owner_id,
            "domain": self.domain.value,
            "category": self.category.value,
            "content": self.content,
            "source": self.source,
            "confidence": self.confidence,
            "importance": self.importance,
            "status": self.status.value,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_accessed_at": self.last_accessed_at.isoformat() if self.last_accessed_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "embedding": self.embedding,
            "metadata": self.metadata,
            "active": self.active,
        }

    @classmethod
    def now(cls, memory_id: str | None, owner_id: str, domain: MemoryDomain,
            category: MemoryCategory, content: Any, session_id: Optional[str] = None, **kwargs: Any):
        timestamp = datetime.now(timezone.utc)
        return cls(memory_id or str(uuid4()), owner_id, domain, category, content,
                   created_at=timestamp, updated_at=timestamp, session_id=session_id, **kwargs)
