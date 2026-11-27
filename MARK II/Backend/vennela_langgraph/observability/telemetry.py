import threading
from time import perf_counter
from typing import List, Optional
from pydantic import BaseModel


class TelemetryEvent(BaseModel):
    request_id: str
    session_id: str
    node: str
    event: str
    status: str
    duration_ms: float
    error_category: Optional[str] = None
    failure_kind: Optional[str] = None
    attempt: Optional[int] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    intent_type: Optional[str] = None
    plan_id: Optional[str] = None
    capability: Optional[str] = None


class InMemoryTelemetry:
    def __init__(self, max_events: Optional[int] = None) -> None:
        self._lock = threading.Lock()
        self._max_events = max_events
        self.events: List[TelemetryEvent] = []

    def record(self, state, node: str, event: str, status: str, started: float,
               error_category: Optional[str] = None, provider: Optional[str] = None,
               model: Optional[str] = None, attempt: Optional[int] = None) -> None:
        entry = TelemetryEvent(
            request_id=state.request_id, session_id=state.session_id, node=node,
            event=event, status=status, duration_ms=round((perf_counter() - started) * 1000, 3),
            error_category=error_category, provider=provider, model=model,
            failure_kind=error_category, attempt=attempt,
            intent_type=state.canonical_intent.intent_type.value if state.canonical_intent else None,
            plan_id=state.plan_id,
            capability=node if node in {"memory", "web", "pc", "android"} else None,
        )
        with self._lock:
            self.events.append(entry)
            if self._max_events is not None and len(self.events) > self._max_events:
                del self.events[:-self._max_events]
