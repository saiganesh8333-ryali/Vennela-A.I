"""
Unit tests for Task subsystem with strict owner isolation and temporal resolution.
"""

from datetime import datetime
from zoneinfo import ZoneInfo
import pytest

from core.tasks import InMemoryTaskRepository, TaskManager, TaskPriority, TaskStatus
from core.temporal import TemporalContext


@pytest.fixture
def task_manager():
    fixed = datetime(2026, 9, 10, 10, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    tc = TemporalContext("Asia/Kolkata", fixed_now=fixed)
    repo = InMemoryTaskRepository()
    return TaskManager(repository=repo, temporal_context=tc)


def test_01_create_and_get_task(task_manager):
    task = task_manager.create_task(
        owner_id="boss_1",
        title="Finish Vennela project",
        description="Demo preparation",
        priority=TaskPriority.HIGH,
        due_expr="tomorrow at 5 PM",
    )
    assert task.task_id.startswith("task_")
    assert task.owner_id == "boss_1"
    assert task.title == "Finish Vennela project"
    assert task.status == TaskStatus.PENDING
    assert task.priority == TaskPriority.HIGH
    assert task.due_at is not None
    assert task.due_at.year == 2026 and task.due_at.month == 9 and task.due_at.day == 11
    assert task.due_at.hour == 17

    retrieved = task_manager.get_task(owner_id="boss_1", task_id=task.task_id)
    assert retrieved.task_id == task.task_id
    assert retrieved.title == task.title


def test_02_list_tasks_and_filtering(task_manager):
    task1 = task_manager.create_task(owner_id="boss_1", title="Task Today", due_expr="today")
    task2 = task_manager.create_task(owner_id="boss_1", title="Task Tomorrow", due_expr="tomorrow")
    task3 = task_manager.create_task(owner_id="other_user", title="Other User Task")

    boss_tasks = task_manager.list_tasks(owner_id="boss_1")
    assert len(boss_tasks) == 2
    assert all(t.owner_id == "boss_1" for t in boss_tasks)

    # Filter by due date "tomorrow"
    tomorrow_tasks = task_manager.list_tasks(owner_id="boss_1", due_date_expr="tomorrow")
    assert len(tomorrow_tasks) == 1
    assert tomorrow_tasks[0].title == "Task Tomorrow"


def test_03_update_task(task_manager):
    task = task_manager.create_task(owner_id="boss_1", title="Initial Title")
    updated = task_manager.update_task(
        owner_id="boss_1",
        task_id=task.task_id,
        title="Updated Title",
        priority=TaskPriority.URGENT,
        due_expr="in 2 hours",
    )
    assert updated.title == "Updated Title"
    assert updated.priority == TaskPriority.URGENT
    assert updated.due_at is not None


def test_04_complete_and_cancel_task(task_manager):
    task = task_manager.create_task(owner_id="boss_1", title="Task To Complete")
    completed = task_manager.complete_task(owner_id="boss_1", task_id=task.task_id)
    assert completed.status == TaskStatus.COMPLETED
    assert completed.completed_at is not None

    task2 = task_manager.create_task(owner_id="boss_1", title="Task To Cancel")
    cancelled = task_manager.cancel_task(owner_id="boss_1", task_id=task2.task_id)
    assert cancelled.status == TaskStatus.CANCELLED


def test_05_owner_isolation_enforcement(task_manager):
    task = task_manager.create_task(owner_id="alice", title="Alice Secret Task")

    # Bob attempts to get Alice's task
    with pytest.raises(PermissionError):
        task_manager.get_task(owner_id="bob", task_id=task.task_id)

    # Bob attempts to update Alice's task
    with pytest.raises(PermissionError):
        task_manager.update_task(owner_id="bob", task_id=task.task_id, title="Hacked")

    # Bob attempts to complete Alice's task
    with pytest.raises(PermissionError):
        task_manager.complete_task(owner_id="bob", task_id=task.task_id)

    # Bob attempts to cancel Alice's task
    with pytest.raises(PermissionError):
        task_manager.cancel_task(owner_id="bob", task_id=task.task_id)

    # Bob attempts to delete Alice's task
    with pytest.raises(PermissionError):
        task_manager.delete_task(owner_id="bob", task_id=task.task_id)
