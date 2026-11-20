"""Advanced Fallback Engine implementing tiered state machine."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable, Iterator, Sequence

from .circuit_breaker import CircuitBreaker, CircuitState
from .contracts import (
    Attempt,
    Failure,
    FailureKind,
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    RoutingError,
)
from .health import HealthRegistry
from .performance import LatencyTracker
from .providers.base import BaseLLMProvider


class FallbackEngine:
    """Orchestrates fallback execution across models, providers, and emergency tiers."""

    def __init__(
        self,
        providers: dict[str, BaseLLMProvider],
        health: HealthRegistry,
        max_retries: int = 2,
        retry_delay_seconds: float = 0.0,
        emergency_model_id: str = "meta-llama/llama-3.1-8b-instruct",
    ) -> None:
        self.providers = providers
        self.health = health
        self.max_retries = max(0, max_retries)
        self.retry_delay_seconds = max(0.0, retry_delay_seconds)
        self.emergency_model_id = emergency_model_id

    def is_emergency_candidate(self, model_id: str) -> bool:
        return model_id == self.emergency_model_id or "emergency" in model_id.lower() or "8b" in model_id.lower()

    def execute_completion(
        self,
        request: LLMRequest,
        candidates: Sequence[tuple[str, str]],  # (model_id, provider)
        tracker: LatencyTracker | None = None,
    ) -> tuple[LLMResponse, list[Attempt]]:
        attempts: list[Attempt] = []
        last_failure: Failure | None = None
        blocked_providers: set[str] = set()
        blocked_models: set[str] = set()
        seen: set[tuple[str, str]] = set()

        max_total_attempts = self.max_retries + 1

        for model_id, provider_name in candidates:
            if len(attempts) >= max_total_attempts:
                break

            if (model_id, provider_name) in seen:
                continue

            is_emergency = self.is_emergency_candidate(model_id)

            if model_id in blocked_models:
                continue
            if provider_name in blocked_providers and not is_emergency:
                continue

            seen.add((model_id, provider_name))

            # Circuit Breaker check
            if not self.health.is_available(provider_name, model_id, probe=True) and not is_emergency:
                failure = Failure(
                    FailureKind.CIRCUIT_OPEN,
                    f"Circuit breaker is OPEN for {provider_name}/{model_id}",
                    retryable=True,
                    provider=provider_name,
                    model_id=model_id,
                )
                attempts.append(Attempt(model_id=model_id, provider=provider_name, failure=failure))
                last_failure = failure
                continue

            provider = self.providers.get(provider_name)
            if provider is None:
                failure = Failure(
                    FailureKind.UNKNOWN,
                    f"No provider adapter registered for '{provider_name}'",
                    retryable=False,
                    provider=provider_name,
                    model_id=model_id,
                )
                attempts.append(Attempt(model_id=model_id, provider=provider_name, failure=failure))
                last_failure = failure
                continue

            if len(attempts) > 0 and tracker:
                tracker.start_fallback()

            attempt_start = time.perf_counter()
            try:
                response = provider.complete(request, model_id)
                attempt_latency = (time.perf_counter() - attempt_start) * 1000.0

                self.health.record_success(provider_name, attempt_latency, model_id)
                attempts.append(Attempt(model_id=model_id, provider=provider_name, latency_ms=attempt_latency))

                if tracker:
                    if len(attempts) > 1:
                        tracker.end_fallback()
                    tracker.record_connection_latency(attempt_latency)

                final_resp = LLMResponse(
                    text=response.text,
                    model_id=response.model_id,
                    provider=response.provider,
                    latency_ms=attempt_latency,
                    ttft_ms=response.ttft_ms,
                    usage=response.usage,
                    attempts=tuple(attempts),
                    metadata={"attempts_count": len(attempts)},
                    raw=response.raw,
                )
                return final_resp, attempts

            except RoutingError as exc:
                attempt_latency = (time.perf_counter() - attempt_start) * 1000.0
                last_failure = exc.failure
                attempts.append(Attempt(model_id=model_id, provider=provider_name, latency_ms=attempt_latency, failure=exc.failure))

                self.health.record_failure(provider_name, exc.failure.kind, model_id, reason=exc.failure.message)

                if exc.failure.kind in {
                    FailureKind.AUTHENTICATION,
                    FailureKind.NO_API_KEY,
                    FailureKind.TIMEOUT,
                    FailureKind.RATE_LIMIT,
                    FailureKind.SERVER,
                    FailureKind.NETWORK,
                    FailureKind.MALFORMED_RESPONSE,
                }:
                    blocked_providers.add(provider_name)
                elif exc.failure.kind in {
                    FailureKind.MODEL_UNAVAILABLE,
                    FailureKind.CONTEXT_LIMIT,
                    FailureKind.INVALID_REQUEST,
                }:
                    blocked_models.add(model_id)

                if self.retry_delay_seconds > 0 and len(attempts) < max_total_attempts:
                    time.sleep(self.retry_delay_seconds)

        raise RoutingError(
            last_failure or Failure(FailureKind.UNKNOWN, "All fallback candidates exhausted without success")
        )

    def execute_stream(
        self,
        request: LLMRequest,
        candidates: Sequence[tuple[str, str]],
        tracker: LatencyTracker | None = None,
    ) -> Iterator[LLMStreamChunk]:
        attempts: list[Attempt] = []
        last_failure: Failure | None = None
        blocked_providers: set[str] = set()
        blocked_models: set[str] = set()
        seen: set[tuple[str, str]] = set()

        max_total_attempts = self.max_retries + 1

        for model_id, provider_name in candidates:
            if len(attempts) >= max_total_attempts:
                break
            if (model_id, provider_name) in seen:
                continue

            is_emergency = self.is_emergency_candidate(model_id)

            if model_id in blocked_models:
                continue
            if provider_name in blocked_providers and not is_emergency:
                continue

            seen.add((model_id, provider_name))

            if not self.health.is_available(provider_name, model_id, probe=True) and not is_emergency:
                failure = Failure(
                    FailureKind.CIRCUIT_OPEN,
                    f"Circuit breaker is OPEN for {provider_name}/{model_id}",
                    retryable=True,
                    provider=provider_name,
                    model_id=model_id,
                )
                attempts.append(Attempt(model_id=model_id, provider=provider_name, failure=failure))
                last_failure = failure
                continue

            provider = self.providers.get(provider_name)
            if provider is None:
                continue

            if len(attempts) > 0 and tracker:
                tracker.start_fallback()

            attempt_start = time.perf_counter()
            try:
                stream_iter = provider.stream(request, model_id)
                first_chunk = next(stream_iter)
                attempt_latency = (time.perf_counter() - attempt_start) * 1000.0

                if tracker:
                    if len(attempts) > 1:
                        tracker.end_fallback()
                    tracker.record_connection_latency(attempt_latency)
                    if first_chunk.ttft_ms is not None:
                        tracker.record_ttft(first_chunk.ttft_ms)

                self.health.record_success(provider_name, attempt_latency, model_id)

                def _generator():
                    yield first_chunk
                    for chunk in stream_iter:
                        yield chunk

                return _generator()

            except (RoutingError, StopIteration) as exc:
                attempt_latency = (time.perf_counter() - attempt_start) * 1000.0
                failure = exc.failure if isinstance(exc, RoutingError) else Failure(FailureKind.SERVER, "Stream ended prematurely", True, provider_name)
                last_failure = failure
                attempts.append(Attempt(model_id=model_id, provider=provider_name, latency_ms=attempt_latency, failure=failure))
                self.health.record_failure(provider_name, failure.kind, model_id, reason=failure.message)

                if failure.kind in {
                    FailureKind.AUTHENTICATION,
                    FailureKind.NO_API_KEY,
                    FailureKind.TIMEOUT,
                    FailureKind.RATE_LIMIT,
                    FailureKind.SERVER,
                    FailureKind.NETWORK,
                    FailureKind.MALFORMED_RESPONSE,
                }:
                    blocked_providers.add(provider_name)
                elif failure.kind in {FailureKind.MODEL_UNAVAILABLE, FailureKind.CONTEXT_LIMIT}:
                    blocked_models.add(model_id)

        raise RoutingError(
            last_failure or Failure(FailureKind.UNKNOWN, "All streaming fallback candidates exhausted without success")
        )
