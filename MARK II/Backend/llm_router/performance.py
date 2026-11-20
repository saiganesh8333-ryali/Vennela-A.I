"""Ultra-low latency metrics and performance tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Iterator


@dataclass
class LatencyMetrics:
    routing_decision_latency_ms: float = 0.0
    provider_connection_latency_ms: float = 0.0
    time_to_first_token_ms: float | None = None
    total_response_latency_ms: float = 0.0
    fallback_latency_ms: float = 0.0

    def to_dict(self) -> dict[str, float | None]:
        return {
            "routing_decision_latency_ms": round(self.routing_decision_latency_ms, 3),
            "provider_connection_latency_ms": round(self.provider_connection_latency_ms, 3),
            "time_to_first_token_ms": round(self.time_to_first_token_ms, 3) if self.time_to_first_token_ms is not None else None,
            "total_response_latency_ms": round(self.total_response_latency_ms, 3),
            "fallback_latency_ms": round(self.fallback_latency_ms, 3),
        }


class LatencyTracker:
    """Accurately records latency phases without adding overhead."""

    def __init__(self) -> None:
        self.metrics = LatencyMetrics()
        self._start_time: float = time.perf_counter()
        self._decision_start: float | None = None
        self._fallback_start: float | None = None

    def start_decision(self) -> None:
        self._decision_start = time.perf_counter()

    def end_decision(self) -> float:
        if self._decision_start is not None:
            ms = (time.perf_counter() - self._decision_start) * 1000.0
            self.metrics.routing_decision_latency_ms = ms
            return ms
        return 0.0

    def start_fallback(self) -> None:
        if self._fallback_start is None:
            self._fallback_start = time.perf_counter()

    def end_fallback(self) -> float:
        if self._fallback_start is not None:
            ms = (time.perf_counter() - self._fallback_start) * 1000.0
            self.metrics.fallback_latency_ms = ms
            return ms
        return 0.0

    def record_connection_latency(self, latency_ms: float) -> None:
        self.metrics.provider_connection_latency_ms = latency_ms

    def record_ttft(self, ttft_ms: float) -> None:
        self.metrics.time_to_first_token_ms = ttft_ms

    def complete(self) -> LatencyMetrics:
        self.metrics.total_response_latency_ms = (time.perf_counter() - self._start_time) * 1000.0
        return self.metrics
