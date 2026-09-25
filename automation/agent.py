"""Agent contracts, platform types, status definitions, and execution protocols."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any

from .models import ActionType, AgentAction


class AgentPlatform(str, Enum):
    ANDROID = "android"
    PC = "pc"
    MOCK = "mock"


class AgentStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    ERROR = "error"


@dataclass(frozen=True)
class ExecutionResult:
    task_id: str
    success: bool
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    latency_ms: float = 0.0
    agent_id: str | None = None
    device_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "task_id": self.task_id,
            "success": self.success,
            "output": self.output,
            "latency_ms": self.latency_ms,
        }
        if self.error is not None:
            payload["error"] = self.error
        if self.agent_id is not None:
            payload["agent_id"] = self.agent_id
        if self.device_id is not None:
            payload["device_id"] = self.device_id
        return payload


@dataclass
class AgentMetadata:
    agent_id: str
    device_id: str
    platform: AgentPlatform
    status: AgentStatus = AgentStatus.ONLINE
    capabilities: frozenset[ActionType] = frozenset()
    last_heartbeat: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def supports(self, action_type: ActionType) -> bool:
        return action_type in self.capabilities

    def is_available(self) -> bool:
        return self.status == AgentStatus.ONLINE


class BaseExecutionAgent(ABC):
    """Abstract contract for execution agents (Android, PC, or Mock)."""

    def __init__(self, metadata: AgentMetadata) -> None:
        self.metadata = metadata

    @property
    def agent_id(self) -> str:
        return self.metadata.agent_id

    @property
    def device_id(self) -> str:
        return self.metadata.device_id

    @property
    def platform(self) -> AgentPlatform:
        return self.metadata.platform

    @property
    def capabilities(self) -> frozenset[ActionType]:
        return self.metadata.capabilities

    def get_status(self) -> AgentStatus:
        return self.metadata.status

    def set_status(self, status: AgentStatus) -> None:
        self.metadata.status = status

    def heartbeat(self) -> None:
        self.metadata.last_heartbeat = time.time()

    @abstractmethod
    def execute(self, action: AgentAction, task_id: str, context: dict[str, Any] | None = None) -> ExecutionResult:
        """Execute an action on the physical/virtual agent."""

    @abstractmethod
    def cancel(self, task_id: str) -> bool:
        """Cancel a running or scheduled task on the agent."""


class MockExecutionAgent(BaseExecutionAgent):
    """Deterministic in-memory mock agent for testing and verification."""

    def __init__(
        self,
        agent_id: str = "mock-agent-1",
        device_id: str = "mock-device-1",
        platform: AgentPlatform = AgentPlatform.MOCK,
        capabilities: frozenset[ActionType] | None = None,
        default_success: bool = True,
        custom_outputs: dict[ActionType, dict[str, Any]] | None = None,
    ) -> None:
        caps = capabilities if capabilities is not None else frozenset(ActionType)
        metadata = AgentMetadata(
            agent_id=agent_id,
            device_id=device_id,
            platform=platform,
            capabilities=caps,
        )
        super().__init__(metadata)
        self.default_success = default_success
        self.custom_outputs = custom_outputs or {}
        self.executed_actions: list[tuple[AgentAction, str]] = []
        self.cancelled_tasks: list[str] = []

    def execute(self, action: AgentAction, task_id: str, context: dict[str, Any] | None = None) -> ExecutionResult:
        self.executed_actions.append((action, task_id))
        self.heartbeat()

        if not self.metadata.supports(action.type):
            return ExecutionResult(
                task_id=task_id,
                success=False,
                error=f"Action '{action.type.value}' not supported by agent '{self.agent_id}'",
                agent_id=self.agent_id,
                device_id=self.device_id,
            )

        if not self.default_success:
            return ExecutionResult(
                task_id=task_id,
                success=False,
                error="Mock execution simulated failure",
                agent_id=self.agent_id,
                device_id=self.device_id,
            )

        output = dict(self.custom_outputs.get(action.type, {"status": "success", "action": action.type.value}))
        if action.target:
            output["target"] = action.target

        return ExecutionResult(
            task_id=task_id,
            success=True,
            output=output,
            latency_ms=1.5,
            agent_id=self.agent_id,
            device_id=self.device_id,
        )

    def cancel(self, task_id: str) -> bool:
        self.cancelled_tasks.append(task_id)
        return True
