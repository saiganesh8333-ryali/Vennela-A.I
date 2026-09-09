"""
Domain models and contracts for the Reminder subsystem.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import uuid

from core.temporal.context import DEFAULT_TIMEZONE


class ReminderStatus(str, Enum):
    PENDING = "PENDING"
    TRIGGERED = "TRIGGERED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class Reminder:
    reminder_id: str
    owner_id: str
    title: str
    description: str
    remind_at: datetime
    timezone: str
    status: ReminderStatus
    created_at: datetime
    updated_at: datetime
    task_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "reminder_id": self.reminder_id,
            "owner_id": self.owner_id,
            "title": self.title,
            "description": self.description,
            "remind_at": self.remind_at.isoformat(),
            "timezone": self.timezone,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "task_id": self.task_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Reminder:
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
        remind_at = (
            datetime.fromisoformat(data["remind_at"].replace("Z", "+00:00"))
            if isinstance(data.get("remind_at"), str)
            else data["remind_at"]
        )

        return cls(
            reminder_id=data["reminder_id"],
            owner_id=data["owner_id"],
            title=data["title"],
            description=data.get("description", ""),
            remind_at=remind_at,
            timezone=data.get("timezone", DEFAULT_TIMEZONE),
            status=ReminderStatus(data.get("status", ReminderStatus.PENDING.value)),
            created_at=created_at,
            updated_at=updated_at,
            task_id=data.get("task_id"),
        )

    @classmethod
    def create(
        cls,
        owner_id: str,
        title: str,
        remind_at: datetime,
        description: str = "",
        tz_name: str = DEFAULT_TIMEZONE,
        task_id: Optional[str] = None,
        reminder_id: Optional[str] = None,
    ) -> Reminder:
        now = datetime.now(timezone.utc)
        rid = reminder_id or f"rem_{uuid.uuid4().hex[:12]}"
        return cls(
            reminder_id=rid,
            owner_id=owner_id,
            title=title.strip(),
            description=description.strip(),
            remind_at=remind_at,
            timezone=tz_name,
            status=ReminderStatus.PENDING,
            created_at=now,
            updated_at=now,
            task_id=task_id,
        )
