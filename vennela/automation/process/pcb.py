from __future__ import annotations

from .models import ProcessModel
from .states import ProcessState, validate_transition
from typing import Dict, Any


class ConcurrentUpdateError(Exception):
    pass


class PCB:
    """Process Control Block wrapper around ProcessModel.

    Provides helpers and invariants but does not persist directly.
    """

    def __init__(self, model: ProcessModel):
        self.model = model

    def transition(self, to_state: str) -> None:
        validate_transition(self.model.state, to_state)
        self.model.state = to_state
        self.model.version += 1

    def to_dict(self) -> Dict[str, Any]:
        return self.model.to_dict()

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "PCB":
        return PCB(ProcessModel.from_dict(data))

    def bump_version_check(self, expected_version: int) -> None:
        if self.model.version != expected_version:
            raise ConcurrentUpdateError(
                f"Version mismatch: expected={expected_version} current={self.model.version}"
            )
