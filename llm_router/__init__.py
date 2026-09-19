"""LLM Router - Isolated, Provider-Agnostic Intelligent Routing Engine."""

from .adapter import VennelaLLMAdapter
from .benchmark import run_benchmark_suite
from .circuit_breaker import CircuitBreaker, CircuitState
from .config import CircuitBreakerConfig, ProviderConfig, RouterConfig
from .contracts import (
    Attempt,
    Failure,
    FailureKind,
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    Message,
    Role,
    RoutingError,
    TaskType,
)
from .fallback import FallbackEngine
from .gateway import Gateway
from .health import HealthRegistry, HealthStats
from .performance import LatencyMetrics, LatencyTracker
from .providers.base import BaseLLMProvider, classify_http_error, validate_response
from .providers.groq import GroqProvider
from .providers.mock import MockMode, MockProvider
from .providers.openrouter import OpenRouterProvider
from .registry import ModelProfile, ModelRegistry, ModelTier, default_model_registry
from .router import LLMRouter

__all__ = [
    "Attempt",
    "BaseLLMProvider",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitState",
    "Failure",
    "FailureKind",
    "FallbackEngine",
    "Gateway",
    "GroqProvider",
    "HealthRegistry",
    "HealthStats",
    "LLMRequest",
    "LLMResponse",
    "LLMRouter",
    "LLMStreamChunk",
    "LatencyMetrics",
    "LatencyTracker",
    "Message",
    "MockMode",
    "MockProvider",
    "ModelProfile",
    "ModelRegistry",
    "ModelTier",
    "OpenRouterProvider",
    "ProviderConfig",
    "Role",
    "RouterConfig",
    "RoutingError",
    "TaskType",
    "VennelaLLMAdapter",
    "classify_http_error",
    "default_model_registry",
    "run_benchmark_suite",
    "validate_response",
]
