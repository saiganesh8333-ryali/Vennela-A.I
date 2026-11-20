"""Finite State Machine Circuit Breaker for Providers and Models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import threading
import time
from typing import Callable


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class BreakerEntry:
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    opened_at: float | None = None
    last_failure_reason: str | None = None
    probing: bool = False


class CircuitBreaker:
    """Thread-safe circuit breaker with CLOSED, OPEN, and HALF_OPEN states."""

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.failure_threshold = max(1, failure_threshold)
        self.recovery_seconds = max(0.0, recovery_seconds)
        self.clock = clock
        self._lock = threading.Lock()
        self._providers: dict[str, BreakerEntry] = {}
        self._models: dict[tuple[str, str], BreakerEntry] = {}

    def _get_entry(self, provider: str, model_id: str | None = None) -> BreakerEntry:
        if model_id is not None:
            return self._models.setdefault((provider, model_id), BreakerEntry())
        return self._providers.setdefault(provider, BreakerEntry())

    def get_state(self, provider: str, model_id: str | None = None) -> CircuitState:
        with self._lock:
            entry = self._get_entry(provider, model_id)
            self._update_state_locked(entry)
            return entry.state

    def _update_state_locked(self, entry: BreakerEntry) -> None:
        now = self.clock()
        if entry.state == CircuitState.OPEN:
            if entry.opened_at is not None and (now - entry.opened_at) >= self.recovery_seconds:
                entry.state = CircuitState.HALF_OPEN
                entry.probing = False

    def can_execute(self, provider: str, model_id: str | None = None, probe: bool = True) -> bool:
        """Return True if execution is permitted, False if blocked by OPEN circuit."""
        with self._lock:
            p_entry = self._get_entry(provider)
            self._update_state_locked(p_entry)
            if p_entry.state == CircuitState.OPEN:
                return False

            if model_id is not None:
                m_entry = self._get_entry(provider, model_id)
                self._update_state_locked(m_entry)
                if m_entry.state == CircuitState.OPEN:
                    return False

            if probe:
                if p_entry.state == CircuitState.HALF_OPEN:
                    if p_entry.probing:
                        return False
                    p_entry.probing = True

                if model_id is not None and m_entry.state == CircuitState.HALF_OPEN:
                    if m_entry.probing:
                        return False
                    m_entry.probing = True

            return True

    def record_success(self, provider: str, model_id: str | None = None) -> None:
        """Successful execution resets failure count and moves HALF_OPEN -> CLOSED."""
        with self._lock:
            entries = [self._get_entry(provider)]
            if model_id is not None:
                entries.append(self._get_entry(provider, model_id))

            for entry in entries:
                entry.success_count += 1
                entry.failure_count = 0
                entry.opened_at = None
                entry.probing = False
                entry.state = CircuitState.CLOSED

    def record_failure(
        self,
        provider: str,
        model_id: str | None = None,
        reason: str | None = None,
    ) -> CircuitState:
        """Record a failure on provider or model. If threshold reached, transition to OPEN."""
        with self._lock:
            entry = self._get_entry(provider, model_id)
            now = self.clock()
            entry.last_failure_reason = reason
            entry.failure_count += 1
            entry.probing = False

            if entry.state == CircuitState.HALF_OPEN:
                entry.state = CircuitState.OPEN
                entry.opened_at = now
            elif entry.failure_count >= self.failure_threshold:
                entry.state = CircuitState.OPEN
                entry.opened_at = now

            return entry.state

    def reset(self, provider: str | None = None) -> None:
        with self._lock:
            if provider is None:
                self._providers.clear()
                self._models.clear()
            else:
                self._providers.pop(provider, None)
                keys_to_remove = [k for k in self._models if k[0] == provider]
                for k in keys_to_remove:
                    self._models.pop(k, None)
