"""Public Gateway facade for the LLM Router subsystem."""

from __future__ import annotations

from typing import Any, Iterator, Mapping, Sequence

from .config import RouterConfig
from .contracts import (
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    Message,
    TaskType,
)
from .health import HealthRegistry
from .providers.base import BaseLLMProvider
from .providers.groq import GroqProvider
from .providers.mock import MockProvider
from .providers.openrouter import OpenRouterProvider
from .registry import ModelRegistry, default_model_registry
from .router import LLMRouter


class Gateway:
    """High-level facade providing simplified entry points to LLM Router."""

    def __init__(self, router: LLMRouter) -> None:
        self.router = router

    @classmethod
    def create(
        cls,
        mock: bool = False,
        config: RouterConfig | None = None,
        custom_providers: dict[str, BaseLLMProvider] | None = None,
        registry: ModelRegistry | None = None,
    ) -> "Gateway":
        cfg = config or RouterConfig.from_env()
        health = HealthRegistry()
        reg = registry or default_model_registry()

        if custom_providers is not None:
            providers = custom_providers
        elif mock:
            providers = {
                "openrouter": MockProvider("openrouter", "Mock OpenRouter response"),
                "groq": MockProvider("groq", "Mock Groq response"),
            }
        else:
            providers = {
                "openrouter": OpenRouterProvider(cfg.openrouter_api_key, cfg.timeout_seconds),
                "groq": GroqProvider(cfg.groq_api_key, cfg.timeout_seconds),
            }

        router = LLMRouter(providers, registry=reg, config=cfg, health=health)
        return cls(router)

    def generate(
        self,
        prompt: str | None = None,
        *,
        messages: Sequence[Message | Mapping[str, str]] | None = None,
        task_type: TaskType | str | None = None,
        latency_sensitive: bool = False,
        structured_output: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        requirements: Sequence[str] = (),
    ) -> LLMResponse:
        req = LLMRequest(
            prompt=prompt,
            messages=messages,
            task_type=task_type,
            latency_sensitive=latency_sensitive,
            structured_output=structured_output,
            temperature=temperature,
            max_tokens=max_tokens,
            requirements=frozenset(requirements),
        )
        return self.router.generate(req)

    def stream(
        self,
        prompt: str | None = None,
        *,
        messages: Sequence[Message | Mapping[str, str]] | None = None,
        task_type: TaskType | str | None = None,
        latency_sensitive: bool = False,
        structured_output: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        requirements: Sequence[str] = (),
    ) -> Iterator[LLMStreamChunk]:
        req = LLMRequest(
            prompt=prompt,
            messages=messages,
            task_type=task_type,
            latency_sensitive=latency_sensitive,
            structured_output=structured_output,
            temperature=temperature,
            max_tokens=max_tokens,
            requirements=frozenset(requirements),
            streaming=True,
        )
        return self.router.stream(req)

    def health_summary(self) -> dict[str, Any]:
        return {
            provider: self.router.health.summary(provider)
            for provider in self.router.providers
        }

    def model_catalog(self) -> list[dict[str, Any]]:
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
