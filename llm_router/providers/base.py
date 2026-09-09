"""Base provider interface and safe HTTP / streaming helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
import time
from typing import Any, Iterator, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..contracts import (
    Failure,
    FailureKind,
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    RoutingError,
)


USER_AGENT = "VennelaLLMRouter/1.0"


def classify_http_error(status_code: int, body: str = "") -> FailureKind:
    text = body.lower()
    if status_code == 403 and ("error code: 1010" in text or "access denied" in text or "cloudflare" in text):
        return FailureKind.NETWORK
    if status_code in (401, 403):
        return FailureKind.AUTHENTICATION
    if status_code == 429:
        return FailureKind.RATE_LIMIT
    if status_code in (408, 504):
        return FailureKind.TIMEOUT
    if status_code in (404,):
        return FailureKind.MODEL_UNAVAILABLE
    if status_code == 413 or "context" in text or "token limit" in text:
        return FailureKind.CONTEXT_LIMIT
    if 400 <= status_code < 500:
        return FailureKind.INVALID_REQUEST
    if status_code >= 500:
        return FailureKind.SERVER
    return FailureKind.UNKNOWN


def is_retryable_kind(kind: FailureKind) -> bool:
    return kind in {
        FailureKind.RATE_LIMIT,
        FailureKind.TIMEOUT,
        FailureKind.SERVER,
        FailureKind.NETWORK,
    }


def validate_response(
    response: LLMResponse,
    *,
    expected_model: str | None = None,
    expected_provider: str | None = None,
    structured_output: bool = False,
) -> LLMResponse:
    if not isinstance(response, LLMResponse) or not isinstance(response.text, str):
        raise RoutingError(
            Failure(
                FailureKind.MALFORMED_RESPONSE,
                "Provider returned an unparseable response object",
                retryable=True,
                provider=expected_provider,
            )
        )
    if not response.text.strip():
        raise RoutingError(
            Failure(
                FailureKind.MALFORMED_RESPONSE,
                "Provider returned an empty response body",
                retryable=True,
                provider=expected_provider,
            )
        )
    if structured_output:
        try:
            parsed = json.loads(response.text)
            if not isinstance(parsed, (dict, list)):
                raise ValueError("Structured output must be a JSON object or list")
        except (ValueError, TypeError) as exc:
            raise RoutingError(
                Failure(
                    FailureKind.MALFORMED_RESPONSE,
                    f"Invalid structured JSON response: {exc}",
                    retryable=True,
                    provider=expected_provider,
                )
            ) from None

    if expected_model and response.model_id != expected_model:
        raise RoutingError(
            Failure(
                FailureKind.MODEL_UNAVAILABLE,
                f"Expected model '{expected_model}' but provider returned '{response.model_id}'",
                retryable=True,
                provider=expected_provider,
            )
        )
    return response


class BaseLLMProvider(ABC):
    """Abstract interface for LLM provider adapters."""

    provider_name: str = "unknown"

    def __init__(self, api_key: str | None = None, timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.timeout = timeout

    @abstractmethod
    def complete(self, request: LLMRequest, model_id: str) -> LLMResponse:
        """Execute non-streaming completion."""
        raise NotImplementedError

    @abstractmethod
    def stream(self, request: LLMRequest, model_id: str) -> Iterator[LLMStreamChunk]:
        """Execute streaming completion yielding chunks."""
        raise NotImplementedError

    def health_check(self) -> bool:
        """Return True if basic prerequisites (e.g. credentials) are met."""
        return bool(self.api_key)

    def _build_request(self, url: str, payload: Mapping[str, Any], headers: Mapping[str, str]) -> Request:
        data = json.dumps(payload).encode("utf-8")
        merged_headers = {
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            **headers,
        }
        return Request(url, data=data, headers=merged_headers, method="POST")

    def _post_json(self, url: str, payload: Mapping[str, Any], headers: Mapping[str, str]) -> Mapping[str, Any]:
        req = self._build_request(url, payload, headers)
        try:
            with urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:600]
            kind = classify_http_error(exc.code, body)
            retryable = is_retryable_kind(kind)
            msg = f"{self.provider_name} request failed with HTTP {exc.code}"
            raise RoutingError(
                Failure(kind, msg, retryable=retryable, provider=self.provider_name, status_code=exc.code)
            ) from None
        except (URLError, TimeoutError, OSError) as exc:
            kind = FailureKind.TIMEOUT if isinstance(exc, TimeoutError) else FailureKind.NETWORK
            raise RoutingError(
                Failure(kind, f"{self.provider_name} network connection failed", retryable=True, provider=self.provider_name)
            ) from None
        except (ValueError, json.JSONDecodeError):
            raise RoutingError(
                Failure(FailureKind.MALFORMED_RESPONSE, f"{self.provider_name} returned invalid JSON", retryable=True, provider=self.provider_name)
            ) from None

    def _stream_sse(
        self,
        url: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str],
        model_id: str,
    ) -> Iterator[str]:
        req = self._build_request(url, payload, headers)
        try:
            with urlopen(req, timeout=self.timeout) as response:
                for line in response:
                    decoded = line.decode("utf-8", errors="replace").strip()
                    if not decoded or decoded.startswith(":"):
                        continue
                    if decoded.startswith("data: "):
                        data_str = decoded[6:]
                        if data_str == "[DONE]":
                            break
                        yield data_str
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:600]
            kind = classify_http_error(exc.code, body)
            retryable = is_retryable_kind(kind)
            raise RoutingError(
                Failure(kind, f"{self.provider_name} stream failed with HTTP {exc.code}", retryable=retryable, provider=self.provider_name, status_code=exc.code)
            ) from None
        except (URLError, TimeoutError, OSError) as exc:
            kind = FailureKind.TIMEOUT if isinstance(exc, TimeoutError) else FailureKind.NETWORK
            raise RoutingError(
                Failure(kind, f"{self.provider_name} stream connection failed", retryable=True, provider=self.provider_name)
            ) from None
