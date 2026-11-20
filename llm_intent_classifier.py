"""LLM Intent Classifier - Route queries to appropriate providers."""

import logging
from typing import Dict, Optional, List
import re

logger = logging.getLogger(__name__)


class IntentClassifier:
    """Classify user queries to determine optimal LLM provider."""
    
    # Query patterns for classification
    REASONING_KEYWORDS = [
        "analyze", "explain", "reason", "logic", "how does",
        "why", "calculate", "complex", "algorithm", "design",
        "architecture", "research", "understand", "theory",
        "problem solve", "debug", "troubleshoot"
    ]
    
    REALTIME_KEYWORDS = [
        "call", "voice", "speak", "listen", "talk", "hear",
        "urgent", "emergency", "happening now", "streaming"
    ]
    
    LIGHTWEIGHT_KEYWORDS = [
        "hello", "hi", "hey", "what time", "date", "remind me",
        "quick", "fast", "simple", "list", "count", "search",
        "weather", "news", "joke", "quote"
    ]
    
    CREATIVE_KEYWORDS = [
        "write", "create", "imagine", "story", "poem", "song",
        "describe", "paint", "artistic", "design", "brainstorm"
    ]
    
    MATH_KEYWORDS = [
        "calculate", "math", "equation", "compute", "sum",
        "multiply", "divide", "percentage", "formula", "number"
    ]
    
    def __init__(self):
        """Initialize classifier."""
        logger.info("Initializing Intent Classifier")
    
    def classify_query(
        self,
        query: str,
        conversation_length: int = 0,
        user_context: Optional[Dict] = None
    ) -> Dict[str, any]:
        """
        Classify a user query to determine optimal provider.
        
        Args:
            query: User's input query
            conversation_length: Number of messages in conversation
            user_context: Optional user profile data
            
        Returns:
            Classification result with provider recommendation
        """
        if not query or not isinstance(query, str):
            return {
                "intent": "unknown",
                "recommended_provider": "flash_lite",
                "reasoning_required": False,
                "realtime_needed": False,
                "priority": "low",
                "confidence": 0.0,
                "alternatives": ["flash", "reasoning"]
            }
        
        query_lower = query.lower().strip()
        query_length = len(query.split())
        
        try:
            # Score each intent category
            reasoning_score = self._score_keywords(
                query_lower,
                self.REASONING_KEYWORDS
            )
            realtime_score = self._score_keywords(
                query_lower,
                self.REALTIME_KEYWORDS
            )
            lightweight_score = self._score_keywords(
                query_lower,
                self.LIGHTWEIGHT_KEYWORDS
            )
            creative_score = self._score_keywords(
                query_lower,
                self.CREATIVE_KEYWORDS
            )
            math_score = self._score_keywords(
                query_lower,
                self.MATH_KEYWORDS
            )
            
            # Boost scores based on context
            if conversation_length > 10:
                reasoning_score *= 1.2
            
            if query_length > 100:
                reasoning_score *= 1.1
            
            # Determine primary intent
            scores = {
                "reasoning": reasoning_score,
                "realtime": realtime_score,
                "lightweight": lightweight_score,
                "creative": creative_score,
                "math": math_score
            }
            
            primary_intent = max(scores, key=scores.get)
            primary_score = scores[primary_intent]
            
            # Route to provider based on intent
            result = self._route_to_provider(
                primary_intent,
                primary_score,
                scores,
                query_length,
                conversation_length
            )
            
            logger.debug(
                f"Query classified: {primary_intent} "
                f"(confidence: {primary_score:.2f}) "
                f"→ {result['recommended_provider']}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Classification error: {e}")
            return {
                "intent": "unknown",
                "recommended_provider": "flash_lite",
                "reasoning_required": False,
                "realtime_needed": False,
                "priority": "low",
                "confidence": 0.0,
                "alternatives": ["flash", "reasoning"]
            }
    
    def _score_keywords(
        self,
        text: str,
        keywords: List[str]
    ) -> float:
        """Score text based on keyword matches."""
        score = 0.0
        
        for keyword in keywords:
            if keyword in text:
                # Bonus for exact phrase match
                if re.search(rf'\b{re.escape(keyword)}\b', text):
                    score += 1.0
                else:
                    score += 0.5
        
        return min(score / len(keywords), 1.0) if keywords else 0.0
    
    def _route_to_provider(
        self,
        intent: str,
        confidence: float,
        scores: Dict,
        query_length: int,
        conversation_length: int
    ) -> Dict:
        """Route to optimal provider based on intent."""
        
        # High confidence in complex reasoning
        if intent == "reasoning" and confidence > 0.6:
            return {
                "intent": intent,
                "recommended_provider": "reasoning",
                "reasoning_required": True,
                "realtime_needed": False,
                "priority": "high",
                "confidence": confidence,
                "alternatives": ["flash", "flash_lite"]
            }
        
        # Voice/realtime interactions
        if intent == "realtime" and confidence > 0.5:
            return {
                "intent": intent,
                "recommended_provider": "live",
                "reasoning_required": False,
                "realtime_needed": True,
                "priority": "urgent",
                "confidence": confidence,
                "alternatives": ["flash", "reasoning"]
            }
        
        # Lightweight queries
        if intent == "lightweight" and confidence > 0.6:
            return {
                "intent": intent,
                "recommended_provider": "flash_lite",
                "reasoning_required": False,
                "realtime_needed": False,
                "priority": "low",
                "confidence": confidence,
                "alternatives": ["flash", "reasoning"]
            }
        
        # Creative tasks
        if intent == "creative" and confidence > 0.6:
            return {
                "intent": intent,
                "recommended_provider": "flash",
                "reasoning_required": False,
                "realtime_needed": False,
                "priority": "medium",
                "confidence": confidence,
                "alternatives": ["reasoning", "flash_lite"]
            }
        
        # Math/calculations
        if intent == "math" and confidence > 0.6:
            return {
                "intent": intent,
                "recommended_provider": "flash",
                "reasoning_required": True,
                "realtime_needed": False,
                "priority": "medium",
                "confidence": confidence,
                "alternatives": ["reasoning", "flash_lite"]
            }
        
        # Default routing by complexity
        if query_length > 150 and conversation_length > 5:
            return {
                "intent": "complex_reasoning",
                "recommended_provider": "reasoning",
                "reasoning_required": True,
                "realtime_needed": False,
                "priority": "medium",
                "confidence": 0.5,
                "alternatives": ["flash", "flash_lite"]
            }
        
        if query_length < 50:
            return {
                "intent": "simple_query",
                "recommended_provider": "flash_lite",
                "reasoning_required": False,
                "realtime_needed": False,
                "priority": "low",
                "confidence": 0.6,
                "alternatives": ["flash", "reasoning"]
            }
        
        # Default to standard Flash
        return {
            "intent": "general",
            "recommended_provider": "flash",
            "reasoning_required": False,
            "realtime_needed": False,
            "priority": "medium",
            "confidence": 0.5,
            "alternatives": ["flash_lite", "reasoning"]
        }
    
    def estimate_tokens(
        self,
        query: str,
        provider: str
    ) -> Dict[str, int]:
        """Estimate token usage for query on provider."""
        query_tokens = len(query.split()) * 1.3  # ~1.3 tokens per word
        
        token_estimates = {
            "flash_lite": {
                "input_tokens": int(query_tokens),
                "estimated_output_tokens": 150,
                "total_estimated": int(query_tokens + 150)
            },
            "flash": {
                "input_tokens": int(query_tokens),
                "estimated_output_tokens": 250,
                "total_estimated": int(query_tokens + 250)
            },
            "reasoning": {
                "input_tokens": int(query_tokens),
                "estimated_output_tokens": 500,
                "total_estimated": int(query_tokens + 500)
            },
            "live": {
                "input_tokens": int(query_tokens),
                "estimated_output_tokens": 300,
                "total_estimated": int(query_tokens + 300)
            }
        }
        
        return token_estimates.get(
            provider,
            token_estimates["flash"]
        )


# Singleton instance
_classifier_instance = None


def get_classifier() -> IntentClassifier:
    """Get or create classifier singleton."""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = IntentClassifier()
    return _classifier_instance
