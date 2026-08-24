from __future__ import annotations

from enum import Enum
from typing import Dict, Set


class ProcessState(str, Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    READY = "READY"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    RETRYING = "RETRYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TERMINATED = "TERMINATED"


# Allowed transitions mapping
_ALLOWED_TRANSITIONS: Dict[ProcessState, Set[ProcessState]] = {
    ProcessState.PENDING: {ProcessState.QUEUED, ProcessState.BLOCKED, ProcessState.CANCELLED, ProcessState.TERMINATED},
    ProcessState.QUEUED: {ProcessState.READY, ProcessState.BLOCKED, ProcessState.CANCELLED},
    ProcessState.READY: {ProcessState.RUNNING, ProcessState.BLOCKED, ProcessState.CANCELLED},
    ProcessState.RUNNING: {ProcessState.COMPLETED, ProcessState.FAILED, ProcessState.BLOCKED, ProcessState.RETRYING, ProcessState.CANCELLED, ProcessState.TERMINATED},
    ProcessState.BLOCKED: {ProcessState.READY, ProcessState.FAILED, ProcessState.CANCELLED},
    ProcessState.RETRYING: {ProcessState.QUEUED, ProcessState.FAILED, ProcessState.CANCELLED},
    ProcessState.COMPLETED: set(),
    ProcessState.FAILED: set(),
    ProcessState.CANCELLED: set(),
    ProcessState.TERMINATED: set(),
}


class InvalidStateTransition(Exception):
    pass


def validate_transition(from_state: str, to_state: str) -> None:
    try:
        f = ProcessState(from_state)
        t = ProcessState(to_state)
    except Exception:
        raise InvalidStateTransition(f"Invalid state name: {from_state} -> {to_state}")
    allowed = _ALLOWED_TRANSITIONS.get(f, set())
    if t not in allowed:
        raise InvalidStateTransition(f"Transition not allowed: {f.value} -> {t.value}")
