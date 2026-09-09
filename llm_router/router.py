"""Core LLM Router implementation with in-memory deterministic routing and fallback."""

from __future__ import annotations

import re
import threading
from typing import Any, Iterator, Sequence

from .config import RouterConfig
from .contracts import (
    Failure,
    FailureKind,
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    RoutingError,
    TaskType,
)
from .fallback import FallbackEngine
from .health import HealthRegistry
from .performance import LatencyTracker
from .providers.base import BaseLLMProvider
from .registry import ModelProfile, ModelRegistry, ModelTier, default_model_registry


class LLMRouter:
    """Independent, provider-agnostic router orchestrating selection and fallback."""

    def __init__(
        self,
        providers: dict[str, BaseLLMProvider],
        registry: ModelRegistry | None = None,
        config: RouterConfig | None = None,
        health: HealthRegistry | None = None,
    ) -> None:
        self.providers = providers
        self.registry = registry or default_model_registry()
        self.config = config or RouterConfig.from_env()
        self.health = health or HealthRegistry()
        self.fallback = FallbackEngine(
            providers=self.providers,
            health=self.health,
            max_retries=self.config.max_retries,
            retry_delay_seconds=self.config.retry_delay_seconds,
        )
        self._lock = threading.Lock()

    def infer_task_type(self, request: LLMRequest) -> TaskType:
        """Deterministically infer task type from request contents in-memory."""
        if request.task_type is not None:
            if isinstance(request.task_type, TaskType):
                return request.task_type
            try:
                return TaskType(str(request.task_type).upper())
            except ValueError:
                pass

        prompt = request.get_prompt_text().strip()
        lower = prompt.lower()
        words = re.findall(r"\S+", lower)

        if "vision" in request.requirements or any(w in lower for w in ("image", "photo", "screenshot", "vision")):
            return TaskType.MULTIMODAL

        coding_keywords = ("code", "function", "class ", "def ", "bug", "python", "javascript", "typescript", "refactor", "sql", "api", "git")
        if "coding" in request.requirements or any(k in lower for k in coding_keywords):
            return TaskType.CODING

        reasoning_keywords = ("prove", "derive", "step by step", "deep reasoning", "theorem", "math", "deduce", "trade-off", "architecture")
        if "reasoning" in request.requirements or any(k in lower for k in reasoning_keywords):
            return TaskType.DEEP_REASONING

        if len(words) > 4000 or "long_context" in request.requirements:
            return TaskType.LONG_CONTEXT

        if (
            len(words) <= 8
            and not any(k in lower for k in coding_keywords)
            and not any(k in lower for k in reasoning_keywords)
            and (
                bool(re.fullmatch(r"[\d\s+\-*/().=]+", prompt))
                or any(k in lower for k in ("calculate", "what is", "2 + 2", "time is it", "ping"))
            )
        ):
            return TaskType.TINY_TASK

        if any(k in lower for k in ("hello", "hi ", "hey", "how are you", "good morning", "chat", "assist")):
            return TaskType.CONVERSATION

        return TaskType.GENERAL_REASONING

    def score_model(self, profile: ModelProfile, task_type: TaskType, request: LLMRequest) -> float:
        """Deterministic in-memory model scoring."""
        score = profile.quality_score * 0.3

        if task_type == TaskType.CODING:
            score += profile.coding_strength * 0.6
        elif task_type == TaskType.DEEP_REASONING:
            score += profile.reasoning_strength * 0.6
        elif task_type in {TaskType.CONVERSATION, TaskType.TINY_TASK}:
            score += profile.conversation_strength * 0.4
        else:
            score += profile.quality_score * 0.3

        # Latency weighting
        if request.latency_sensitive or task_type == TaskType.TINY_TASK:
            latency_factor = max(0.0, 1.0 - (profile.latency_ms / 2000.0))
            score += latency_factor * 0.7
        else:
            latency_factor = max(0.0, 1.0 - (profile.latency_ms / 3000.0))
            score += latency_factor * 0.15

        # Strong preference for default model on normal conversational & general tasks
        if (
            profile.model_id == self.config.default_model_id
            and not request.latency_sensitive
            and task_type not in {TaskType.DEEP_REASONING, TaskType.CODING}
        ):
            score += 0.45

        # Provider health consideration (read-only probe=False)
        if not self.health.is_available(profile.provider, profile.model_id, probe=False):
            score -= 100.0

        return score

    def build_candidate_chain(self, request: LLMRequest, task_type: TaskType) -> list[tuple[str, str]]:
        """Construct deterministic candidate chain: PRIMARY -> ALT_MODEL -> ALT_PROVIDER -> EMERGENCY."""
        estimated_tokens = max(1, int(len(request.get_prompt_text().split()) * 1.3) + 4)
        all_candidates = self.registry.candidates(request.requirements, estimated_tokens)

        if not all_candidates:
            raise RoutingError(
                Failure(
                    FailureKind.INVALID_REQUEST,
                    f"No registered model satisfies requirements: {list(request.requirements)}",
                    retryable=False,
                )
            )

        ranked = sorted(
            all_candidates,
            key=lambda p: (-self.score_model(p, task_type, request), p.latency_ms),
        )

        candidates: list[tuple[str, str]] = []
        primary = ranked[0]
        candidates.append((primary.model_id, primary.provider))

        # 1. Alternate model on primary provider (if available and capable)
        for p in ranked[1:]:
            if p.provider == primary.provider and (p.model_id, p.provider) not in candidates:
                candidates.append((p.model_id, p.provider))
                break

        # 2. Alternate provider
        for p in ranked[1:]:
            if p.provider != primary.provider and (p.model_id, p.provider) not in candidates:
                candidates.append((p.model_id, p.provider))
                break

        # 3. Emergency fallback
        emergency_profiles = self.registry.by_tier(ModelTier.EMERGENCY)
        if emergency_profiles:
            em = emergency_profiles[0]
            if (em.model_id, em.provider) not in candidates:
                candidates.append((em.model_id, em.provider))
        elif (self.config.emergency_model_id, "openrouter") not in candidates:
            candidates.append((self.config.emergency_model_id, "openrouter"))

        return candidates

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Standard non-streaming generation."""
        tracker = LatencyTracker()
        tracker.start_decision()

        task_type = self.infer_task_type(request)
        candidates = self.build_candidate_chain(request, task_type)

        tracker.end_decision()

        resp, _ = self.fallback.execute_completion(request, candidates, tracker)
        metrics = tracker.complete()

        meta = dict(resp.metadata)
        meta["latency_metrics"] = metrics.to_dict()
        meta["task_type"] = task_type.value

        return LLMResponse(
            text=resp.text,
            model_id=resp.model_id,
            provider=resp.provider,
            latency_ms=resp.latency_ms,
            ttft_ms=resp.ttft_ms,
            usage=resp.usage,
            attempts=resp.attempts,
            metadata=meta,
            raw=resp.raw,
        )

    def stream(self, request: LLMRequest) -> Iterator[LLMStreamChunk]:
        """Streaming generation yielding LLMStreamChunk tokens."""
        tracker = LatencyTracker()
        tracker.start_decision()

        task_type = self.infer_task_type(request)
        candidates = self.build_candidate_chain(request, task_type)

        tracker.end_decision()

        return self.fallback.execute_stream(request, candidates, tracker)
