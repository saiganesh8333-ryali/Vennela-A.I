"""Thin integration adapter connecting Vennela backend to standalone LLM Router."""

from __future__ import annotations

from time import perf_counter
from typing import Any, Iterator, Mapping, Sequence

from .contracts import (
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    Message,
    Role,
    TaskType,
)
from .gateway import Gateway
from .router import LLMRouter


class VennelaLLMAdapter:
    """Minimal adapter that maps Vennela requests into standalone LLM Router contracts."""

    def __init__(self, router: LLMRouter | None = None, mock: bool = False) -> None:
        if router is not None:
            self.router = router
        else:
            self.router = Gateway.create(mock=mock).router

    def route_text(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        messages: Sequence[Message | Mapping[str, str]] | None = None,
        latency_sensitive: bool = False,
        structured_output: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        task_hint: str | None = None,
        request_id: str | None = None,
        timing_callback: Any | None = None,
    ) -> dict[str, Any]:
        """Simple text generation for Vennela backend callers."""
        request_messages = self._build_messages(prompt, system_instruction, messages)

        req = LLMRequest(
            prompt=prompt,
            messages=request_messages,
            task_type=task_hint,
            latency_sensitive=latency_sensitive,
            structured_output=structured_output,
            temperature=temperature,
            max_tokens=max_tokens,
            metadata={"request_id": request_id} if request_id else {},
        )

        started = perf_counter()
        try:
            response = self.router.generate(req)
        except Exception as exc:
            if timing_callback is not None:
                timing_callback(
                    {
                        "duration_ms": round((perf_counter() - started) * 1000, 3),
                        "provider": None,
                        "model": None,
                        "success": False,
                        "failure": type(exc).__name__,
                    }
                )
            raise
        if timing_callback is not None:
            timing_callback(
                {
                    "duration_ms": round((perf_counter() - started) * 1000, 3),
                    "provider": response.provider,
                    "model": response.model_id,
                    "success": True,
                    "fallback_used": response.fallback_used,
                    "attempt_count": len(response.attempts),
                }
            )
        return {
            "text": response.text,
            "model_id": response.model_id,
            "provider": response.provider,
            "latency_ms": response.latency_ms,
            "fallback_used": response.fallback_used,
            "attempts": [
                {
                    "model_id": a.model_id,
                    "provider": a.provider,
                    "succeeded": a.succeeded,
                    "failure_kind": a.failure.kind.value if a.failure else None,
                }
                for a in response.attempts
            ],
            "usage": dict(response.usage),
        }

    def stream_text(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        messages: Sequence[Message | Mapping[str, str]] | None = None,
        latency_sensitive: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        request_id: str | None = None,
    ) -> Iterator[str]:
        """Streaming text token generator for Vennela UI / agents."""
        request_messages = self._build_messages(prompt, system_instruction, messages)

        req = LLMRequest(
            prompt=prompt,
            messages=request_messages,
            latency_sensitive=latency_sensitive,
            streaming=True,
            temperature=temperature,
            max_tokens=max_tokens,
            metadata={"request_id": request_id} if request_id else {},
        )

        for chunk in self.router.stream(req):
            if chunk.delta:
                yield chunk.delta

    @staticmethod
    def _build_messages(
        prompt: str,
        system_instruction: str | None,
        messages: Sequence[Message | Mapping[str, str]] | None,
    ) -> list[Message | Mapping[str, str]]:
        """Preserve caller-provided history while replacing, rather than duplicating, system context."""
        if messages is None:
            result: list[Message | Mapping[str, str]] = []
            if system_instruction:
                result.append(Message(role="system", content=system_instruction))
            result.append(Message(role="user", content=prompt))
            return result

        result = list(messages)
        system_indexes = [
            index
            for index, message in enumerate(result)
            if (
                isinstance(message, Message)
                and (
                    message.role.value
                    if isinstance(message.role, Role)
                    else str(message.role)
                ) == "system"
            )
            or (
                isinstance(message, Mapping)
                and str(message.get("role", "")) == "system"
            )
        ]
        if system_instruction:
            system_message = Message(role="system", content=system_instruction)
            if system_indexes:
                result[system_indexes[0]] = system_message
                for index in reversed(system_indexes[1:]):
                    del result[index]
            else:
                result.insert(0, system_message)
        elif len(system_indexes) > 1:
            for index in reversed(system_indexes[1:]):
                del result[index]
        return result

    def health_summary(self) -> dict[str, Any]:
        """Diagnostic summary of provider health and circuit states."""
        return {
            provider: self.router.health.summary(provider)
            for provider in self.router.providers
        }

    def model_catalog(self) -> list[dict[str, Any]]:
        """List configured model profiles."""
        return [
            {
                "model_id": p.model_id,
                "provider": p.provider,
                "tier": p.tier.value,
                "context_window": p.context_window,
                "capabilities": list(p.capabilities),
                "quality_score": p.quality_score,
                "latency_ms": p.latency_ms,
            }
            for p in self.router.registry.all()
        ]
