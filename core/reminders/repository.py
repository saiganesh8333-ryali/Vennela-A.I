"""
Repository abstraction and implementations for the Reminder subsystem.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, List, Optional

from .models import Reminder, ReminderStatus


class ReminderRepository(ABC):
    @abstractmethod
    def create(self, reminder: Reminder) -> Reminder:
        pass

    @abstractmethod
    def get(self, reminder_id: str) -> Optional[Reminder]:
        pass

    @abstractmethod
    def list_by_owner(
        self,
        owner_id: str,
        status: Optional[ReminderStatus] = None,
    ) -> List[Reminder]:
        pass

    @abstractmethod
    def get_due_reminders(self, now: datetime) -> List[Reminder]:
        pass

    @abstractmethod
    def update(self, reminder: Reminder) -> Reminder:
        pass

    @abstractmethod
    def delete(self, reminder_id: str) -> bool:
        pass


class InMemoryReminderRepository(ReminderRepository):
    """Deterministic in-memory repository for unit tests and local execution."""

    def __init__(self) -> None:
        self._reminders: dict[str, Reminder] = {}

    def create(self, reminder: Reminder) -> Reminder:
        if reminder.reminder_id in self._reminders:
            raise ValueError(f"Reminder with ID {reminder.reminder_id} already exists")
        self._reminders[reminder.reminder_id] = deepcopy(reminder)
        return deepcopy(reminder)

    def get(self, reminder_id: str) -> Optional[Reminder]:
        reminder = self._reminders.get(reminder_id)
        return deepcopy(reminder) if reminder is not None else None

    def list_by_owner(
        self,
        owner_id: str,
        status: Optional[ReminderStatus] = None,
    ) -> List[Reminder]:
        result = [
            deepcopy(r)
            for r in self._reminders.values()
            if r.owner_id == owner_id
            and (status is None or r.status == status)
        ]
        return sorted(result, key=lambda r: r.remind_at)

    def get_due_reminders(self, now: datetime) -> List[Reminder]:
        check_time = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
        result = [
            deepcopy(r)
            for r in self._reminders.values()
            if r.status == ReminderStatus.PENDING
            and r.remind_at <= check_time
        ]
        return sorted(result, key=lambda r: r.remind_at)

    def update(self, reminder: Reminder) -> Reminder:
        if reminder.reminder_id not in self._reminders:
            raise KeyError(f"Reminder with ID {reminder.reminder_id} not found")
        self._reminders[reminder.reminder_id] = deepcopy(reminder)
        return deepcopy(reminder)

    def delete(self, reminder_id: str) -> bool:
        if reminder_id in self._reminders:
            del self._reminders[reminder_id]
            return True
        return False


class SupabaseReminderRepository(ReminderRepository):
    """Production repository integrating with Supabase reminders table."""

    table_name = "reminders"

    def __init__(self, client: Any) -> None:
        self.client = client

    @staticmethod
    def _check(response: Any) -> list[dict[str, Any]]:
        error = getattr(response, "error", None)
        if error:
            raise RuntimeError(f"Supabase reminder operation failed: {error}")
        return getattr(response, "data", []) or []

    def create(self, reminder: Reminder) -> Reminder:
        payload = reminder.to_dict()
        rows = self._check(self.client.table(self.table_name).insert(payload).execute())
        if not rows:
            raise RuntimeError("Failed to insert reminder in Supabase")
        return Reminder.from_dict(rows[0])

    def get(self, reminder_id: str) -> Optional[Reminder]:
        rows = self._check(
            self.client.table(self.table_name).select("*").eq("reminder_id", reminder_id).limit(1).execute()
        )
        return Reminder.from_dict(rows[0]) if rows else None

    def list_by_owner(
        self,
        owner_id: str,
        status: Optional[ReminderStatus] = None,
    ) -> List[Reminder]:
        query = self.client.table(self.table_name).select("*").eq("owner_id", owner_id)
        if status is not None:
            query = query.eq("status", status.value)
        rows = self._check(query.order("remind_at", desc=False).execute())
        return [Reminder.from_dict(row) for row in rows]

    def get_due_reminders(self, now: datetime) -> List[Reminder]:
        now_iso = now.isoformat()
        rows = self._check(
            self.client.table(self.table_name)
            .select("*")
            .eq("status", ReminderStatus.PENDING.value)
            .lte("remind_at", now_iso)
            .order("remind_at", desc=False)
            .execute()
        )
        return [Reminder.from_dict(row) for row in rows]

    def update(self, reminder: Reminder) -> Reminder:
        payload = reminder.to_dict()
        rows = self._check(
            self.client.table(self.table_name)
            .update(payload)
            .eq("reminder_id", reminder.reminder_id)
            .execute()
        )
        if not rows:
            raise KeyError(f"Reminder with ID {reminder.reminder_id} not found")
        return Reminder.from_dict(rows[0])

    def delete(self, reminder_id: str) -> bool:
        rows = self._check(
            self.client.table(self.table_name).delete().eq("reminder_id", reminder_id).execute()
        )
        return bool(rows)
