"""
Unit tests for Reminder subsystem and Scheduler integration.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pytest

from core.reminders import InMemoryReminderRepository, ReminderManager, ReminderStatus
from core.scheduler import ReminderScheduler
from core.temporal import TemporalContext


@pytest.fixture
def reminder_setup():
    fixed = datetime(2026, 9, 10, 10, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    tc = TemporalContext("Asia/Kolkata", fixed_now=fixed)
    repo = InMemoryReminderRepository()
    manager = ReminderManager(repository=repo, temporal_context=tc)
    scheduler = ReminderScheduler(repository=repo, temporal_context=tc)
    return {"manager": manager, "scheduler": scheduler, "tc": tc, "repo": repo}


def test_01_create_and_get_reminder(reminder_setup):
    manager = reminder_setup["manager"]
    rem = manager.create_reminder(
        owner_id="boss_1",
        title="Study Maths",
        remind_expr="tomorrow at 7 AM",
    )
    assert rem.reminder_id.startswith("rem_")
    assert rem.owner_id == "boss_1"
    assert rem.title == "Study Maths"
    assert rem.status == ReminderStatus.PENDING
    assert rem.remind_at.year == 2026 and rem.remind_at.month == 9 and rem.remind_at.day == 11
    assert rem.remind_at.hour == 7

    retrieved = manager.get_reminder(owner_id="boss_1", reminder_id=rem.reminder_id)
    assert retrieved.reminder_id == rem.reminder_id
    assert retrieved.title == rem.title


def test_02_list_and_cancel_reminder(reminder_setup):
    manager = reminder_setup["manager"]
    rem1 = manager.create_reminder(owner_id="boss_1", title="Rem 1", remind_expr="in 30 minutes")
    rem2 = manager.create_reminder(owner_id="boss_1", title="Rem 2", remind_expr="in 2 hours")
    rem3 = manager.create_reminder(owner_id="other", title="Other Rem", remind_expr="in 1 hour")

    boss_rems = manager.list_reminders(owner_id="boss_1")
    assert len(boss_rems) == 2
    assert all(r.owner_id == "boss_1" for r in boss_rems)

    cancelled = manager.cancel_reminder(owner_id="boss_1", reminder_id=rem1.reminder_id)
    assert cancelled.status == ReminderStatus.CANCELLED

    pending_rems = manager.list_reminders(owner_id="boss_1", status=ReminderStatus.PENDING)
    assert len(pending_rems) == 1
    assert pending_rems[0].reminder_id == rem2.reminder_id


def test_03_owner_isolation_enforcement(reminder_setup):
    manager = reminder_setup["manager"]
    rem = manager.create_reminder(owner_id="alice", title="Alice Secret Reminder", remind_expr="in 1 hour")

    with pytest.raises(PermissionError):
        manager.get_reminder(owner_id="bob", reminder_id=rem.reminder_id)

    with pytest.raises(PermissionError):
        manager.cancel_reminder(owner_id="bob", reminder_id=rem.reminder_id)


def test_04_scheduler_due_detection_and_duplicate_protection(reminder_setup):
    manager = reminder_setup["manager"]
    scheduler = reminder_setup["scheduler"]
    fixed = datetime(2026, 9, 10, 10, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))

    # Reminder 1: in 10 minutes (10:10)
    rem1 = manager.create_reminder(owner_id="boss_1", title="Call client", remind_expr="in 10 minutes")
    # Reminder 2: in 60 minutes (11:00)
    rem2 = manager.create_reminder(owner_id="boss_1", title="Lunch", remind_expr="in 1 hour")

    triggered_events = []
    scheduler.register_trigger_handler(lambda r: triggered_events.append(r.title))

    # Check at 10:05 -> Nothing due
    t1 = fixed + timedelta(minutes=5)
    due_t1 = scheduler.check_due_reminders(now=t1)
    assert len(due_t1) == 0
    assert len(triggered_events) == 0

    # Check at 10:15 -> rem1 is due
    t2 = fixed + timedelta(minutes=15)
    due_t2 = scheduler.check_due_reminders(now=t2)
    assert len(due_t2) == 1
    assert due_t2[0].reminder_id == rem1.reminder_id
    assert due_t2[0].status == ReminderStatus.TRIGGERED
    assert len(triggered_events) == 1
    assert triggered_events[0] == "Call client"

    # Check at 10:20 -> Duplicate trigger protection should prevent rem1 from firing again
    t3 = fixed + timedelta(minutes=20)
    due_t3 = scheduler.check_due_reminders(now=t3)
    assert len(due_t3) == 0
    assert len(triggered_events) == 1

    # Check at 11:05 -> rem2 is due
    t4 = fixed + timedelta(minutes=65)
    due_t4 = scheduler.check_due_reminders(now=t4)
    assert len(due_t4) == 1
    assert due_t4[0].reminder_id == rem2.reminder_id
    assert len(triggered_events) == 2
    assert triggered_events[1] == "Lunch"
