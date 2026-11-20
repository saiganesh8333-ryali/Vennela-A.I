"""
Deterministic Scheduler for Reminders and Scheduled Automations.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, List, Optional, Set

from core.reminders.models import Reminder, ReminderStatus
from core.reminders.repository import ReminderRepository
from core.temporal.context import TemporalContext

logger = logging.getLogger(__name__)

TriggerHandler = Callable[[Reminder], Any]


class ReminderScheduler:
    """
    Deterministic time-aware scheduler supporting due detection, triggering,
    status updates, and duplicate-trigger protection.
    """

    def __init__(
        self,
        repository: ReminderRepository,
        temporal_context: Optional[TemporalContext] = None,
    ) -> None:
        self.repository = repository
        self.temporal = temporal_context or TemporalContext()
        self._handlers: List[TriggerHandler] = []
        self._triggered_in_session: Set[str] = set()
        self._running: bool = False
        self._loop_task: Optional[asyncio.Task] = None

    def register_trigger_handler(self, handler: TriggerHandler) -> None:
        """Register a callback for when a reminder triggers."""
        self._handlers.append(handler)

    def check_due_reminders(self, now: Optional[datetime] = None) -> List[Reminder]:
        """
        Check and trigger all due pending reminders deterministically.
        Prevents duplicate triggers and updates status to TRIGGERED.
        """
        current_time = now if now is not None else self.temporal.now()
        # Convert to UTC for consistent comparison across repositories
        if current_time.tzinfo is None:
            check_utc = current_time.replace(tzinfo=timezone.utc)
        else:
            check_utc = current_time.astimezone(timezone.utc)

        due_reminders = self.repository.get_due_reminders(check_utc)
        triggered_list: List[Reminder] = []

        for reminder in due_reminders:
            # Duplicate-trigger protection
            if reminder.reminder_id in self._triggered_in_session:
                continue
            if reminder.status != ReminderStatus.PENDING:
                continue

            # Idempotently update status
            updated = Reminder(
                reminder_id=reminder.reminder_id,
                owner_id=reminder.owner_id,
                title=reminder.title,
                description=reminder.description,
                remind_at=reminder.remind_at,
                timezone=reminder.timezone,
                status=ReminderStatus.TRIGGERED,
                created_at=reminder.created_at,
                updated_at=datetime.now(timezone.utc),
                task_id=reminder.task_id,
            )
            self.repository.update(updated)
            self._triggered_in_session.add(reminder.reminder_id)
            triggered_list.append(updated)

            # Fire handlers
            for handler in self._handlers:
                try:
                    handler(updated)
                except Exception as exc:
                    logger.error("Error in reminder trigger handler for %s: %s", reminder.reminder_id, exc)

        return triggered_list

    async def start(self, interval_seconds: float = 1.0) -> None:
        """Start async background check loop."""
        if self._running:
            return
        self._running = True

        async def _loop() -> None:
            while self._running:
                try:
                    self.check_due_reminders()
                except Exception as e:
                    logger.error("Error in scheduler loop: %s", e)
                await asyncio.sleep(interval_seconds)

        self._loop_task = asyncio.create_task(_loop())
        logger.info("ReminderScheduler started with %ss interval", interval_seconds)

    async def stop(self) -> None:
        """Stop async background check loop."""
        self._running = False
        if self._loop_task is not None:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None
        logger.info("ReminderScheduler stopped")
