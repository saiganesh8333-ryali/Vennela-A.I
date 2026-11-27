"""Base provider interface and safe HTTP / streaming helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
import logging
import re
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
logger = logging.getLogger(__name__)

_SECRET_SUB_PATTERNS = (
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE),
    re.compile(r"\b(sk-or-v1-|sk-|gsk_|AIza)[A-Za-z0-9._\-]{8,}"),
    re.compile(r"(api[_-]?key|token|authorization|secret)\s*[:=]\s*[^\s,;\"'}]+", re.IGNORECASE),
)


def sanitize_error_detail(raw_text: str, max_len: int = 200) -> str:
    """Extract a concise, secret-redacted upstream error description for safe logging."""
    cleaned = (raw_text or "").strip()
    if not cleaned:
        return ""
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, Mapping):
            err = parsed.get("error")
            if isinstance(err, Mapping):
                parts = []
                if err.get("code") is not None:
                    parts.append(f"code={err.get('code')}")
                if err.get("type"):
                    parts.append(f"type={err.get('type')}")
                if err.get("message"):
                    parts.append(f"message={err.get('message')}")
                if parts:
                    cleaned = " ".join(parts)
            elif err:
                cleaned = str(err)
            elif parsed.get("message") or parsed.get("detail"):
                cleaned = str(parsed.get("message") or parsed.get("detail"))
    except (ValueError, TypeError):
        pass

    for pattern in _SECRET_SUB_PATTERNS:
        cleaned = pattern.sub("[REDACTED]", cleaned)
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > max_len:
        return cleaned[: max_len - 3] + "..."
    return cleaned


def _coerce_status_code(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def classify_http_error(status_code: int, body: str = "") -> FailureKind:
    text = body.lower()
    if status_code == 403 and ("error code: 1010" in text or "access denied" in text or "cloudflare" in text):
        return FailureKind.NETWORK
    if status_code in (401, 403):
        return FailureKind.AUTHENTICATION
    if status_code in (402, 429) or "insufficient credits" in text or "insufficient_quota" in text:
        return FailureKind.RATE_LIMIT
    if status_code in (408, 504):
        return FailureKind.TIMEOUT
    if status_code in (404,):
        return FailureKind.MODEL_UNAVAILABLE
    if status_code == 400 and (
        "not a valid model" in text
        or "model_not_found" in text
        or "unknown model" in text
        or "no endpoints found" in text
        or ("model" in text and "does not exist" in text)
    ):
        return FailureKind.MODEL_UNAVAILABLE
    if status_code == 413 or "context" in text or "token limit" in text:
        return FailureKind.CONTEXT_LIMIT
    if 400 <= status_code < 500:
        return FailureKind.INVALID_REQUEST
    if status_code >= 500:
        return FailureKind.SERVER
    return FailureKind.UNKNOWN


def raise_if_provider_error(
    payload: Any,
    *,
    provider_name: str,
    model_id: str,
    http_status: int = 200,
) -> None:
    """Raise a classified RoutingError if an HTTP-200 JSON payload contains an error object."""
    if not isinstance(payload, Mapping):
        return
    err = payload.get("error")
    if not err:
        return

    raw_err_str = json.dumps({"error": err}, ensure_ascii=False)
    safe_detail = sanitize_error_detail(raw_err_str)
    err_code = _coerce_status_code(err.get("code")) if isinstance(err, Mapping) else None
    effective_status = err_code or http_status
    if err_code is not None:
        kind = classify_http_error(err_code, safe_detail)
    else:
        kind = FailureKind.SERVER if "overloaded" in safe_detail.lower() else FailureKind.MALFORMED_RESPONSE
    retryable = is_retryable_kind(kind)

    logger.warning(
        "provider_payload_error provider=%s model=%s http_status=%s error_code=%s kind=%s detail=%s",
        provider_name,
        model_id,
        http_status,
        err_code,
        kind.value,
        safe_detail,
    )
    raise RoutingError(
        Failure(
            kind,
            f"{provider_name} returned error payload (status={effective_status}): {safe_detail}",
            retryable=retryable,
            provider=provider_name,
            model_id=model_id,
            status_code=effective_status,
        )
    )


def extract_openai_chat_text(
    raw: Any,
    *,
    provider_name: str,
    model_id: str,
) -> str:
    """Validate and extract chat text from an OpenAI-compatible JSON payload with rich diagnostics."""
    raise_if_provider_error(raw, provider_name=provider_name, model_id=model_id, http_status=200)

    if not isinstance(raw, Mapping):
        preview = sanitize_error_detail(repr(raw))
        logger.warning(
            "provider_malformed_payload provider=%s model=%s type=%s detail=%s",
            provider_name,
            model_id,
            type(raw).__name__,
            preview,
        )
        raise RoutingError(
            Failure(
                FailureKind.MALFORMED_RESPONSE,
                f"{provider_name} returned non-object JSON ({type(raw).__name__}): {preview}",
                retryable=True,
                provider=provider_name,
                model_id=model_id,
                status_code=200,
            )
        )

    try:
        choices = raw["choices"]
        if not isinstance(choices, Sequence) or isinstance(choices, (str, bytes)) or not choices:
            raise ValueError("empty choices list")
        first_choice = choices[0]
        message = first_choice["message"]
        content = message.get("content")
        if (content is None or not str(content).strip()) and message.get("reasoning") is not None:
            content = message["reasoning"]
        if (content is None or not str(content).strip()) and message.get("reasoning_content") is not None:
            content = message["reasoning_content"]
        if content is None:
            content = ""
        text = str(content)
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        keys = sorted(str(k) for k in raw.keys())
        preview = sanitize_error_detail(json.dumps(dict(raw), default=str))
        logger.warning(
            "provider_malformed_choices provider=%s model=%s keys=%s err=%s detail=%s",
            provider_name,
            model_id,
            keys,
            type(exc).__name__,
            preview,
        )
        raise RoutingError(
            Failure(
                FailureKind.MALFORMED_RESPONSE,
                f"{provider_name} returned malformed response choices (keys={keys}): {preview}",
                retryable=True,
                provider=provider_name,
                model_id=model_id,
                status_code=200,
            )
        ) from None

    if not text.strip():
        finish_reason = first_choice.get("finish_reason") if isinstance(first_choice, Mapping) else None
        logger.warning(
            "provider_empty_content provider=%s model=%s finish_reason=%s",
            provider_name,
            model_id,
            finish_reason,
        )
        raise RoutingError(
            Failure(
                FailureKind.MALFORMED_RESPONSE,
                f"{provider_name} returned empty content (model={model_id}, finish_reason={finish_reason})",
                retryable=True,
                provider=provider_name,
                model_id=model_id,
                status_code=200,
            )
        )

    return text


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

    def _post_json(
        self,
        url: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str],
        *,
        model_id: str | None = None,
    ) -> Mapping[str, Any]:
        req = self._build_request(url, payload, headers)
        status_code: int | None = None
        raw_body = ""
        try:
            with urlopen(req, timeout=self.timeout) as response:
                status_code = getattr(response, "status", None)
                raw_body = response.read().decode("utf-8", errors="replace")
                return json.loads(raw_body)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:1024]
            safe_detail = sanitize_error_detail(body)
            kind = classify_http_error(exc.code, body)
            retryable = is_retryable_kind(kind)
            logger.warning(
                "provider_http_error provider=%s model=%s status=%s kind=%s detail=%s",
                self.provider_name,
                model_id or payload.get("model"),
                exc.code,
                kind.value,
                safe_detail,
            )
            msg = f"{self.provider_name} request failed with HTTP {exc.code}"
            if safe_detail:
                msg = f"{msg}: {safe_detail}"
            raise RoutingError(
                Failure(
                    kind,
                    msg,
                    retryable=retryable,
                    provider=self.provider_name,
                    model_id=model_id or (str(payload.get("model")) if payload.get("model") else None),
                    status_code=exc.code,
                )
            ) from None
        except (URLError, TimeoutError, OSError) as exc:
            kind = FailureKind.TIMEOUT if isinstance(exc, TimeoutError) else FailureKind.NETWORK
            raise RoutingError(
                Failure(
                    kind,
                    f"{self.provider_name} network connection failed ({type(exc).__name__})",
                    retryable=True,
                    provider=self.provider_name,
                    model_id=model_id,
                )
            ) from None
        except (ValueError, json.JSONDecodeError):
            safe_detail = sanitize_error_detail(raw_body)
            logger.warning(
                "provider_invalid_json provider=%s model=%s status=%s detail=%s",
                self.provider_name,
                model_id or payload.get("model"),
                status_code,
                safe_detail,
            )
            msg = f"{self.provider_name} returned invalid JSON (status={status_code})"
            if safe_detail:
                msg = f"{msg}: {safe_detail}"
            raise RoutingError(
                Failure(
                    FailureKind.MALFORMED_RESPONSE,
                    msg,
                    retryable=True,
                    provider=self.provider_name,
                    model_id=model_id,
                    status_code=status_code,
                )
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
            body = exc.read().decode("utf-8", errors="replace")[:1024]
            safe_detail = sanitize_error_detail(body)
            kind = classify_http_error(exc.code, body)
            retryable = is_retryable_kind(kind)
            logger.warning(
                "provider_stream_http_error provider=%s model=%s status=%s kind=%s detail=%s",
                self.provider_name,
                model_id,
                exc.code,
                kind.value,
                safe_detail,
            )
            msg = f"{self.provider_name} stream failed with HTTP {exc.code}"
            if safe_detail:
                msg = f"{msg}: {safe_detail}"
            raise RoutingError(
                Failure(
                    kind,
                    msg,
                    retryable=retryable,
                    provider=self.provider_name,
                    model_id=model_id,
                    status_code=exc.code,
                )
            ) from None
        except (URLError, TimeoutError, OSError) as exc:
            kind = FailureKind.TIMEOUT if isinstance(exc, TimeoutError) else FailureKind.NETWORK
            raise RoutingError(
                Failure(
                    kind,
                    f"{self.provider_name} stream connection failed ({type(exc).__name__})",
                    retryable=True,
                    provider=self.provider_name,
                    model_id=model_id,
                )
            ) from None
