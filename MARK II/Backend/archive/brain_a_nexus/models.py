"""Shared models for the Vennela agent planning boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DelegationType(str, Enum):
    """The planner's two possible actions."""

    DIRECT = "DIRECT"
    DELEGATE = "DELEGATE"


@dataclass(frozen=True)
class DelegationDecision:
    """Deterministic decision produced before any agent execution."""

    request_id: str
    decision: DelegationType
    task: str
    reason: str
    capability: str | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id must be a non-empty string")
        if not isinstance(self.decision, DelegationType):
            raise ValueError("decision must be a DelegationType")
        if not self.task.strip():
            raise ValueError("task must be a non-empty string")
        if not self.reason.strip():
            raise ValueError("reason must be a non-empty string")
        if self.decision is DelegationType.DELEGATE and not self.capability:
            raise ValueError("delegated decisions require a capability")
        if self.decision is DelegationType.DIRECT and self.capability is not None:
            raise ValueError("direct decisions must not specify a capability")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "decision": self.decision.value,
            "capability": self.capability,
            "task": self.task,
            "reason": self.reason,
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
        }
