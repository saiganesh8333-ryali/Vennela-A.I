from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
import json


class ProcessType(str, Enum):
    TOOL_TASK = "tool_task"
    WORKFLOW_TASK = "workflow_task"
    DEVICE_TASK = "device_task"
    ORCHESTRATION_TASK = "orchestration_task"
    COMPOSITE_TASK = "composite_task"


@dataclass
class RetryPolicy:
    attempts: int = 0
    max_attempts: int = 0
    backoff_strategy: str = "none"  # none, fixed, exponential
    next_retry_at: Optional[str] = None
    last_error: Optional[str] = None


@dataclass
class ResourceRequest:
    resource_type: str
    mode: str = "exclusive"  # exclusive or shared
    count: int = 1


@dataclass
class ProcessAction:
    tool: Optional[str] = None
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessModel:
    process_id: str
    parent_id: Optional[str] = None
    child_ids: List[str] = field(default_factory=list)
    process_type: ProcessType = ProcessType.TOOL_TASK
    state: str = "PENDING"
    priority: int = 0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    scheduled_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    assigned_worker_id: Optional[str] = None
    target_device: Optional[str] = None
    action: ProcessAction = field(default_factory=ProcessAction)
    required_resources: List[ResourceRequest] = field(default_factory=list)
    held_resources: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    timeout_seconds: Optional[int] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    execution_metadata: Dict[str, Any] = field(default_factory=dict)
    cancellable: bool = True
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return json.loads(json.dumps(asdict(self)))

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ProcessModel":
        # reconstruct nested dataclasses
        rp = data.get("retry_policy") or {}
        retry = RetryPolicy(**rp) if isinstance(rp, dict) else rp
        action = data.get("action") or {}
        action_obj = ProcessAction(**action) if isinstance(action, dict) else action
        required = [ResourceRequest(**r) for r in (data.get("required_resources") or [])]
        return ProcessModel(
            process_id=data["process_id"],
            parent_id=data.get("parent_id"),
            child_ids=list(data.get("child_ids") or []),
            process_type=ProcessType(data.get("process_type") or ProcessType.TOOL_TASK),
            state=data.get("state") or "PENDING",
            priority=int(data.get("priority") or 0),
            created_at=data.get("created_at") or datetime.utcnow().isoformat(),
            scheduled_at=data.get("scheduled_at"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            assigned_worker_id=data.get("assigned_worker_id"),
            target_device=data.get("target_device"),
            action=action_obj,
            required_resources=required,
            held_resources=list(data.get("held_resources") or []),
            dependencies=list(data.get("dependencies") or []),
            retry_policy=retry,
            timeout_seconds=data.get("timeout_seconds"),
            result=data.get("result"),
            error=data.get("error"),
            execution_metadata=data.get("execution_metadata") or {},
            cancellable=bool(data.get("cancellable") if data.get("cancellable") is not None else True),
            version=int(data.get("version") or 1),
        )
