"""
Repository abstraction and implementations for the Task subsystem.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Any, List, Optional

from .models import Task, TaskStatus


class TaskRepository(ABC):
    @abstractmethod
    def create(self, task: Task) -> Task:
        pass

    @abstractmethod
    def get(self, task_id: str) -> Optional[Task]:
        pass

    @abstractmethod
    def list_by_owner(
        self,
        owner_id: str,
        status: Optional[TaskStatus] = None,
    ) -> List[Task]:
        pass

    @abstractmethod
    def update(self, task: Task) -> Task:
        pass

    @abstractmethod
    def delete(self, task_id: str) -> bool:
        pass


class InMemoryTaskRepository(TaskRepository):
    """Deterministic in-memory repository for unit tests and local execution."""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}

    def create(self, task: Task) -> Task:
        if task.task_id in self._tasks:
            raise ValueError(f"Task with ID {task.task_id} already exists")
        self._tasks[task.task_id] = deepcopy(task)
        return deepcopy(task)

    def get(self, task_id: str) -> Optional[Task]:
        task = self._tasks.get(task_id)
        return deepcopy(task) if task is not None else None

    def list_by_owner(
        self,
        owner_id: str,
        status: Optional[TaskStatus] = None,
    ) -> List[Task]:
        result = [
            deepcopy(task)
            for task in self._tasks.values()
            if task.owner_id == owner_id
            and (status is None or task.status == status)
        ]
        return sorted(result, key=lambda t: t.created_at, reverse=True)

    def update(self, task: Task) -> Task:
        if task.task_id not in self._tasks:
            raise KeyError(f"Task with ID {task.task_id} not found")
        self._tasks[task.task_id] = deepcopy(task)
        return deepcopy(task)

    def delete(self, task_id: str) -> bool:
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False


class SupabaseTaskRepository(TaskRepository):
    """Production repository integrating with Supabase tasks table."""

    table_name = "tasks"

    def __init__(self, client: Any) -> None:
        self.client = client

    @staticmethod
    def _check(response: Any) -> list[dict[str, Any]]:
        error = getattr(response, "error", None)
        if error:
            raise RuntimeError(f"Supabase task operation failed: {error}")
        return getattr(response, "data", []) or []

    def create(self, task: Task) -> Task:
        payload = task.to_dict()
        rows = self._check(self.client.table(self.table_name).insert(payload).execute())
        if not rows:
            raise RuntimeError("Failed to insert task in Supabase")
        return Task.from_dict(rows[0])

    def get(self, task_id: str) -> Optional[Task]:
        rows = self._check(
            self.client.table(self.table_name).select("*").eq("task_id", task_id).limit(1).execute()
        )
        return Task.from_dict(rows[0]) if rows else None

    def list_by_owner(
        self,
        owner_id: str,
        status: Optional[TaskStatus] = None,
    ) -> List[Task]:
        query = self.client.table(self.table_name).select("*").eq("owner_id", owner_id)
        if status is not None:
            query = query.eq("status", status.value)
        rows = self._check(query.order("created_at", desc=True).execute())
        return [Task.from_dict(row) for row in rows]

    def update(self, task: Task) -> Task:
        payload = task.to_dict()
        rows = self._check(
            self.client.table(self.table_name).update(payload).eq("task_id", task.task_id).execute()
        )
        if not rows:
            raise KeyError(f"Task with ID {task.task_id} not found")
        return Task.from_dict(rows[0])

    def delete(self, task_id: str) -> bool:
        rows = self._check(
            self.client.table(self.table_name).delete().eq("task_id", task_id).execute()
        )
        return bool(rows)
