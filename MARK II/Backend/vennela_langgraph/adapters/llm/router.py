from time import perf_counter
from typing import Dict
from .contracts import LLMRequest, LLMResponse
from .providers import LLMProvider, DeterministicMockProvider
from .config import LLMConfig
from .real_provider import OpenAICompatibleProvider
from .real_provider import LLMProviderError


class LLMRouter:
    """Lab-local logical-task router; it never classifies user intent."""

    def __init__(self, providers: Dict[str, LLMProvider] | None = None,
                 default_provider: str = "mock"):
        self.providers = providers or {"mock": DeterministicMockProvider()}
        self.default_provider = default_provider
        self.history: list[LLMResponse] = []
        self.telemetry_events: list[dict] = []

    @classmethod
    def from_environment(cls, mode_override: str | None = None) -> "LLMRouter":
        config = LLMConfig.from_environment()
        if mode_override:
            config = LLMConfig(
                mode=mode_override.upper(), provider=config.provider, model=config.model,
                api_key=config.api_key, base_url=config.base_url,
                timeout_seconds=config.timeout_seconds, max_retries=config.max_retries,
            )
        if config.mode == "REAL":
            config.validate_real_mode()
            return cls({config.provider: OpenAICompatibleProvider(config)}, config.provider)
        return cls({"mock": DeterministicMockProvider()}, "mock")

    def generate(self, request: LLMRequest, provider: str | None = None) -> LLMResponse:
        selected = self.providers.get(provider or self.default_provider)
        if selected is None:
            raise ValueError(f"Unknown LLM provider: {provider or self.default_provider}")
        started = perf_counter()
        try:
            response = selected.generate(request)
        except LLMProviderError as error:
            self.telemetry_events.append({
                "request_id": request.request_id, "task": request.task,
                "provider": getattr(selected, "provider", "unknown"),
                "model": getattr(selected, "model", "unknown"),
                "latency_ms": round((perf_counter() - started) * 1000, 3),
                "success": False, "failure_category": error.category.value,
                "retry_count": request.retry_count,
            })
            raise
        response.metadata.latency_ms = round((perf_counter() - started) * 1000, 3)
        self.history.append(response)
        self.telemetry_events.append({
            "request_id": request.request_id, "task": request.task,
            "provider": response.metadata.provider, "model": response.metadata.model,
            "latency_ms": response.metadata.latency_ms,
            "success": response.metadata.success,
            "failure_category": response.metadata.failure_category,
            "retry_count": request.retry_count,
            "input_tokens": response.usage.input_tokens if response.usage else None,
            "output_tokens": response.usage.output_tokens if response.usage else None,
            "total_tokens": response.usage.total_tokens if response.usage else None,
        })
        return response
