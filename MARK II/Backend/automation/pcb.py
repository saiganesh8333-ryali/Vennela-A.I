"""Process Control Block (PCB), Automation Thread, and Process Lifecycle States."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
import uuid
from typing import Any

from .agent import AgentPlatform, ExecutionResult
from .models import AgentAction


class ProcessState(str, Enum):
    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AutomationThread:
    thread_id: str
    process_id: str
    action: AgentAction
    target_platform: AgentPlatform | None = None
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent_id: str | None = None
    result: ExecutionResult | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "thread_id": self.thread_id,
            "process_id": self.process_id,
            "action": self.action.to_dict()["agent_action"],
            "status": self.status.value,
            "target_platform": self.target_platform.value if self.target_platform else None,
            "assigned_agent_id": self.assigned_agent_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.result is not None:
            data["result"] = self.result.to_dict()
        return data


@dataclass
class ProcessControlBlock:
    """Process Control Block (PCB) tracking state, resources, and threads for an automation goal."""

    process_id: str
    goal: str
    state: ProcessState = ProcessState.CREATED
    threads: list[AutomationThread] = field(default_factory=list)
    preferred_platform: AgentPlatform | None = None
    context: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @classmethod
    def create(
        cls,
        goal: str,
        actions: list[AgentAction] | None = None,
        preferred_platform: AgentPlatform | None = None,
        context: dict[str, Any] | None = None,
    ) -> ProcessControlBlock:
        proc_id = f"proc-{uuid.uuid4().hex[:8]}"
        pcb = cls(
            process_id=proc_id,
            goal=goal,
            preferred_platform=preferred_platform,
            context=context or {},
        )
        if actions:
            for action in actions:
                th_id = f"th-{uuid.uuid4().hex[:8]}"
                thread = AutomationThread(
                    thread_id=th_id,
                    process_id=proc_id,
                    action=action,
                    target_platform=preferred_platform,
                )
                pcb.threads.append(thread)
            pcb.state = ProcessState.READY
        return pcb

    def to_dict(self) -> dict[str, Any]:
        return {
            "process_id": self.process_id,
            "goal": self.goal,
            "state": self.state.value,
            "threads": [t.to_dict() for t in self.threads],
            "preferred_platform": self.preferred_platform.value if self.preferred_platform else None,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
