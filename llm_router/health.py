"""Provider and Model Health Registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import fmean
import threading
from typing import Any

from .circuit_breaker import CircuitBreaker, CircuitState
from .contracts import FailureKind


@dataclass
class HealthStats:
    successes: int = 0
    failures: int = 0
    timeouts: int = 0
    rate_limits: int = 0
    server_errors: int = 0
    auth_errors: int = 0
    network_errors: int = 0
    malformed_responses: int = 0
    latencies_ms: list[float] = field(default_factory=list)

    @property
    def total_requests(self) -> int:
        return self.successes + self.failures

    @property
    def avg_latency_ms(self) -> float:
        return fmean(self.latencies_ms[-100:]) if self.latencies_ms else 0.0

    @property
    def success_rate(self) -> float:
        total = self.total_requests
        return (self.successes / total) if total > 0 else 1.0


class HealthRegistry:
    """Thread-safe registry for telemetry, latency statistics, and health states."""

    def __init__(self, circuit_breaker: CircuitBreaker | None = None) -> None:
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self._lock = threading.Lock()
        self._provider_stats: dict[str, HealthStats] = {}
        self._model_stats: dict[tuple[str, str], HealthStats] = {}

    def _get_stats(self, provider: str, model_id: str | None = None) -> HealthStats:
        if model_id is not None:
            return self._model_stats.setdefault((provider, model_id), HealthStats())
        return self._provider_stats.setdefault(provider, HealthStats())

    def record_success(self, provider: str, latency_ms: float, model_id: str | None = None) -> None:
        with self._lock:
            stats_list = [self._get_stats(provider)]
            if model_id is not None:
                stats_list.append(self._get_stats(provider, model_id))

            for stats in stats_list:
                stats.successes += 1
                if latency_ms >= 0:
                    stats.latencies_ms.append(latency_ms)
                    if len(stats.latencies_ms) > 200:
                        stats.latencies_ms = stats.latencies_ms[-100:]

        self.circuit_breaker.record_success(provider, model_id)

    def record_failure(
        self,
        provider: str,
        kind: FailureKind | str,
        model_id: str | None = None,
        reason: str | None = None,
    ) -> None:
        kind_str = kind.value if isinstance(kind, FailureKind) else str(kind)
        with self._lock:
            stats_list = [self._get_stats(provider)]
            if model_id is not None:
                stats_list.append(self._get_stats(provider, model_id))

            for stats in stats_list:
                stats.failures += 1
                if kind_str == FailureKind.TIMEOUT.value:
                    stats.timeouts += 1
                elif kind_str == FailureKind.RATE_LIMIT.value:
                    stats.rate_limits += 1
                elif kind_str == FailureKind.SERVER.value:
                    stats.server_errors += 1
                elif kind_str in {FailureKind.AUTHENTICATION.value, FailureKind.NO_API_KEY.value}:
                    stats.auth_errors += 1
                elif kind_str == FailureKind.NETWORK.value:
                    stats.network_errors += 1
                elif kind_str == FailureKind.MALFORMED_RESPONSE.value:
                    stats.malformed_responses += 1

        if kind_str in {
            FailureKind.TIMEOUT.value,
            FailureKind.RATE_LIMIT.value,
            FailureKind.SERVER.value,
            FailureKind.AUTHENTICATION.value,
            FailureKind.NO_API_KEY.value,
            FailureKind.NETWORK.value,
            FailureKind.MALFORMED_RESPONSE.value,
        }:
            self.circuit_breaker.record_failure(provider, reason=reason or kind_str)
        elif model_id is not None:
            self.circuit_breaker.record_failure(provider, model_id=model_id, reason=reason or kind_str)

    def is_available(self, provider: str, model_id: str | None = None, probe: bool = True) -> bool:
        return self.circuit_breaker.can_execute(provider, model_id, probe=probe)

    def get_circuit_state(self, provider: str, model_id: str | None = None) -> CircuitState:
        return self.circuit_breaker.get_state(provider, model_id)

    def summary(self, provider: str, model_id: str | None = None) -> dict[str, Any]:
        with self._lock:
            stats = self._get_stats(provider, model_id)
            state = self.circuit_breaker.get_state(provider, model_id)
            return {
                "provider": provider,
                "model_id": model_id or "",
                "circuit_state": state.value,
                "available": self.circuit_breaker.can_execute(provider, model_id, probe=False),
                "successes": stats.successes,
                "failures": stats.failures,
                "timeouts": stats.timeouts,
                "rate_limits": stats.rate_limits,
                "server_errors": stats.server_errors,
                "auth_errors": stats.auth_errors,
                "network_errors": stats.network_errors,
                "malformed_responses": stats.malformed_responses,
                "avg_latency_ms": round(stats.avg_latency_ms, 2),
                "success_rate": round(stats.success_rate, 4),
            }
