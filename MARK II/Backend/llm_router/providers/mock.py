"""Deterministic mock provider capable of simulating all failure and latency modes."""

from __future__ import annotations

from enum import Enum
import time
from typing import Any, Iterator, Sequence

from ..contracts import (
    Failure,
    FailureKind,
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    RoutingError,
)
from .base import BaseLLMProvider


class MockMode(str, Enum):
    SUCCESS = "SUCCESS"
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT_429 = "RATE_LIMIT_429"
    SERVER_ERROR_500 = "SERVER_ERROR_500"
    CONNECTION_FAILURE = "CONNECTION_FAILURE"
    AUTH_ERROR = "AUTH_ERROR"
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
    SLOW_RESPONSE = "SLOW_RESPONSE"


class MockProvider(BaseLLMProvider):
    """Deterministic provider for unit testing without consuming API quota."""

    def __init__(
        self,
        provider_name: str = "mock",
        default_text: str = "Mock response text",
        *,
        delay_ms: float = 0.0,
        failures: Sequence[Failure | MockMode] | None = None,
        stream_chunks: Sequence[str] | None = None,
    ) -> None:
        super().__init__(api_key="mock-api-key")
        self.provider_name = provider_name
        self.default_text = default_text
        self.delay_ms = delay_ms
        self._failures: list[Failure | MockMode] = list(failures or [])
        self._stream_chunks = list(stream_chunks or ["Mock", " streaming", " chunks"])
        self.call_count = 0
        self.stream_call_count = 0
        self.recorded_requests: list[tuple[LLMRequest, str]] = []

    def set_failures(self, failures: Sequence[Failure | MockMode]) -> None:
        self._failures = list(failures)

    def add_failure(self, failure: Failure | MockMode) -> None:
        self._failures.append(failure)

    def _convert_mode(self, mode: MockMode) -> Failure:
        if mode == MockMode.TIMEOUT:
            return Failure(FailureKind.TIMEOUT, f"{self.provider_name} request timed out", retryable=True, provider=self.provider_name, status_code=408)
        if mode == MockMode.RATE_LIMIT_429:
            return Failure(FailureKind.RATE_LIMIT, f"{self.provider_name} rate limit exceeded", retryable=True, provider=self.provider_name, status_code=429)
        if mode == MockMode.SERVER_ERROR_500:
            return Failure(FailureKind.SERVER, f"{self.provider_name} internal server error", retryable=True, provider=self.provider_name, status_code=500)
        if mode == MockMode.CONNECTION_FAILURE:
            return Failure(FailureKind.NETWORK, f"{self.provider_name} connection refused", retryable=True, provider=self.provider_name)
        if mode == MockMode.AUTH_ERROR:
            return Failure(FailureKind.AUTHENTICATION, f"{self.provider_name} invalid API key", retryable=False, provider=self.provider_name, status_code=401)
        if mode == MockMode.MALFORMED_RESPONSE:
            return Failure(FailureKind.MALFORMED_RESPONSE, f"{self.provider_name} returned unparseable response", retryable=True, provider=self.provider_name)
        if mode == MockMode.SLOW_RESPONSE:
            return Failure(FailureKind.TIMEOUT, f"{self.provider_name} exceeded latency deadline", retryable=True, provider=self.provider_name)
        return Failure(FailureKind.UNKNOWN, f"Unknown mock failure", retryable=False, provider=self.provider_name)

    def _check_and_raise(self) -> None:
        if self._failures:
            item = self._failures.pop(0)
            if isinstance(item, MockMode):
                if item == MockMode.SLOW_RESPONSE:
                    time.sleep(self.delay_ms / 1000.0 if self.delay_ms else 0.05)
                raise RoutingError(self._convert_mode(item))
            if isinstance(item, Failure):
                raise RoutingError(item)

    def complete(self, request: LLMRequest, model_id: str) -> LLMResponse:
        self.call_count += 1
        self.recorded_requests.append((request, model_id))

        if self.delay_ms > 0:
            time.sleep(self.delay_ms / 1000.0)

        self._check_and_raise()

        response_text = self.default_text
        if request.structured_output and self.default_text == "Mock response text":
            response_text = '{"status": "success", "mock": true}'

        return LLMResponse(
            text=response_text,
            model_id=model_id,
            provider=self.provider_name,
            latency_ms=self.delay_ms,
            usage={"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
            metadata={"mock": True},
        )

    def stream(self, request: LLMRequest, model_id: str) -> Iterator[LLMStreamChunk]:
        self.stream_call_count += 1
        self.recorded_requests.append((request, model_id))

        if self.delay_ms > 0:
            time.sleep(self.delay_ms / 1000.0)

        self._check_and_raise()

        chunks = self._stream_chunks
        start = time.perf_counter()
        ttft_recorded = False

        for idx, chunk in enumerate(chunks):
            now_ms = (time.perf_counter() - start) * 1000.0
            ttft = now_ms if not ttft_recorded else None
            ttft_recorded = True
            is_final = (idx == len(chunks) - 1)
            yield LLMStreamChunk(
                delta=chunk,
                model_id=model_id,
                provider=self.provider_name,
                index=idx,
                is_final=is_final,
                ttft_ms=ttft,
                usage={"total_tokens": len(chunks)} if is_final else None,
            )
