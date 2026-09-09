"""
Domain models and contracts for the Task management subsystem.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import uuid


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TaskPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


@dataclass(frozen=True)
class Task:
    task_id: str
    owner_id: str
    title: str
    description: str
    status: TaskStatus
    priority: TaskPriority
    created_at: datetime
    updated_at: datetime
    start_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "owner_id": self.owner_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "start_at": self.start_at.isoformat() if self.start_at else None,
            "due_at": self.due_at.isoformat() if self.due_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        created_at = (
            datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
            if isinstance(data.get("created_at"), str)
            else (data.get("created_at") or datetime.now(timezone.utc))
        )
        updated_at = (
            datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
            if isinstance(data.get("updated_at"), str)
            else (data.get("updated_at") or created_at)
        )
        start_at = (
            datetime.fromisoformat(data["start_at"].replace("Z", "+00:00"))
            if data.get("start_at") and isinstance(data["start_at"], str)
            else data.get("start_at")
        )
        due_at = (
            datetime.fromisoformat(data["due_at"].replace("Z", "+00:00"))
            if data.get("due_at") and isinstance(data["due_at"], str)
            else data.get("due_at")
        )
        completed_at = (
            datetime.fromisoformat(data["completed_at"].replace("Z", "+00:00"))
            if data.get("completed_at") and isinstance(data["completed_at"], str)
            else data.get("completed_at")
        )

        return cls(
            task_id=data["task_id"],
            owner_id=data["owner_id"],
            title=data["title"],
            description=data.get("description", ""),
            status=TaskStatus(data.get("status", TaskStatus.PENDING.value)),
            priority=TaskPriority(data.get("priority", TaskPriority.NORMAL.value)),
            created_at=created_at,
            updated_at=updated_at,
            start_at=start_at,
            due_at=due_at,
            completed_at=completed_at,
        )

    @classmethod
    def create(
        cls,
        owner_id: str,
        title: str,
        description: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        start_at: Optional[datetime] = None,
        due_at: Optional[datetime] = None,
        task_id: Optional[str] = None,
    ) -> Task:
        now = datetime.now(timezone.utc)
        tid = task_id or f"task_{uuid.uuid4().hex[:12]}"
        return cls(
            task_id=tid,
            owner_id=owner_id,
            title=title.strip(),
            description=description.strip(),
            status=TaskStatus.PENDING,
            priority=priority,
            created_at=now,
            updated_at=now,
            start_at=start_at,
            due_at=due_at,
            completed_at=None,
        )
