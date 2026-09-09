"""Thin integration adapter connecting Vennela backend to standalone LLM Router."""

from __future__ import annotations

from typing import Any, Iterator, Mapping, Sequence

from .contracts import (
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    Message,
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
        latency_sensitive: bool = False,
        structured_output: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        task_hint: str | None = None,
    ) -> dict[str, Any]:
        """Simple text generation for Vennela backend callers."""
        messages: list[Message] = []
        if system_instruction:
            messages.append(Message(role="system", content=system_instruction))
        messages.append(Message(role="user", content=prompt))

        req = LLMRequest(
            prompt=prompt,
            messages=messages,
            task_type=task_hint,
            latency_sensitive=latency_sensitive,
            structured_output=structured_output,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        response = self.router.generate(req)
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
        latency_sensitive: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        """Streaming text token generator for Vennela UI / agents."""
        messages: list[Message] = []
        if system_instruction:
            messages.append(Message(role="system", content=system_instruction))
        messages.append(Message(role="user", content=prompt))

        req = LLMRequest(
            prompt=prompt,
            messages=messages,
            latency_sensitive=latency_sensitive,
            streaming=True,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        for chunk in self.router.stream(req):
            if chunk.delta:
                yield chunk.delta

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
