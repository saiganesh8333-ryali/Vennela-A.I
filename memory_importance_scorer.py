"""Memory Intelligence - Phase 4 importance scorer."""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


def calculate_content_importance(memory_text: str) -> float:
    """
    Calculate importance based on content.
    
    Returns:
        Score [0, 1]
    """
    if not memory_text or not isinstance(memory_text, str):
        return 0.3
    
    try:
        importance = 0.3
        lower_text = memory_text.lower()
        
        # Personal information
        personal_keywords = ["name", "birthday", "anniversary", "goal", "dream", "hobby"]
        for keyword in personal_keywords:
            if keyword in lower_text:
                importance += 0.15
        
        # Emotional markers
        emotional_keywords = ["love", "hate", "fear", "cherish", "regret", "proud"]
        for keyword in emotional_keywords:
            if keyword in lower_text:
                importance += 0.1
        
        # Milestone markers
        milestone_keywords = ["first", "last", "never", "always", "breakthrough", "achieved"]
        for keyword in milestone_keywords:
            if keyword in lower_text:
                importance += 0.1
        
        # Length indicates importance
        if len(memory_text) > 200:
            importance += 0.1
        
        return min(1.0, importance)
    
    except Exception as e:
        logger.error(f"Error calculating content importance: {e}")
        return 0.3


def calculate_emotional_valence_importance(
    emotion: str,
    sentiment: str,
    user_emotions: Dict = None
) -> float:
    """
    Calculate importance based on emotional valence.
    
    Returns:
        Score [0, 1]
    """
    user_emotions = user_emotions or {}
    
    try:
        importance = 0.3
        
        # Strong emotions increase importance
        strong_emotions = ["love", "fear", "anger", "grief", "joy", "shame"]
        if emotion in strong_emotions:
            importance += 0.2
        
        # Negative sentiments increase importance (more memorable)
        if sentiment in ["negative", "sad", "angry"]:
            importance += 0.15
        
        # If emotion is dominant in user's history
        if user_emotions:
            total_emotions = sum(user_emotions.values())
            if total_emotions > 0:
                emotion_ratio = user_emotions.get(emotion, 0) / total_emotions
                if emotion_ratio > 0.3:
                    importance += 0.15
        
        return min(1.0, importance)
    
    except Exception as e:
        logger.error(f"Error calculating emotional valence: {e}")
        return 0.3


def calculate_relationship_importance(
    memory_item: Dict,
    all_memories: List[Dict] = None
) -> float:
    """
    Calculate importance based on how often related to other memories.
    
    Returns:
        Score [0, 1]
    """
    all_memories = all_memories or []
    
    try:
        importance = 0.3
        
        if not all_memories:
            return importance
        
        memory_text = memory_item.get("text", memory_item.get("content", "")).lower()
        keywords = set(memory_text.split())
        
        related_count = 0
        for other in all_memories:
            if other == memory_item:
                continue
            other_text = other.get("text", other.get("content", "")).lower()
            other_words = set(other_text.split())
            
            if keywords & other_words:
                related_count += 1
        
        # More connections = more important
        if related_count > 5:
            importance = 0.8
        elif related_count > 2:
            importance = 0.6
        elif related_count > 0:
            importance = 0.5
        
        return min(1.0, importance)
    
    except Exception as e:
        logger.error(f"Error calculating relationship importance: {e}")
        return 0.3


def calculate_temporal_importance(timestamp: float) -> float:
    """
    Calculate importance based on temporal significance.
    
    Returns:
        Score [0, 1]
    """
    try:
        import time
        import datetime
        
        current_time = time.time()
        memory_time = datetime.datetime.fromtimestamp(timestamp)
        current_date = datetime.datetime.now()
        
        # Anniversaries increase importance
        if memory_time.month == current_date.month and memory_time.day == current_date.day:
            return 0.9
        
        # Recent events
        age_days = (current_time - timestamp) / (24 * 3600)
        if age_days < 7:
            return 0.7
        elif age_days < 30:
            return 0.5
        elif age_days < 365:
            return 0.4
        else:
            return 0.3
    
    except Exception as e:
        logger.error(f"Error calculating temporal importance: {e}")
        return 0.3


class ImportanceScorer:
    """Calculate emotional and contextual importance of memories."""
    
    def __init__(self):
        """Initialize scorer."""
        self.cache = {}
    
    def score_memory(
        self,
        memory_item: Dict,
        user_emotions: Dict = None,
        all_memories: List[Dict] = None
    ) -> Dict:
        """
        Calculate comprehensive importance score.
        
        Returns:
            Dict with score and breakdown
        """
        if not memory_item or not isinstance(memory_item, dict):
            return {"importance_score": 0.3, "components": {}}
        
        try:
            components = {
                "content_importance": calculate_content_importance(
                    memory_item.get("text", memory_item.get("content", ""))
                ),
                "emotional_importance": calculate_emotional_valence_importance(
                    memory_item.get("emotion", "neutral"),
                    memory_item.get("sentiment", "neutral"),
                    user_emotions
                ),
                "relationship_importance": calculate_relationship_importance(
                    memory_item,
                    all_memories
                ),
                "temporal_importance": calculate_temporal_importance(
                    memory_item.get("timestamp", 0)
                )
            }
            
            # Weighted composite
            importance = (
                components["content_importance"] * 0.25 +
                components["emotional_importance"] * 0.35 +
                components["relationship_importance"] * 0.2 +
                components["temporal_importance"] * 0.2
            )
            
            return {
                "importance_score": importance,
                "components": components,
                "high_importance": importance > 0.6
            }
        
        except Exception as e:
            logger.error(f"Error scoring memory importance: {e}")
            return {"importance_score": 0.3, "components": {}}
    
    def score_all_memories(
        self,
        memories: List[Dict],
        user_emotions: Dict = None
    ) -> List[Dict]:
        """Score all memories and rank by importance."""
        if not memories or not isinstance(memories, list):
            return []
        
        try:
            scored = []
            for mem in memories:
                result = self.score_memory(mem, user_emotions, memories)
                mem_copy = mem.copy()
                mem_copy["importance_score"] = result["importance_score"]
                mem_copy["importance_components"] = result["components"]
                scored.append(mem_copy)
            
            # Sort by importance
            scored.sort(key=lambda x: x["importance_score"], reverse=True)
            
            return scored
        
        except Exception as e:
            logger.error(f"Error scoring memories: {e}")
            return []
