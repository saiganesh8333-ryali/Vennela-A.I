"""
🔥 Intelligent LLM Model Selector
Smart routing based on query complexity, latency needs, and cost optimization.

Routing Strategy:
- Casual Chat → gemini-3.1-flash-lite (fast, cheap)
- Reasoning → gemini-2.5-flash (powerful)
- Voice I/O → gemini-live-3.1-flash (streaming)
- Fallback → groq (fast) → openrouter (diverse)
"""

import logging
import time
from typing import Dict, Optional, List, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class ModelTier(Enum):
    """Model capability tiers."""
    LITE = "lite"              # gemini-3.1-flash-lite
    STANDARD = "standard"      # gemini-2.5-flash
    LIVE = "live"              # gemini-live-3.1-flash
    FALLBACK_FAST = "groq"     # groq llama
    FALLBACK_DIVERSE = "openrouter"


class ComplexityScorer:
    """Analyze query complexity to select appropriate model."""
    
    def __init__(self):
        """Initialize complexity scoring."""
        self.reasoning_keywords = {
            "why": 0.8,
            "how": 0.8,
            "explain": 0.9,
            "analyze": 0.85,
            "compare": 0.7,
            "prove": 0.95,
            "derive": 0.9,
            "complex": 0.8,
            "difficult": 0.7,
            "solve": 0.75,
            "logic": 0.8,
            "algorithm": 0.85,
            "math": 0.8,
            "physics": 0.8,
            "chemistry": 0.8,
        }
        
        self.simple_keywords = {
            "hi": 0.1,
            "hello": 0.1,
            "thanks": 0.1,
            "ok": 0.1,
            "yes": 0.1,
            "no": 0.1,
            "what": 0.3,
            "who": 0.3,
            "where": 0.3,
            "when": 0.3,
        }
    
    def score(self, query: str, conversation_length: int = 0) -> float:
        """
        Score query complexity (0.0 = simple, 1.0 = complex).
        
        Args:
            query: User query string
            conversation_length: Number of previous messages (context depth)
            
        Returns:
            Complexity score 0.0-1.0
        """
        if not query:
            return 0.0
        
        query_lower = query.lower().strip()
        score = 0.0
        
        # Base score from query length
        query_words = len(query_lower.split())
        if query_words < 3:
            score += 0.1
        elif query_words < 10:
            score += 0.3
        elif query_words < 30:
            score += 0.5
        else:
            score += 0.7
        
        # Reasoning indicators
        for keyword, weight in self.reasoning_keywords.items():
            if keyword in query_lower:
                score = max(score, weight)
                break  # Use highest scoring keyword
        
        # Simple query indicators (lower score)
        for keyword, weight in self.simple_keywords.items():
            if query_lower.startswith(keyword):
                score = min(score, weight)
                break
        
        # Multi-turn context increases complexity
        if conversation_length > 5:
            score += 0.15
        if conversation_length > 10:
            score += 0.1
        
        # Code or math blocks indicate higher complexity
        if "```" in query or "def " in query or "class " in query:
            score = max(score, 0.8)
        
        if "=" in query and ("{" in query or "[" in query):
            score = max(score, 0.7)
        
        return min(score, 1.0)


class LatencyPredictor:
    """Estimate response latency for each model."""
    
    # Baseline latencies (ms) - empirically determined
    BASELINE_LATENCIES = {
        ModelTier.LITE: 300,           # Fast
        ModelTier.STANDARD: 800,       # Slower but powerful
        ModelTier.LIVE: 150,           # Real-time streaming
        ModelTier.FALLBACK_FAST: 400,  # Groq is fast
        ModelTier.FALLBACK_DIVERSE: 600,  # OpenRouter varies
    }
    
    def __init__(self):
        """Initialize latency tracking."""
        self.model_latencies = {}  # Rolling average
        self.measurement_count = {}
    
    def predict(self, model_tier: ModelTier, token_count: int = 100) -> int:
        """
        Predict latency for a model.
        
        Args:
            model_tier: Which model tier
            token_count: Estimated tokens in response
            
        Returns:
            Predicted latency in milliseconds
        """
        baseline = self.BASELINE_LATENCIES.get(model_tier, 500)
        
        # Token-based adjustment (each token adds ~20ms)
        token_latency = (token_count / 100) * 20
        
        # Use rolling average if available
        if model_tier in self.model_latencies:
            measured = self.model_latencies[model_tier]
            baseline = (baseline + measured) / 2
        
        return int(baseline + token_latency)
    
    def record_latency(self, model_tier: ModelTier, latency_ms: int) -> None:
        """Record actual latency for future predictions."""
        if model_tier not in self.model_latencies:
            self.model_latencies[model_tier] = latency_ms
            self.measurement_count[model_tier] = 1
        else:
            count = self.measurement_count[model_tier]
            avg = self.model_latencies[model_tier]
            new_avg = (avg * count + latency_ms) / (count + 1)
            self.model_latencies[model_tier] = new_avg
            self.measurement_count[model_tier] = count + 1


class CostOptimizer:
    """Calculate cost-effectiveness of model choices."""
    
    # Cost per 1M input tokens (approximate USD)
    INPUT_COSTS = {
        ModelTier.LITE: 0.075,
        ModelTier.STANDARD: 0.3,
        ModelTier.LIVE: 0.1,
        ModelTier.FALLBACK_FAST: 0.05,
        ModelTier.FALLBACK_DIVERSE: 0.15,
    }
    
    # Cost per 1M output tokens (approximate USD)
    OUTPUT_COSTS = {
        ModelTier.LITE: 0.30,
        ModelTier.STANDARD: 1.2,
        ModelTier.LIVE: 0.4,
        ModelTier.FALLBACK_FAST: 0.15,
        ModelTier.FALLBACK_DIVERSE: 0.6,
    }
    
    def estimate_cost(
        self,
        model_tier: ModelTier,
        input_tokens: int = 100,
        output_tokens: int = 100
    ) -> float:
        """
        Estimate cost for a request.
        
        Args:
            model_tier: Model to use
            input_tokens: Estimated input tokens
            output_tokens: Estimated output tokens
            
        Returns:
            Estimated cost in USD
        """
        input_cost = (input_tokens / 1_000_000) * self.INPUT_COSTS.get(model_tier, 0.1)
        output_cost = (output_tokens / 1_000_000) * self.OUTPUT_COSTS.get(model_tier, 0.5)
        return input_cost + output_cost
    
    def cost_effectiveness_score(
        self,
        model_tier: ModelTier,
        quality_score: float,
        input_tokens: int = 100,
        output_tokens: int = 100
    ) -> float:
        """
        Calculate cost-effectiveness (higher = better value).
        
        Score = quality_score / estimated_cost
        """
        cost = self.estimate_cost(model_tier, input_tokens, output_tokens)
        if cost == 0:
            cost = 0.0001  # Avoid division by zero
        
        return quality_score / cost


class ModelSelector:
    """Main intelligent model selection engine."""
    
    def __init__(self):
        """Initialize selector components."""
        self.complexity_scorer = ComplexityScorer()
        self.latency_predictor = LatencyPredictor()
        self.cost_optimizer = CostOptimizer()
        
        # Health tracking for fallback
        self.model_health = {tier: 1.0 for tier in ModelTier}
        self.error_counts = {tier: 0 for tier in ModelTier}
    
    def select_model(
        self,
        query: str,
        conversation_length: int = 0,
        force_model: Optional[str] = None,
        is_voice: bool = False,
        latency_budget_ms: int = 2000
    ) -> Tuple[ModelTier, Dict[str, any]]:
        """
        Select optimal model based on query and constraints.
        
        Args:
            query: User query
            conversation_length: Number of prior messages
            force_model: Force specific model (for testing)
            is_voice: Is this a voice/streaming request?
            latency_budget_ms: Maximum acceptable latency
            
        Returns:
            (ModelTier, selection_metadata)
        """
        logger.info(f"🧠 Selecting model for: {query[:50]}...")
        
        # Force override
        if force_model:
            try:
                model = ModelTier[force_model.upper()]
                logger.info(f"✓ Force model: {model.value}")
                return model, {"reason": "forced", "force_model": force_model}
            except KeyError:
                logger.warning(f"Invalid force model: {force_model}, continuing auto-selection")
        
        # Voice takes priority
        if is_voice:
            logger.info("✓ Voice mode → gemini-live")
            return ModelTier.LIVE, {"reason": "voice", "model": "gemini-live-3.1-flash"}
        
        # Score complexity
        complexity = self.complexity_scorer.score(query, conversation_length)
        logger.debug(f"Complexity score: {complexity:.2f}")
        
        # Estimate tokens (rough: 1 word ≈ 1.3 tokens)
        words = len(query.split())
        input_tokens = int(words * 1.3)
        output_tokens = min(500, input_tokens * 2)  # Response usually 2x input
        
        # Score each model
        scores = {}
        
        if complexity > 0.7:
            # Complex query → use powerful model
            scores[ModelTier.STANDARD] = {
                "score": 0.95,
                "reason": "high_complexity",
                "latency": self.latency_predictor.predict(ModelTier.STANDARD, output_tokens)
            }
            scores[ModelTier.LITE] = {
                "score": 0.6,
                "reason": "fallback_for_complex",
                "latency": self.latency_predictor.predict(ModelTier.LITE, output_tokens)
            }
        elif complexity > 0.4:
            # Medium complexity → balanced choice
            scores[ModelTier.LITE] = {
                "score": 0.85,
                "reason": "medium_complexity",
                "latency": self.latency_predictor.predict(ModelTier.LITE, output_tokens)
            }
            scores[ModelTier.STANDARD] = {
                "score": 0.75,
                "reason": "overkill_but_available",
                "latency": self.latency_predictor.predict(ModelTier.STANDARD, output_tokens)
            }
        else:
            # Simple query → use fast lite model
            scores[ModelTier.LITE] = {
                "score": 0.98,
                "reason": "simple_query",
                "latency": self.latency_predictor.predict(ModelTier.LITE, output_tokens)
            }
        
        # Apply health penalties
        for tier, score_data in scores.items():
            health = self.model_health.get(tier, 1.0)
            score_data["score"] *= health
            if health < 0.8:
                logger.warning(f"⚠️ {tier.value} unhealthy ({health:.2f})")
        
        # Check latency constraints
        for tier, score_data in list(scores.items()):
            if score_data["latency"] > latency_budget_ms:
                logger.warning(f"⏱️ {tier.value} exceeds budget ({score_data['latency']}ms > {latency_budget_ms}ms)")
                if tier != ModelTier.LITE:
                    del scores[tier]
        
        # Select best scored model
        if not scores:
            logger.warning("All models exceeded latency budget, using LITE")
            selected = ModelTier.LITE
        else:
            selected = max(scores.items(), key=lambda x: x[1]["score"])[0]
        
        selected_data = scores.get(selected, {"reason": "fallback"})
        
        logger.info(f"✓ Selected: {selected.value} (score: {selected_data['score']:.2f}, latency: {selected_data.get('latency', 'N/A')}ms)")
        
        return selected, {
            "complexity": complexity,
            "selected_model": selected.value,
            "scores": {k.value: v for k, v in scores.items()},
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_estimate": self.cost_optimizer.estimate_cost(selected, input_tokens, output_tokens)
        }
    
    def record_usage(self, model_tier: ModelTier, latency_ms: int, success: bool) -> None:
        """Record actual usage for future optimization."""
        self.latency_predictor.record_latency(model_tier, latency_ms)
        
        if success:
            self.error_counts[model_tier] = max(0, self.error_counts[model_tier] - 1)
            self.model_health[model_tier] = min(1.0, self.model_health[model_tier] + 0.05)
        else:
            self.error_counts[model_tier] += 1
            self.model_health[model_tier] *= 0.8


# Singleton instance
_selector = None


def get_model_selector() -> ModelSelector:
    """Get or create model selector instance."""
    global _selector
    if _selector is None:
        _selector = ModelSelector()
    return _selector


def select_model_for_query(
    query: str,
    conversation_length: int = 0,
    force_model: Optional[str] = None,
    is_voice: bool = False
) -> Tuple[ModelTier, Dict]:
    """Convenience function to select model."""
    selector = get_model_selector()
    return selector.select_model(
        query,
        conversation_length=conversation_length,
        force_model=force_model,
        is_voice=is_voice
    )
