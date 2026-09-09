"""
Task Management Service with strict owner isolation and temporal resolution.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from core.temporal.context import TemporalContext
from .models import Task, TaskPriority, TaskStatus
from .repository import InMemoryTaskRepository, TaskRepository


class TaskManager:
    """
    Task manager enforcing owner isolation and temporal context resolution.
    """

    def __init__(
        self,
        repository: Optional[TaskRepository] = None,
        temporal_context: Optional[TemporalContext] = None,
    ) -> None:
        self.repository = repository or InMemoryTaskRepository()
        self.temporal = temporal_context or TemporalContext()

    def create_task(
        self,
        owner_id: str,
        title: str,
        description: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        due_expr: Optional[str] = None,
        start_expr: Optional[str] = None,
        due_at: Optional[datetime] = None,
        start_at: Optional[datetime] = None,
        task_id: Optional[str] = None,
    ) -> Task:
        if not owner_id or not owner_id.strip():
            raise ValueError("owner_id is required")
        if not title or not title.strip():
            raise ValueError("Task title cannot be empty")

        resolved_due_at = due_at
        if resolved_due_at is None and due_expr:
            resolved_due_at = self.temporal.resolve_datetime(due_expr)

        resolved_start_at = start_at
        if resolved_start_at is None and start_expr:
            resolved_start_at = self.temporal.resolve_datetime(start_expr)

        task = Task.create(
            owner_id=owner_id.strip(),
            title=title.strip(),
            description=description.strip(),
            priority=priority,
            start_at=resolved_start_at,
            due_at=resolved_due_at,
            task_id=task_id,
        )
        return self.repository.create(task)

    def list_tasks(
        self,
        owner_id: str,
        status: Optional[TaskStatus] = None,
        due_date_expr: Optional[str] = None,
    ) -> List[Task]:
        if not owner_id or not owner_id.strip():
            raise ValueError("owner_id is required")

        tasks = self.repository.list_by_owner(owner_id.strip(), status=status)

        if due_date_expr:
            target_dt = self.temporal.resolve_datetime(due_date_expr)
            if target_dt:
                target_date = target_dt.date()
                tasks = [
                    t for t in tasks
                    if t.due_at is not None and t.due_at.astimezone(self.temporal.tz).date() == target_date
                ]

        return tasks

    def get_task(self, owner_id: str, task_id: str) -> Task:
        if not owner_id or not owner_id.strip():
            raise ValueError("owner_id is required")
        task = self.repository.get(task_id)
        if task is None:
            raise KeyError(f"Task {task_id} not found")
        if task.owner_id != owner_id.strip():
            raise PermissionError("Access denied: You are not the owner of this task")
        return task

    def update_task(
        self,
        owner_id: str,
        task_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None,
        due_expr: Optional[str] = None,
        due_at: Optional[datetime] = None,
        start_at: Optional[datetime] = None,
    ) -> Task:
        existing = self.get_task(owner_id, task_id)
        now = datetime.now(timezone.utc)

        resolved_due_at = existing.due_at
        if due_at is not None:
            resolved_due_at = due_at
        elif due_expr is not None:
            resolved_due_at = self.temporal.resolve_datetime(due_expr)

        new_status = status if status is not None else existing.status
        completed_at = existing.completed_at
        if new_status == TaskStatus.COMPLETED and existing.status != TaskStatus.COMPLETED:
            completed_at = now
        elif new_status != TaskStatus.COMPLETED:
            completed_at = None

        updated_task = Task(
            task_id=existing.task_id,
            owner_id=existing.owner_id,
            title=title.strip() if title is not None else existing.title,
            description=description.strip() if description is not None else existing.description,
            status=new_status,
            priority=priority if priority is not None else existing.priority,
            created_at=existing.created_at,
            updated_at=now,
            start_at=start_at if start_at is not None else existing.start_at,
            due_at=resolved_due_at,
            completed_at=completed_at,
        )
        return self.repository.update(updated_task)

    def complete_task(self, owner_id: str, task_id: str) -> Task:
        return self.update_task(owner_id, task_id, status=TaskStatus.COMPLETED)

    def cancel_task(self, owner_id: str, task_id: str) -> Task:
        return self.update_task(owner_id, task_id, status=TaskStatus.CANCELLED)

    def delete_task(self, owner_id: str, task_id: str) -> bool:
        self.get_task(owner_id, task_id)  # Enforce permission
        return self.repository.delete(task_id)
