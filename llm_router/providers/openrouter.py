"""OpenRouter provider adapter with multi-model collection and streaming."""

from __future__ import annotations

import json
import time
from typing import Any, Iterator

from ..contracts import (
    Failure,
    FailureKind,
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    RoutingError,
)
from .base import BaseLLMProvider, validate_response


class OpenRouterProvider(BaseLLMProvider):
    provider_name = "openrouter"
    base_url = "https://openrouter.ai/api/v1/chat/completions"

    def complete(self, request: LLMRequest, model_id: str) -> LLMResponse:
        if not self.api_key:
            raise RoutingError(
                Failure(FailureKind.NO_API_KEY, "OpenRouter API key is not configured", False, self.provider_name)
            )

        payload: dict[str, Any] = {
            "model": model_id,
            "messages": request.normalized_messages(),
            "stream": False,
        }
        if request.structured_output:
            payload["response_format"] = {"type": "json_object"}
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            payload["top_p"] = request.top_p

        started = time.perf_counter()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://vennela.ai",
            "X-Title": "Vennela AI",
            "Accept": "application/json",
        }

        raw = self._post_json(self.base_url, payload, headers)
        latency_ms = (time.perf_counter() - started) * 1000.0

        try:
            choice = raw["choices"][0]["message"]
            content = choice.get("content")
            if content is None and "reasoning" in choice:
                content = choice["reasoning"]
            if content is None:
                content = ""
            text = str(content)
        except (KeyError, IndexError, TypeError):
            raise RoutingError(
                Failure(FailureKind.MALFORMED_RESPONSE, "OpenRouter returned malformed response choices", True, self.provider_name)
            )

        usage = raw.get("usage") if isinstance(raw, dict) else {}
        resp = LLMResponse(
            text=text,
            model_id=model_id,
            provider=self.provider_name,
            latency_ms=latency_ms,
            usage=usage or {},
            raw=raw,
        )
        return validate_response(
            resp,
            expected_model=model_id,
            expected_provider=self.provider_name,
            structured_output=request.structured_output,
        )

    def stream(self, request: LLMRequest, model_id: str) -> Iterator[LLMStreamChunk]:
        if not self.api_key:
            raise RoutingError(
                Failure(FailureKind.NO_API_KEY, "OpenRouter API key is not configured", False, self.provider_name)
            )

        payload: dict[str, Any] = {
            "model": model_id,
            "messages": request.normalized_messages(),
            "stream": True,
        }
        if request.structured_output:
            payload["response_format"] = {"type": "json_object"}
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            payload["top_p"] = request.top_p

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://vennela.ai",
            "X-Title": "Vennela AI",
            "Accept": "text/event-stream",
        }

        started = time.perf_counter()
        ttft_recorded = False
        idx = 0

        for chunk_data in self._stream_sse(self.base_url, payload, headers, model_id):
            try:
                parsed = json.loads(chunk_data)
                choices = parsed.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    now_ms = (time.perf_counter() - started) * 1000.0
                    ttft = now_ms if not ttft_recorded else None
                    ttft_recorded = True
                    yield LLMStreamChunk(
                        delta=content,
                        model_id=model_id,
                        provider=self.provider_name,
                        index=idx,
                        is_final=False,
                        ttft_ms=ttft,
                    )
                    idx += 1
            except (json.JSONDecodeError, KeyError, IndexError):
                continue

        yield LLMStreamChunk(
            delta="",
            model_id=model_id,
            provider=self.provider_name,
            index=idx,
            is_final=True,
        )
