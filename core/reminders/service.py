"""
Reminder Management Service with strict owner isolation and temporal resolution.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from core.temporal.context import DEFAULT_TIMEZONE, TemporalContext
from .models import Reminder, ReminderStatus
from .repository import InMemoryReminderRepository, ReminderRepository


class ReminderManager:
    """
    Reminder manager enforcing owner isolation and temporal context resolution.
    """

    def __init__(
        self,
        repository: Optional[ReminderRepository] = None,
        temporal_context: Optional[TemporalContext] = None,
    ) -> None:
        self.repository = repository or InMemoryReminderRepository()
        self.temporal = temporal_context or TemporalContext()

    def create_reminder(
        self,
        owner_id: str,
        title: str,
        description: str = "",
        remind_expr: Optional[str] = None,
        remind_at: Optional[datetime] = None,
        tz_name: Optional[str] = None,
        task_id: Optional[str] = None,
        reminder_id: Optional[str] = None,
    ) -> Reminder:
        if not owner_id or not owner_id.strip():
            raise ValueError("owner_id is required")
        if not title or not title.strip():
            raise ValueError("Reminder title cannot be empty")

        resolved_tz = tz_name or self.temporal.timezone_name
        resolved_remind_at = remind_at

        if resolved_remind_at is None:
            if not remind_expr:
                raise ValueError("Either remind_at or remind_expr must be provided")
            resolved_remind_at = self.temporal.resolve_datetime(remind_expr)
            if resolved_remind_at is None:
                raise ValueError(f"Could not parse reminder time expression: '{remind_expr}'")

        reminder = Reminder.create(
            owner_id=owner_id.strip(),
            title=title.strip(),
            description=description.strip(),
            remind_at=resolved_remind_at,
            tz_name=resolved_tz,
            task_id=task_id,
            reminder_id=reminder_id,
        )
        return self.repository.create(reminder)

    def list_reminders(
        self,
        owner_id: str,
        status: Optional[ReminderStatus] = None,
    ) -> List[Reminder]:
        if not owner_id or not owner_id.strip():
            raise ValueError("owner_id is required")
        return self.repository.list_by_owner(owner_id.strip(), status=status)

    def get_reminder(self, owner_id: str, reminder_id: str) -> Reminder:
        if not owner_id or not owner_id.strip():
            raise ValueError("owner_id is required")
        reminder = self.repository.get(reminder_id)
        if reminder is None:
            raise KeyError(f"Reminder {reminder_id} not found")
        if reminder.owner_id != owner_id.strip():
            raise PermissionError("Access denied: You are not the owner of this reminder")
        return reminder

    def cancel_reminder(self, owner_id: str, reminder_id: str) -> Reminder:
        existing = self.get_reminder(owner_id, reminder_id)
        if existing.status == ReminderStatus.TRIGGERED:
            raise ValueError("Cannot cancel a reminder that has already been triggered")

        updated = Reminder(
            reminder_id=existing.reminder_id,
            owner_id=existing.owner_id,
            title=existing.title,
            description=existing.description,
            remind_at=existing.remind_at,
            timezone=existing.timezone,
            status=ReminderStatus.CANCELLED,
            created_at=existing.created_at,
            updated_at=datetime.now(timezone.utc),
            task_id=existing.task_id,
        )
        return self.repository.update(updated)

    def trigger_reminder(self, reminder_id: str) -> Reminder:
        """Trigger reminder (idempotent transition to TRIGGERED)."""
        existing = self.repository.get(reminder_id)
        if existing is None:
            raise KeyError(f"Reminder {reminder_id} not found")
        if existing.status == ReminderStatus.TRIGGERED:
            return existing
        if existing.status == ReminderStatus.CANCELLED:
            raise ValueError("Cannot trigger a cancelled reminder")

        updated = Reminder(
            reminder_id=existing.reminder_id,
            owner_id=existing.owner_id,
            title=existing.title,
            description=existing.description,
            remind_at=existing.remind_at,
            timezone=existing.timezone,
            status=ReminderStatus.TRIGGERED,
            created_at=existing.created_at,
            updated_at=datetime.now(timezone.utc),
            task_id=existing.task_id,
        )
        return self.repository.update(updated)
