"""Unified LLM Provider Manager - Abstract interface for all providers."""

import logging
import os
import time
from typing import Dict, Optional, List, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """Supported LLM providers."""
    GEMINI_FLASH_LITE = "gemini_flash_lite"
    GEMINI_FLASH = "gemini_flash"
    GEMINI_REASONING = "gemini_reasoning"
    GEMINI_LIVE = "gemini_live"
    GROQ = "groq"
    OPENROUTER = "openrouter"


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider."""
    provider_type: ProviderType
    api_key: str
    model_name: str
    base_url: Optional[str] = None
    timeout: int = 30
    max_tokens: int = 500
    temperature: float = 0.7
    enabled: bool = True


@dataclass
class ProviderResponse:
    """Unified response from any provider."""
    provider: str
    model: str
    response: str
    tokens_used: int
    latency_ms: int
    cost: float
    timestamp: float
    error: Optional[str] = None
    success: bool = True


class ProviderHealth:
    """Track provider health and availability."""
    
    def __init__(self):
        """Initialize health tracking."""
        self.health_status = {}
        self.error_counts = {}
        self.last_error_time = {}
        self.availability_score = {}
    
    def update_success(self, provider: str) -> None:
        """Record successful call."""
        if provider not in self.error_counts:
            self.error_counts[provider] = 0
        self.error_counts[provider] = max(0, self.error_counts[provider] - 1)
        self.health_status[provider] = "healthy"
        self.availability_score[provider] = min(
            self.availability_score.get(provider, 1.0) + 0.05,
            1.0
        )
    
    def update_error(self, provider: str) -> None:
        """Record failed call."""
        if provider not in self.error_counts:
            self.error_counts[provider] = 0
        self.error_counts[provider] += 1
        self.last_error_time[provider] = time.time()
        
        error_count = self.error_counts[provider]
        if error_count > 5:
            self.health_status[provider] = "unhealthy"
        elif error_count > 2:
            self.health_status[provider] = "degraded"
        else:
            self.health_status[provider] = "healthy"
        
        self.availability_score[provider] = max(
            self.availability_score.get(provider, 1.0) - 0.1,
            0.0
        )
    
    def is_available(self, provider: str) -> bool:
        """Check if provider is available."""
        status = self.health_status.get(provider, "unknown")
        return status != "unhealthy"
    
    def get_score(self, provider: str) -> float:
        """Get availability score."""
        return self.availability_score.get(provider, 0.8)


class UnifiedProviderManager:
    """Unified interface for all LLM providers."""
    
    def __init__(self):
        """Initialize provider manager."""
        logger.info("Initializing Unified Provider Manager")
        self.providers: Dict[str, ProviderConfig] = {}
        self.health = ProviderHealth()
        self.response_history: List[ProviderResponse] = []
        self.max_history = 1000
        self._initialize_providers()
    
    def _initialize_providers(self) -> None:
        """Initialize all available providers."""
        from dotenv import load_dotenv
        load_dotenv()
        
        # Gemini providers
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            self.register_provider(ProviderConfig(
                provider_type=ProviderType.GEMINI_FLASH_LITE,
                api_key=gemini_key,
                model_name=os.getenv(
                    "GEMINI_FLASH_LITE_MODEL",
                    "gemini-3.5-flash"
                ),
                timeout=15,
                max_tokens=500
            ))
            self.register_provider(ProviderConfig(
                provider_type=ProviderType.GEMINI_FLASH,
                api_key=gemini_key,
                model_name=os.getenv(
                    "GEMINI_FLASH_MODEL",
                    "gemini-2.0-flash-exp"
                ),
                timeout=30,
                max_tokens=1000
            ))
            self.register_provider(ProviderConfig(
                provider_type=ProviderType.GEMINI_REASONING,
                api_key=gemini_key,
                model_name=os.getenv(
                    "GEMINI_REASONING_MODEL",
                    "gemini-2.0-flash-thinking-exp-01-21"
                ),
                timeout=60,
                max_tokens=2000
            ))
        else:
            logger.warning("⚠️ GEMINI_API_KEY not found")
        
        # Groq provider
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            self.register_provider(ProviderConfig(
                provider_type=ProviderType.GROQ,
                api_key=groq_key,
                model_name=os.getenv(
                    "GROQ_MODEL",
                    "llama-3.3-70b-versatile"
                ),
                base_url="https://api.groq.com/openai/v1",
                timeout=30,
                max_tokens=500
            ))
        
        # OpenRouter provider
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        if openrouter_key:
            self.register_provider(ProviderConfig(
                provider_type=ProviderType.OPENROUTER,
                api_key=openrouter_key,
                model_name=os.getenv(
                    "OPENROUTER_MODEL",
                    "openai/gpt-4o-mini"
                ),
                base_url="https://openrouter.ai/api/v1",
                timeout=30,
                max_tokens=500
            ))
        
        logger.info(
            f"✓ Registered {len(self.providers)} providers"
        )
    
    def register_provider(
        self,
        config: ProviderConfig
    ) -> None:
        """Register a new provider."""
        if not config.enabled:
            logger.debug(f"Provider disabled: {config.provider_type.value}")
            return
        
        self.providers[config.provider_type.value] = config
        self.health.health_status[config.provider_type.value] = "healthy"
        self.health.availability_score[config.provider_type.value] = 1.0
        
        logger.debug(f"✓ Registered provider: {config.provider_type.value}")
    
    def get_provider(
        self,
        provider_type: ProviderType
    ) -> Optional[ProviderConfig]:
        """Get provider config by type."""
        return self.providers.get(provider_type.value)
    
    def list_providers(self) -> List[str]:
        """List all registered providers."""
        return list(self.providers.keys())
    
    def is_provider_available(
        self,
        provider_type: ProviderType
    ) -> bool:
        """Check if provider is available."""
        provider_key = provider_type.value
        return (
            provider_key in self.providers
            and self.health.is_available(provider_key)
        )
    
    def get_available_providers(self) -> List[str]:
        """Get list of available providers."""
        return [
            p for p in self.providers.keys()
            if self.health.is_available(p)
        ]
    
    def record_success(
        self,
        provider: str,
        response: ProviderResponse
    ) -> None:
        """Record successful response."""
        self.health.update_success(provider)
        self._add_to_history(response)
    
    def record_error(
        self,
        provider: str,
        error: str
    ) -> None:
        """Record error."""
        self.health.update_error(provider)
        logger.warning(f"Provider error ({provider}): {error}")
    
    def _add_to_history(self, response: ProviderResponse) -> None:
        """Add response to history."""
        self.response_history.append(response)
        if len(self.response_history) > self.max_history:
            self.response_history = self.response_history[-self.max_history:]
    
    def get_provider_stats(self) -> Dict[str, Any]:
        """Get statistics for all providers."""
        stats = {}
        for provider_key in self.providers.keys():
            responses = [r for r in self.response_history if r.provider == provider_key]
            successful = [r for r in responses if r.success]
            
            stats[provider_key] = {
                "status": self.health.health_status.get(provider_key, "unknown"),
                "availability": self.health.get_score(provider_key),
                "total_calls": len(responses),
                "successful_calls": len(successful),
                "error_count": self.health.error_counts.get(provider_key, 0),
                "avg_latency_ms": (
                    sum(r.latency_ms for r in successful) / len(successful)
                    if successful else 0
                ),
                "total_tokens": sum(r.tokens_used for r in responses),
                "total_cost": sum(r.cost for r in responses)
            }
        
        return stats
    
    def get_best_provider(
        self,
        for_reasoning: bool = False,
        for_speed: bool = False
    ) -> Optional[ProviderType]:
        """Get best provider for current conditions."""
        available = self.get_available_providers()
        
        if not available:
            return None
        
        if for_reasoning:
            # Prefer reasoning model
            if ProviderType.GEMINI_REASONING.value in available:
                return ProviderType.GEMINI_REASONING
            if ProviderType.GEMINI_FLASH.value in available:
                return ProviderType.GEMINI_FLASH
        
        if for_speed:
            # Prefer fastest models
            if ProviderType.GEMINI_FLASH_LITE.value in available:
                return ProviderType.GEMINI_FLASH_LITE
            if ProviderType.GROQ.value in available:
                return ProviderType.GROQ
        
        # Default: pick by availability score
        best_provider = max(
            available,
            key=lambda p: self.health.get_score(p)
        )
        
        return ProviderType(best_provider)
    
    def get_provider_health_summary(self) -> Dict[str, Any]:
        """Get health summary for all providers."""
        return {
            "timestamp": time.time(),
            "providers_online": len(self.get_available_providers()),
            "providers_total": len(self.providers),
            "health_status": self.health.health_status,
            "availability_scores": self.health.availability_score,
            "stats": self.get_provider_stats()
        }


# Singleton instance
_manager_instance = None


def get_provider_manager() -> UnifiedProviderManager:
    """Get or create provider manager singleton."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = UnifiedProviderManager()
    return _manager_instance
