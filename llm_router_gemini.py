"""Multi-LLM Router with Gemini, Groq, and OpenRouter support."""

import logging
import os
import time
from typing import Dict, Optional, Any, List
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Import components
from llm_intent_classifier import get_classifier, IntentClassifier
from llm_provider_manager import (
    get_provider_manager,
    ProviderType,
    ProviderResponse,
    UnifiedProviderManager
)

load_dotenv()


class MultiLLMRouter:
    """Intelligent router that selects optimal LLM provider and model."""
    
    def __init__(self):
        """Initialize router."""
        logger.info("Initializing Multi-LLM Router")
        self.classifier = get_classifier()
        self.provider_manager = get_provider_manager()
        self.routing_history = []
        self.max_history = 500
        self._gemini_client = None
        self._initialize_gemini()
    
    def _initialize_gemini(self) -> None:
        """Initialize Gemini client."""
        try:
            import google.generativeai as genai
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
                self._gemini_client = genai
                logger.info("✓ Gemini client initialized")
            else:
                logger.warning("⚠️ GEMINI_API_KEY not set")
        except ImportError:
            logger.warning("⚠️ google-generativeai not installed")
        except Exception as e:
            logger.error(f"Gemini initialization error: {e}")
    
    def route_and_call(
        self,
        query: str,
        messages: Optional[List[Dict]] = None,
        conversation_length: int = 0,
        user_context: Optional[Dict] = None,
        force_provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Route query to best LLM provider and generate response.
        
        Args:
            query: User query
            messages: Chat history (OpenAI format)
            conversation_length: Number of messages in conversation
            user_context: User profile data
            force_provider: Force specific provider (bypass routing)
            
        Returns:
            Response with routing metadata
        """
        start_time = time.time()
        
        try:
            # Classify intent
            classification = self.classifier.classify_query(
                query,
                conversation_length,
                user_context
            )
            
            # Determine provider
            if force_provider:
                provider_type = ProviderType(force_provider)
            else:
                recommended = classification.get("recommended_provider")
                provider_type = self._resolve_provider_type(recommended)
            
            # Try primary provider
            result = self._call_provider(
                provider_type,
                query,
                messages,
                classification
            )
            
            if result["success"]:
                # Record routing decision
                self._record_routing(
                    query,
                    provider_type.value,
                    result,
                    classification,
                    time.time() - start_time
                )
                return result
            
            # Try alternatives on failure
            alternatives = classification.get("alternatives", [])
            for alt_provider_name in alternatives:
                alt_provider_type = self._resolve_provider_type(alt_provider_name)
                if alt_provider_type != provider_type:
                    logger.info(
                        f"⚡ Fallback: {provider_type.value} failed, "
                        f"trying {alt_provider_name}"
                    )
                    result = self._call_provider(
                        alt_provider_type,
                        query,
                        messages,
                        classification
                    )
                    if result["success"]:
                        self._record_routing(
                            query,
                            alt_provider_type.value,
                            result,
                            classification,
                            time.time() - start_time
                        )
                        return result
            
            # Ultimate fallback
            logger.warning("❌ All providers failed")
            return {
                "success": False,
                "error": "All LLM providers failed",
                "provider": "none",
                "response": "AI services temporarily unavailable",
                "latency_ms": int((time.time() - start_time) * 1000)
            }
            
        except Exception as e:
            logger.error(f"Routing error: {e}")
            return {
                "success": False,
                "error": str(e),
                "provider": "error",
                "response": "Routing error occurred",
                "latency_ms": int((time.time() - start_time) * 1000)
            }
    
    def _resolve_provider_type(self, provider_name: str) -> ProviderType:
        """Resolve provider name string to ProviderType enum."""
        mapping = {
            "flash_lite": ProviderType.GEMINI_FLASH_LITE,
            "flash": ProviderType.GEMINI_FLASH,
            "reasoning": ProviderType.GEMINI_REASONING,
            "live": ProviderType.GEMINI_LIVE,
            "groq": ProviderType.GROQ,
            "openrouter": ProviderType.OPENROUTER,
        }
        return mapping.get(provider_name, ProviderType.GEMINI_FLASH)
    
    def _call_provider(
        self,
        provider_type: ProviderType,
        query: str,
        messages: Optional[List[Dict]],
        classification: Dict
    ) -> Dict[str, Any]:
        """Call specific provider."""
        
        if not self.provider_manager.is_provider_available(provider_type):
            return {
                "success": False,
                "error": f"Provider {provider_type.value} unavailable",
                "provider": provider_type.value
            }
        
        try:
            # Route by provider type
            if provider_type == ProviderType.GEMINI_FLASH_LITE:
                return self._call_gemini(
                    provider_type,
                    query,
                    messages,
                    "gemini-3.5-flash"
                )
            elif provider_type == ProviderType.GEMINI_FLASH:
                return self._call_gemini(
                    provider_type,
                    query,
                    messages,
                    "gemini-2.0-flash-exp"
                )
            elif provider_type == ProviderType.GEMINI_REASONING:
                return self._call_gemini(
                    provider_type,
                    query,
                    messages,
                    "gemini-2.0-flash-thinking-exp-01-21"
                )
            elif provider_type == ProviderType.GROQ:
                return self._call_groq(query, messages)
            elif provider_type == ProviderType.OPENROUTER:
                return self._call_openrouter(query, messages)
            else:
                return {
                    "success": False,
                    "error": f"Unknown provider: {provider_type}",
                    "provider": provider_type.value
                }
            
        except Exception as e:
            logger.error(f"Provider error ({provider_type.value}): {e}")
            self.provider_manager.record_error(provider_type.value, str(e))
            return {
                "success": False,
                "error": str(e),
                "provider": provider_type.value
            }
    
    def _call_gemini(
        self,
        provider_type: ProviderType,
        query: str,
        messages: Optional[List[Dict]],
        model_name: str
    ) -> Dict[str, Any]:
        """Call Gemini API."""
        if not self._gemini_client:
            return {
                "success": False,
                "error": "Gemini client not initialized",
                "provider": provider_type.value
            }
        
        start = time.time()
        
        try:
            # Prepare conversation
            conversation = []
            if messages:
                for msg in messages[-5:]:  # Last 5 messages for context
                    conversation.append(msg)
            conversation.append({"role": "user", "content": query})
            
            # Call Gemini
            model = self._gemini_client.GenerativeModel(model_name)
            response = model.generate_content(
                [msg.get("content", "") for msg in conversation]
            )
            
            latency_ms = int((time.time() - start) * 1000)
            
            # Extract response
            ai_response = response.text if response else ""
            
            if not ai_response:
                return {
                    "success": False,
                    "error": "Empty response from Gemini",
                    "provider": provider_type.value
                }
            
            # Estimate tokens
            tokens_used = len(query.split()) * 1.3
            cost = self._estimate_cost(provider_type, int(tokens_used))
            
            result = {
                "success": True,
                "provider": provider_type.value,
                "model": model_name,
                "response": ai_response,
                "tokens_used": int(tokens_used),
                "cost": cost,
                "latency_ms": latency_ms
            }
            
            self.provider_manager.record_success(
                provider_type.value,
                ProviderResponse(
                    provider=provider_type.value,
                    model=model_name,
                    response=ai_response,
                    tokens_used=int(tokens_used),
                    latency_ms=latency_ms,
                    cost=cost,
                    timestamp=time.time()
                )
            )
            
            logger.info(
                f"✅ Gemini ({model_name}): {latency_ms}ms, "
                f"{int(tokens_used)} tokens"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Gemini call failed: {e}")
            self.provider_manager.record_error(provider_type.value, str(e))
            return {
                "success": False,
                "error": str(e),
                "provider": provider_type.value
            }
    
    def _call_groq(
        self,
        query: str,
        messages: Optional[List[Dict]]
    ) -> Dict[str, Any]:
        """Call Groq API."""
        try:
            from openai import OpenAI
            
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                return {
                    "success": False,
                    "error": "GROQ_API_KEY not set",
                    "provider": "groq"
                }
            
            client = OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1"
            )
            
            start = time.time()
            
            # Prepare messages
            if not messages:
                messages = []
            
            # Ensure system message
            if not any(m.get("role") == "system" for m in messages):
                messages.insert(0, {
                    "role": "system",
                    "content": "You are VENNELA AI. Reply naturally and directly."
                })
            
            # Add user query
            messages.append({"role": "user", "content": query})
            
            response = client.chat.completions.create(
                model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            
            latency_ms = int((time.time() - start) * 1000)
            ai_response = response.choices[0].message.content
            
            tokens_used = response.usage.total_tokens
            cost = tokens_used * 0.00001  # Groq pricing estimate
            
            result = {
                "success": True,
                "provider": "groq",
                "model": response.model,
                "response": ai_response,
                "tokens_used": tokens_used,
                "cost": cost,
                "latency_ms": latency_ms
            }
            
            self.provider_manager.record_success(
                "groq",
                ProviderResponse(
                    provider="groq",
                    model=response.model,
                    response=ai_response,
                    tokens_used=tokens_used,
                    latency_ms=latency_ms,
                    cost=cost,
                    timestamp=time.time()
                )
            )
            
            logger.info(f"✅ Groq: {latency_ms}ms, {tokens_used} tokens")
            return result
            
        except Exception as e:
            logger.error(f"Groq call failed: {e}")
            self.provider_manager.record_error("groq", str(e))
            return {
                "success": False,
                "error": str(e),
                "provider": "groq"
            }
    
    def _call_openrouter(
        self,
        query: str,
        messages: Optional[List[Dict]]
    ) -> Dict[str, Any]:
        """Call OpenRouter API."""
        try:
            from openai import OpenAI
            
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                return {
                    "success": False,
                    "error": "OPENROUTER_API_KEY not set",
                    "provider": "openrouter"
                }
            
            client = OpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1"
            )
            
            start = time.time()
            
            if not messages:
                messages = []
            
            if not any(m.get("role") == "system" for m in messages):
                messages.insert(0, {
                    "role": "system",
                    "content": "You are VENNELA AI. Reply naturally and directly."
                })
            
            messages.append({"role": "user", "content": query})
            
            response = client.chat.completions.create(
                model=os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            
            latency_ms = int((time.time() - start) * 1000)
            ai_response = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            cost = tokens_used * 0.00002  # OpenRouter pricing estimate
            
            result = {
                "success": True,
                "provider": "openrouter",
                "model": response.model,
                "response": ai_response,
                "tokens_used": tokens_used,
                "cost": cost,
                "latency_ms": latency_ms
            }
            
            self.provider_manager.record_success(
                "openrouter",
                ProviderResponse(
                    provider="openrouter",
                    model=response.model,
                    response=ai_response,
                    tokens_used=tokens_used,
                    latency_ms=latency_ms,
                    cost=cost,
                    timestamp=time.time()
                )
            )
            
            logger.info(
                f"✅ OpenRouter: {latency_ms}ms, {tokens_used} tokens"
            )
            return result
            
        except Exception as e:
            logger.error(f"OpenRouter call failed: {e}")
            self.provider_manager.record_error("openrouter", str(e))
            return {
                "success": False,
                "error": str(e),
                "provider": "openrouter"
            }
    
    def _estimate_cost(
        self,
        provider_type: ProviderType,
        tokens: int
    ) -> float:
        """Estimate cost for provider."""
        # Cost per 1M tokens (approximate)
        pricing = {
            ProviderType.GEMINI_FLASH_LITE: 0.075,
            ProviderType.GEMINI_FLASH: 0.1,
            ProviderType.GEMINI_REASONING: 0.6,
            ProviderType.GEMINI_LIVE: 0.15,
            ProviderType.GROQ: 0.00001,
            ProviderType.OPENROUTER: 0.00002
        }
        
        price_per_token = pricing.get(provider_type, 0.0001) / 1_000_000
        return tokens * price_per_token
    
    def _record_routing(
        self,
        query: str,
        provider: str,
        result: Dict,
        classification: Dict,
        total_time: float
    ) -> None:
        """Record routing decision."""
        record = {
            "query": query[:100],
            "provider": provider,
            "intent": classification.get("intent"),
            "latency_ms": result.get("latency_ms", 0),
            "success": result.get("success", False),
            "timestamp": time.time()
        }
        
        self.routing_history.append(record)
        if len(self.routing_history) > self.max_history:
            self.routing_history = self.routing_history[-self.max_history:]
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics."""
        if not self.routing_history:
            return {"total_routes": 0}
        
        provider_stats = {}
        for record in self.routing_history:
            provider = record["provider"]
            if provider not in provider_stats:
                provider_stats[provider] = {
                    "count": 0,
                    "successful": 0,
                    "avg_latency": 0,
                    "total_latency": 0
                }
            
            provider_stats[provider]["count"] += 1
            if record["success"]:
                provider_stats[provider]["successful"] += 1
            provider_stats[provider]["total_latency"] += record["latency_ms"]
        
        # Calculate averages
        for provider in provider_stats:
            count = provider_stats[provider]["count"]
            provider_stats[provider]["avg_latency"] = (
                provider_stats[provider]["total_latency"] / count
            )
        
        return {
            "total_routes": len(self.routing_history),
            "providers": provider_stats,
            "health": self.provider_manager.get_provider_health_summary()
        }


# Singleton instance
_router_instance = None


def get_multi_llm_router() -> MultiLLMRouter:
    """Get or create router singleton."""
    global _router_instance
    if _router_instance is None:
        _router_instance = MultiLLMRouter()
    return _router_instance
