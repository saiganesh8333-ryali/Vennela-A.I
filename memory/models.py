"""Contracts for the Basic Memory Layer."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, FrozenSet, Optional


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
    session_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    active: bool = True

    def to_dict(self) -> dict:
        return {
            "memory_id": self.memory_id,
            "owner_id": self.owner_id,
            "domain": self.domain.value,
            "category": self.category.value,
            "content": self.content,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "active": self.active,
        }

    @classmethod
    def now(cls, memory_id: str, owner_id: str, domain: MemoryDomain,
            category: MemoryCategory, content: Any, session_id: Optional[str] = None):
        timestamp = datetime.now(timezone.utc)
        return cls(memory_id, owner_id, domain, category, content, session_id,
                   timestamp, timestamp)


class MemoryNotFoundError(KeyError, ValueError):
    """Raised when a canonical memory record cannot be found."""


class RelationshipType(str, Enum):
    PROJECT_GOAL = "PROJECT_GOAL"
    PROJECT_PREFERENCE = "PROJECT_PREFERENCE"
    PROJECT_EVENT = "PROJECT_EVENT"
    GOAL_PREFERENCE = "GOAL_PREFERENCE"
    EVENT_PROJECT = "EVENT_PROJECT"
    RELATED_TO = "RELATED_TO"


@dataclass(frozen=True)
class MemoryRelationship:
    relationship_id: str
    source_memory_id: str
    target_memory_id: str
    relationship_type: RelationshipType
    strength: float
    created_at: datetime
    updated_at: datetime
    active: bool = True
    metadata: Optional[dict[str, Any]] = None

    @property
    def confidence(self) -> float:
        return self.strength

    def to_dict(self) -> dict:
        return {
            "relationship_id": self.relationship_id,
            "source_memory_id": self.source_memory_id,
            "target_memory_id": self.target_memory_id,
            "relationship_type": (
                self.relationship_type.value
                if isinstance(self.relationship_type, RelationshipType)
                else str(self.relationship_type)
            ),
            "strength": self.strength,
            "confidence": self.strength,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "active": self.active,
            "metadata": self.metadata or {},
        }

    @classmethod
    def now(
        cls,
        relationship_id: str,
        source_memory_id: str,
        target_memory_id: str,
        relationship_type: RelationshipType,
        strength: float = 1.0,
        metadata: Optional[dict[str, Any]] = None,
        active: bool = True,
    ):
        timestamp = datetime.now(timezone.utc)
        return cls(
            relationship_id=relationship_id,
            source_memory_id=source_memory_id,
            target_memory_id=target_memory_id,
            relationship_type=relationship_type,
            strength=float(strength),
            created_at=timestamp,
            updated_at=timestamp,
            active=active,
            metadata=metadata or {},
        )


@dataclass(frozen=True)
class ScoredMemory:
    record: MemoryRecord
    score: float
    semantic_similarity: float = 0.0
    importance: float = 0.0
    recency: float = 0.0
    session_boost: float = 0.0
    relational_boost: float = 0.0

    @property
    def memory_id(self) -> str:
        return self.record.memory_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "record": self.record.to_dict(),
            "score": self.score,
            "semantic_similarity": self.semantic_similarity,
            "importance": self.importance,
            "recency": self.recency,
            "session_boost": self.session_boost,
            "relational_boost": self.relational_boost,
        }


@dataclass(frozen=True)
class ConsolidationResult:
    primary_record: MemoryRecord
    consolidated_records: list[MemoryRecord]
    reason: str
    action: str = "merge"

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_record": self.primary_record.to_dict(),
            "consolidated_records": [r.to_dict() for r in self.consolidated_records],
            "reason": self.reason,
            "action": self.action,
        }


@dataclass(frozen=True)
class ConflictResult:
    status: str
    winning_record: Optional[MemoryRecord]
    conflicting_records: list[MemoryRecord]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "winning_record": self.winning_record.to_dict() if self.winning_record else None,
            "conflicting_records": [r.to_dict() for r in self.conflicting_records],
            "reason": self.reason,
        }

