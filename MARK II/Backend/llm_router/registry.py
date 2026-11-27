"""Model registry with capability profiles and tiered collections."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import os
from typing import TYPE_CHECKING, Iterable, Sequence

from .contracts import TaskType

if TYPE_CHECKING:
    from .config import RouterConfig


class ModelTier(str, Enum):
    FAST = "fast"
    REASONING = "reasoning"
    CODING = "coding"
    EMERGENCY = "emergency"
    GENERAL = "general"


@dataclass(frozen=True)
class ModelProfile:
    model_id: str
    provider: str
    tier: ModelTier = ModelTier.GENERAL
    context_window: int = 128_000
    capabilities: frozenset[str] = field(default_factory=frozenset)
    quality_score: float = 0.8
    reasoning_strength: float = 0.5
    coding_strength: float = 0.5
    conversation_strength: float = 0.8
    latency_ms: float = 500.0
    input_cost_per_million: float = 0.1
    output_cost_per_million: float = 0.3
    tool_calling: bool = False
    vision: bool = False
    enabled: bool = True
    display_name: str = ""

    def supports(self, requirements: Iterable[str], estimated_tokens: int = 0) -> bool:
        if not self.enabled or estimated_tokens > self.context_window:
            return False
        reqs = set(requirements)
        caps = set(self.capabilities)
        aliases = {
            "tools": self.tool_calling,
            "tool_calling": self.tool_calling,
            "vision": self.vision or ("vision" in caps),
            "coding": self.coding_strength >= 0.7 or ("coding" in caps),
            "reasoning": self.reasoning_strength >= 0.7 or ("reasoning" in caps),
            "fast": self.latency_ms <= 400 or ("fast" in caps),
        }
        return all(r in caps or aliases.get(r, False) for r in reqs)


class ModelRegistry:
    """Registry maintaining available models and capability matching."""

    def __init__(self, profiles: Iterable[ModelProfile] = ()) -> None:
        self._profiles: dict[str, ModelProfile] = {p.model_id: p for p in profiles}

    def register(self, profile: ModelProfile) -> None:
        self._profiles[profile.model_id] = profile

    def remove(self, model_id: str) -> None:
        self._profiles.pop(model_id, None)

    def get(self, model_id: str) -> ModelProfile:
        if model_id not in self._profiles:
            raise KeyError(f"Model '{model_id}' is not registered")
        return self._profiles[model_id]

    def all(self) -> list[ModelProfile]:
        return list(self._profiles.values())

    def by_provider(self, provider: str) -> list[ModelProfile]:
        return [p for p in self._profiles.values() if p.provider == provider and p.enabled]

    def by_tier(self, tier: ModelTier | str) -> list[ModelProfile]:
        tier_val = tier.value if isinstance(tier, ModelTier) else tier
        return [p for p in self._profiles.values() if p.tier.value == tier_val and p.enabled]

    def candidates(
        self,
        requirements: Iterable[str] = (),
        estimated_tokens: int = 0,
        provider: str | None = None,
    ) -> list[ModelProfile]:
        return [
            p
            for p in self._profiles.values()
            if (provider is None or p.provider == provider)
            and p.supports(requirements, estimated_tokens)
        ]


def _register_override_profile(
    registry: ModelRegistry,
    model_id: str,
    provider: str,
    default_latency_ms: float,
) -> None:
    """Register or promote an env-configured primary model override for a provider."""
    clean_id = model_id.strip()
    if not clean_id:
        return
    try:
        existing = registry.get(clean_id)
    except KeyError:
        existing = None

    all_caps = frozenset({"chat", "json", "coding", "reasoning", "conversation", "fast"})
    if existing is not None and existing.provider == provider:
        registry.register(
            ModelProfile(
                model_id=existing.model_id,
                provider=provider,
                tier=existing.tier,
                context_window=existing.context_window,
                capabilities=existing.capabilities | all_caps,
                quality_score=max(existing.quality_score, 0.96),
                reasoning_strength=max(existing.reasoning_strength, 0.95),
                coding_strength=max(existing.coding_strength, 0.92),
                conversation_strength=max(existing.conversation_strength, 0.96),
                latency_ms=min(existing.latency_ms, default_latency_ms),
                input_cost_per_million=existing.input_cost_per_million,
                output_cost_per_million=existing.output_cost_per_million,
                tool_calling=existing.tool_calling,
                vision=existing.vision,
                enabled=True,
                display_name=existing.display_name or f"{clean_id} ({provider})",
            )
        )
        return

    registry.register(
        ModelProfile(
            model_id=clean_id,
            provider=provider,
            tier=ModelTier.FAST,
            context_window=128_000,
            capabilities=all_caps,
            quality_score=0.96,
            reasoning_strength=0.95,
            coding_strength=0.92,
            conversation_strength=0.96,
            latency_ms=default_latency_ms,
            tool_calling=True,
            display_name=f"{clean_id} ({provider} override)",
        )
    )


def default_model_registry(config: "RouterConfig | None" = None) -> ModelRegistry:
    """Standard model profiles including OpenRouter tiers, Groq models, and env overrides."""
    registry = ModelRegistry(
        [
            # OpenRouter: Fast Model (Default)
            ModelProfile(
                model_id="google/gemini-2.5-flash-lite",
                provider="openrouter",
                tier=ModelTier.FAST,
                context_window=1_000_000,
                capabilities=frozenset({"chat", "json", "vision", "long_context", "conversation", "fast"}),
                quality_score=0.85,
                conversation_strength=0.90,
                reasoning_strength=0.72,
                coding_strength=0.68,
                latency_ms=350.0,
                input_cost_per_million=0.075,
                output_cost_per_million=0.30,
                tool_calling=True,
                vision=True,
                display_name="Gemini 2.5 Flash Lite (OpenRouter)",
            ),
            # OpenRouter: Coding Model
            ModelProfile(
                model_id="qwen/qwen-2.5-coder-32b-instruct",
                provider="openrouter",
                tier=ModelTier.CODING,
                context_window=131_072,
                capabilities=frozenset({"chat", "json", "coding", "tool_calling"}),
                quality_score=0.88,
                coding_strength=0.95,
                reasoning_strength=0.80,
                conversation_strength=0.70,
                latency_ms=650.0,
                input_cost_per_million=0.05,
                output_cost_per_million=0.08,
                tool_calling=True,
                display_name="Qwen 2.5 Coder 32B (OpenRouter)",
            ),
            # OpenRouter: Deep Reasoning Model
            ModelProfile(
                model_id="deepseek/deepseek-r1-0528",
                provider="openrouter",
                tier=ModelTier.REASONING,
                context_window=128_000,
                capabilities=frozenset({"chat", "json", "reasoning", "coding"}),
                quality_score=0.95,
                reasoning_strength=0.98,
                coding_strength=0.85,
                conversation_strength=0.75,
                latency_ms=1600.0,
                input_cost_per_million=0.55,
                output_cost_per_million=2.19,
                display_name="DeepSeek R1 0528 (OpenRouter)",
            ),
            # OpenRouter: Emergency Model (Lightweight / highly available fallback)
            ModelProfile(
                model_id="meta-llama/llama-3.1-8b-instruct",
                provider="openrouter",
                tier=ModelTier.EMERGENCY,
                context_window=128_000,
                capabilities=frozenset({"chat", "json", "fast"}),
                quality_score=0.75,
                conversation_strength=0.80,
                reasoning_strength=0.65,
                coding_strength=0.60,
                latency_ms=250.0,
                input_cost_per_million=0.02,
                output_cost_per_million=0.05,
                display_name="Llama 3.1 8B (OpenRouter)",
            ),
            # Groq: Production High-Capacity Reasoning & Coding (Primary Failover)
            ModelProfile(
                model_id="llama-3.3-70b-versatile",
                provider="groq",
                tier=ModelTier.REASONING,
                context_window=131_072,
                capabilities=frozenset({"chat", "json", "coding", "reasoning", "conversation"}),
                quality_score=0.92,
                coding_strength=0.90,
                reasoning_strength=0.92,
                conversation_strength=0.88,
                latency_ms=280.0,
                input_cost_per_million=0.59,
                output_cost_per_million=0.79,
                tool_calling=True,
                display_name="Llama 3.3 70B Versatile (Groq)",
            ),
            # Groq: Ultra-Low-Latency Fast Model (Secondary Failover)
            ModelProfile(
                model_id="llama-3.1-8b-instant",
                provider="groq",
                tier=ModelTier.FAST,
                context_window=131_072,
                capabilities=frozenset({"chat", "json", "fast", "conversation"}),
                quality_score=0.82,
                conversation_strength=0.85,
                coding_strength=0.75,
                reasoning_strength=0.72,
                latency_ms=120.0,
                input_cost_per_million=0.05,
                output_cost_per_million=0.08,
                tool_calling=True,
                display_name="Llama 3.1 8B Instant (Groq)",
            ),
        ]
    )

    openrouter_override = (
        (config.openrouter_model if config else None)
        or (os.getenv("OPENROUTER_MODEL") or "").strip()
        or None
    )
    groq_override = (
        (config.groq_model if config else None)
        or (os.getenv("GROQ_MODEL") or "").strip()
        or None
    )

    if openrouter_override:
        _register_override_profile(registry, openrouter_override, "openrouter", 220.0)
    if groq_override:
        _register_override_profile(registry, groq_override, "groq", 110.0)

    return registry
