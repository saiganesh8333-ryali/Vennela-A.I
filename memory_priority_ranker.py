"""Memory Intelligence - Phase 4 priority ranker."""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def calculate_usefulness_score(memory_item: Dict, reinforcement_score: float = 0.0) -> float:
    """
    Calculate usefulness based on reinforcement feedback.
    
    Returns:
        Score [0, 1]
    """
    if not memory_item or not isinstance(memory_item, dict):
        return 0.0
    
    try:
        score = 0.5
        
        if reinforcement_score > 0:
            score += reinforcement_score * 0.3
        elif reinforcement_score < 0:
            score += reinforcement_score * 0.2
        
        return max(0.0, min(1.0, score))
    except Exception as e:
        logger.error(f"Error calculating usefulness: {e}")
        return 0.5


def calculate_frequency_score(access_count: int) -> float:
    """
    Calculate frequency score based on access count.
    
    Returns:
        Score [0, 1]
    """
    try:
        if access_count <= 0:
            return 0.1
        elif access_count < 5:
            return 0.3
        elif access_count < 10:
            return 0.6
        else:
            return min(1.0, 0.6 + (access_count - 10) / 100)
    
    except Exception as e:
        logger.error(f"Error calculating frequency: {e}")
        return 0.5


def calculate_recency_score(timestamp: float) -> float:
    """
    Calculate recency score with exponential decay.
    
    Args:
        timestamp: Memory timestamp (epoch seconds)
    
    Returns:
        Score [0, 1]
    """
    try:
        import time
        current_time = time.time()
        age_days = (current_time - timestamp) / (24 * 3600)
        
        # Exponential decay: newer = higher score
        recency = 1.0 * (0.95 ** age_days)
        
        return max(0.0, min(1.0, recency))
    
    except Exception as e:
        logger.error(f"Error calculating recency: {e}")
        return 0.5


def calculate_emotional_importance(memory_item: Dict, user_emotions: Dict = None) -> float:
    """
    Calculate emotional importance of memory.
    
    Returns:
        Score [0, 1]
    """
    if not memory_item or not isinstance(memory_item, dict):
        return 0.3
    
    user_emotions = user_emotions or {}
    
    try:
        importance = 0.3
        
        # Check if memory is tagged as important
        if memory_item.get("emotional_importance", False):
            importance += 0.4
        
        # Check associated emotion
        emotion = memory_item.get("emotion", "neutral")
        if emotion != "neutral" and user_emotions.get(emotion, 0) > 0:
            importance += 0.2
        
        # Check for milestone events
        if memory_item.get("type") == "event":
            importance += 0.1
        
        return max(0.0, min(1.0, importance))
    
    except Exception as e:
        logger.error(f"Error calculating emotional importance: {e}")
        return 0.3


def calculate_semantic_relatedness(
    memory_text: str,
    query_text: str,
    embedding_engine = None
) -> float:
    """
    Calculate semantic similarity between memory and query.
    
    Returns:
        Score [0, 1]
    """
    if not memory_text or not query_text:
        return 0.0
    
    try:
        if embedding_engine is None:
            # Fallback to simple keyword matching
            memory_lower = memory_text.lower()
            query_lower = query_text.lower()
            
            memory_words = set(memory_lower.split())
            query_words = set(query_lower.split())
            
            intersection = memory_words & query_words
            union = memory_words | query_words
            
            if not union:
                return 0.0
            
            jaccard = len(intersection) / len(union)
            return min(1.0, jaccard)
        
        else:
            # Use embedding engine for semantic similarity
            return embedding_engine.similarity(memory_text, query_text)
    
    except Exception as e:
        logger.error(f"Error calculating semantic relatedness: {e}")
        return 0.0


class MemoryPriorityRanker:
    """Rank memories by relevance and importance."""
    
    def __init__(self, embedding_engine = None):
        """Initialize ranker."""
        self.embedding_engine = embedding_engine
        self.memory_cache = {}
    
    def score_memory(
        self,
        memory_item: Dict,
        reinforcement_score: float = 0.0,
        user_emotions: Dict = None,
        query_text: str = None
    ) -> Dict:
        """
        Calculate comprehensive priority score for memory.
        
        Returns:
            Dict with score and components
        """
        if not memory_item or not isinstance(memory_item, dict):
            return {"score": 0.0, "components": {}}
        
        try:
            components = {
                "usefulness": calculate_usefulness_score(memory_item, reinforcement_score),
                "frequency": calculate_frequency_score(memory_item.get("access_count", 0)),
                "recency": calculate_recency_score(memory_item.get("timestamp", 0)),
                "emotional_importance": calculate_emotional_importance(memory_item, user_emotions),
                "semantic_relatedness": 0.0
            }
            
            # Calculate semantic relatedness if query provided
            if query_text:
                memory_text = memory_item.get("text", memory_item.get("content", ""))
                components["semantic_relatedness"] = calculate_semantic_relatedness(
                    memory_text,
                    query_text,
                    self.embedding_engine
                )
            
            # Weighted composite score
            score = (
                components["usefulness"] * 0.25 +
                components["frequency"] * 0.15 +
                components["recency"] * 0.2 +
                components["emotional_importance"] * 0.15 +
                components["semantic_relatedness"] * 0.25
            )
            
            return {
                "score": score,
                "components": components,
                "ranked_at": __import__('time').time()
            }
        
        except Exception as e:
            logger.error(f"Error scoring memory: {e}")
            return {"score": 0.0, "components": {}}
    
    def rank_memories(
        self,
        memories: List[Dict],
        query_text: str = None,
        user_emotions: Dict = None,
        top_k: int = 5
    ) -> List[Dict]:
        """
        Rank memories by priority.
        
        Args:
            memories: List of memory items
            query_text: Optional query for semantic ranking
            user_emotions: User emotions dict
            top_k: Number of top results
        
        Returns:
            Ranked memories
        """
        if not memories or not isinstance(memories, list):
            return []
        
        try:
            scored = []
            for mem in memories:
                score_result = self.score_memory(
                    mem,
                    0.0,
                    user_emotions,
                    query_text
                )
                mem_copy = mem.copy()
                mem_copy["priority_score"] = score_result["score"]
                mem_copy["score_components"] = score_result["components"]
                scored.append(mem_copy)
            
            # Sort by score descending
            scored.sort(key=lambda x: x["priority_score"], reverse=True)
            
            return scored[:top_k]
        
        except Exception as e:
            logger.error(f"Error ranking memories: {e}")
            return []
