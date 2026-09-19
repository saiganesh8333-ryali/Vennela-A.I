"""Model registry with capability profiles and tiered collections."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Sequence

from .contracts import TaskType


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


def default_model_registry() -> ModelRegistry:
    """Standard model profiles including OpenRouter tiers and Groq models."""
    return ModelRegistry(
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
                model_id="deepseek/deepseek-r1",
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
                display_name="DeepSeek R1 (OpenRouter)",
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
            # Groq: Ultra-Low-Latency Fast Model
            ModelProfile(
                model_id="openai/gpt-oss-20b",
                provider="groq",
                tier=ModelTier.FAST,
                context_window=131_072,
                capabilities=frozenset({"chat", "json", "fast", "coding"}),
                quality_score=0.80,
                conversation_strength=0.82,
                coding_strength=0.78,
                reasoning_strength=0.70,
                latency_ms=150.0,
                input_cost_per_million=0.05,
                output_cost_per_million=0.08,
                display_name="GPT OSS 20B (Groq)",
            ),
            # Groq: Reasoning & Coding
            ModelProfile(
                model_id="qwen/qwen3.6-27b",
                provider="groq",
                tier=ModelTier.CODING,
                context_window=131_072,
                capabilities=frozenset({"chat", "json", "fast", "coding", "reasoning"}),
                quality_score=0.85,
                coding_strength=0.88,
                reasoning_strength=0.82,
                conversation_strength=0.78,
                latency_ms=220.0,
                input_cost_per_million=0.10,
                output_cost_per_million=0.15,
                display_name="Qwen 3.6 27B (Groq)",
            ),
        ]
    )
