"""Provider-agnostic reasoning boundary backed by the active LLM adapter."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from conversation.response_policy import ConversationAdjuster
from llm_router.adapter import VennelaLLMAdapter


class ReasoningLayer(Protocol):
    """Minimum Brain-facing contract for model-backed responses."""

    def respond(
        self,
        task: str,
        *,
        messages: Sequence[Mapping[str, str]] | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> "ReasoningResponse":
        ...


class ReasoningResponse:
    """Provider-neutral model response and routing metadata."""

    def __init__(
        self,
        text: str,
        *,
        model_id: str,
        provider: str,
        latency_ms: float = 0.0,
        fallback_used: bool = False,
        attempts: Sequence[Mapping[str, Any]] = (),
        usage: Mapping[str, Any] | None = None,
    ) -> None:
        self.text = text
        self.model_id = model_id
        self.provider = provider
        self.latency_ms = latency_ms
        self.fallback_used = fallback_used
        self.attempts = tuple(dict(attempt) for attempt in attempts)
        self.usage = dict(usage or {})


class VennelaReasoningAdapter:
    """Adapts the active VennelaLLMAdapter without exposing providers to Brain."""

    def __init__(
        self,
        adapter: VennelaLLMAdapter | None = None,
        *,
        adjuster: ConversationAdjuster | None = None,
    ) -> None:
        self.adapter = adapter or VennelaLLMAdapter()
        self.adjuster = adjuster or ConversationAdjuster()

    def respond(
        self,
        task: str,
        *,
        messages: Sequence[Mapping[str, str]] | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> ReasoningResponse:
        user_system_instruction = None
        reasoning_context = context
        request_id = None
        if context:
            candidate = context.get("_system_instruction")
            if isinstance(candidate, str) and candidate.strip():
                user_system_instruction = candidate
            request_id = context.get("_request_id")
            reasoning_context = {
                key: value
                for key, value in context.items()
                if key not in {"_system_instruction", "_request_id"}
            }

        policy = self.adjuster.adjust(
            task,
            user_system_instruction=user_system_instruction,
        )
        system_instruction = policy.system_instruction
        if reasoning_context:
            system_instruction = (
                f"{system_instruction}\nRelevant context:\n{self._format_context(reasoning_context)}"
            )
        raw = self.adapter.route_text(
            task,
            system_instruction=system_instruction,
            messages=messages,
            latency_sensitive=policy.latency_sensitive,
            max_tokens=policy.max_tokens,
            task_hint=policy.task_hint,
            request_id=request_id,
        )
        return ReasoningResponse(
            raw["text"],
            model_id=raw["model_id"],
            provider=raw["provider"],
            latency_ms=raw["latency_ms"],
            fallback_used=raw["fallback_used"],
            attempts=raw["attempts"],
            usage=raw["usage"],
        )

    @staticmethod
    def _format_context(context: Mapping[str, Any]) -> str:
        return "\n".join(f"- {key}: {value}" for key, value in context.items())


__all__ = ["ReasoningLayer", "ReasoningResponse", "VennelaReasoningAdapter"]
