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
