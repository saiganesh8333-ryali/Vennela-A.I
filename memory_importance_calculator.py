"""
🧠 Memory Importance Calculator
Scores memories based on emotional weight, repetition, and recency.

Formula:
importance = (emotional_weight * 0.4) + (repetition_weight * 0.3) + (recency_weight * 0.3)

This enables intelligent memory prioritization in long-term storage.
"""

import logging
import time
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class EmotionalScorer:
    """Score emotional importance of statements."""
    
    def __init__(self):
        """Initialize emotional scoring keywords."""
        self.high_emotion_keywords = {
            # Positive emotions
            "love": 0.9, "passionate": 0.85, "excited": 0.8, "thrilled": 0.85,
            "happy": 0.7, "delighted": 0.8, "amazing": 0.75, "wonderful": 0.75,
            "beautiful": 0.7, "great": 0.6,
            
            # Negative emotions
            "hate": 0.9, "terrified": 0.85, "devastated": 0.85, "angry": 0.8,
            "frustrated": 0.7, "sad": 0.8, "depressed": 0.85, "anxious": 0.8,
            "scared": 0.75, "worried": 0.7, "afraid": 0.75,
            
            # Intensity markers
            "never": 0.75, "always": 0.7, "absolutely": 0.65, "definitely": 0.6,
            "must": 0.65, "urgent": 0.75, "critical": 0.8, "essential": 0.7,
            
            # Personal goals
            "goal": 0.8, "dream": 0.85, "aspiration": 0.8, "ambition": 0.75,
            "objective": 0.7, "target": 0.65, "want": 0.6, "need": 0.7,
        }
        
        self.medium_emotion_keywords = {
            "like": 0.5, "prefer": 0.5, "enjoy": 0.6, "dislike": 0.55,
            "interesting": 0.5, "boring": 0.5, "good": 0.4, "bad": 0.4,
            "okay": 0.3, "fine": 0.3,
        }
    
    def score_emotional_weight(self, text: str) -> float:
        """
        Score emotional content (0.0-1.0).
        
        Args:
            text: User statement
            
        Returns:
            Emotional weight score
        """
        if not text:
            return 0.0
        
        text_lower = text.lower()
        max_weight = 0.0
        
        # Check high emotion keywords
        for keyword, weight in self.high_emotion_keywords.items():
            if keyword in text_lower:
                max_weight = max(max_weight, weight)
        
        # Check medium emotion keywords
        if max_weight < 0.6:
            for keyword, weight in self.medium_emotion_keywords.items():
                if keyword in text_lower:
                    max_weight = max(max_weight, weight)
        
        # Exclamation marks boost emotion
        exclamation_count = text.count("!")
        if exclamation_count > 0:
            max_weight = min(1.0, max_weight + (exclamation_count * 0.1))
        
        # Caps boost emotion
        caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
        if caps_ratio > 0.3:
            max_weight = min(1.0, max_weight + 0.15)
        
        return min(max_weight, 1.0)


class RepetitionScorer:
    """Track how many times user mentions topics."""
    
    def __init__(self):
        """Initialize repetition tracking."""
        self.mention_counts = {}
        self.topic_history = []  # List of (topic, timestamp)
    
    def add_mention(self, topic: str, weight: float = 1.0) -> None:
        """Record topic mention."""
        if topic not in self.mention_counts:
            self.mention_counts[topic] = 0
        
        self.mention_counts[topic] += weight
        self.topic_history.append((topic, time.time()))
    
    def get_repetition_score(self, topic: str) -> float:
        """
        Score based on how many times topic mentioned.
        
        1st mention: 0.1
        2-3 mentions: 0.3
        4-5 mentions: 0.6
        6+ mentions: 1.0
        """
        count = self.mention_counts.get(topic, 0)
        
        if count == 0:
            return 0.0
        elif count == 1:
            return 0.1
        elif count <= 3:
            return 0.3
        elif count <= 5:
            return 0.6
        else:
            return 1.0
    
    def get_mention_frequency(self, topic: str, days: int = 7) -> float:
        """
        Score based on frequency in recent period.
        
        Returns: How concentrated mentions are (higher = more recent focus)
        """
        cutoff_time = time.time() - (days * 86400)
        recent_mentions = [
            t for t, ts in self.topic_history
            if t == topic and ts > cutoff_time
        ]
        
        if not recent_mentions:
            return 0.0
        
        # More recent mentions = higher score
        return min(len(recent_mentions) / 10.0, 1.0)


class RecencyScorer:
    """Score based on how recent information is."""
    
    @staticmethod
    def score_recency(timestamp: float) -> float:
        """
        Score based on age (newer = higher score).
        
        Today: 1.0
        1-3 days: 0.8
        1-2 weeks: 0.6
        2-4 weeks: 0.4
        1-3 months: 0.2
        3+ months: 0.1
        """
        age_seconds = time.time() - timestamp
        age_days = age_seconds / 86400
        
        if age_days <= 1:
            return 1.0
        elif age_days <= 3:
            return 0.8
        elif age_days <= 14:
            return 0.6
        elif age_days <= 28:
            return 0.4
        elif age_days <= 90:
            return 0.2
        else:
            return 0.1


class MemoryImportanceCalculator:
    """Main importance calculator combining all factors."""
    
    def __init__(self):
        """Initialize all scoring components."""
        self.emotional_scorer = EmotionalScorer()
        self.repetition_scorer = RepetitionScorer()
        self.recency_scorer = RecencyScorer()
        
        # Weights for final calculation
        self.EMOTIONAL_WEIGHT = 0.4
        self.REPETITION_WEIGHT = 0.3
        self.RECENCY_WEIGHT = 0.3
    
    def calculate_importance(
        self,
        text: str,
        timestamp: Optional[float] = None,
        topic: Optional[str] = None,
        context_boost: float = 0.0
    ) -> float:
        """
        Calculate overall importance score (0.0-1.0).
        
        Args:
            text: Memory content
            timestamp: When this memory was created
            topic: Category/topic of memory
            context_boost: Additional boost based on context (0.0-0.5)
            
        Returns:
            Importance score 0.0-1.0
        """
        if not text:
            return 0.0
        
        # Score components
        emotional = self.emotional_scorer.score_emotional_weight(text)
        
        # Repetition (if topic provided)
        if topic:
            self.repetition_scorer.add_mention(topic, weight=1.0)
            repetition = self.repetition_scorer.get_repetition_score(topic)
        else:
            repetition = 0.2  # Neutral baseline
        
        # Recency (if timestamp provided)
        if timestamp:
            recency = self.recency_scorer.score_recency(timestamp)
        else:
            recency = 1.0  # Assume recent if not specified
        
        # Calculate weighted importance
        importance = (
            (emotional * self.EMOTIONAL_WEIGHT) +
            (repetition * self.REPETITION_WEIGHT) +
            (recency * self.RECENCY_WEIGHT)
        )
        
        # Apply context boost
        importance = min(1.0, importance + context_boost)
        
        return importance
    
    def categorize_importance(self, score: float) -> str:
        """Categorize importance into buckets."""
        if score >= 0.8:
            return "critical"  # Must preserve
        elif score >= 0.6:
            return "high"      # Important
        elif score >= 0.4:
            return "medium"    # Useful
        elif score >= 0.2:
            return "low"       # Reference
        else:
            return "minimal"   # Can trim


class MemoryPrioritizer:
    """Prioritize memories for storage and retrieval."""
    
    def __init__(self, max_memories: int = 100):
        """Initialize prioritizer."""
        self.max_memories = max_memories
        self.memories: List[Dict] = []
        self.calculator = MemoryImportanceCalculator()
    
    def add_memory(
        self,
        text: str,
        topic: str,
        metadata: Optional[Dict] = None,
        timestamp: Optional[float] = None
    ) -> float:
        """
        Add memory and return importance score.
        
        Returns: Importance score
        """
        if not timestamp:
            timestamp = time.time()
        
        importance = self.calculator.calculate_importance(
            text,
            timestamp=timestamp,
            topic=topic
        )
        
        memory = {
            "text": text,
            "topic": topic,
            "importance": importance,
            "category": self.calculator.categorize_importance(importance),
            "timestamp": timestamp,
            "metadata": metadata or {}
        }
        
        self.memories.append(memory)
        self._trim_to_capacity()
        
        return importance
    
    def _trim_to_capacity(self) -> None:
        """Remove lowest importance memories if over capacity."""
        if len(self.memories) <= self.max_memories:
            return
        
        # Sort by importance
        self.memories.sort(key=lambda m: m["importance"], reverse=True)
        
        # Keep top N
        self.memories = self.memories[:self.max_memories]
    
    def get_critical_memories(self) -> List[Dict]:
        """Get memories marked as critical."""
        return [m for m in self.memories if m["category"] == "critical"]
    
    def get_high_importance_memories(self) -> List[Dict]:
        """Get high + critical importance memories."""
        return [
            m for m in self.memories
            if m["category"] in ["critical", "high"]
        ]
    
    def get_topic_memories(self, topic: str) -> List[Dict]:
        """Get all memories for a topic, sorted by importance."""
        topic_memories = [m for m in self.memories if m["topic"] == topic]
        return sorted(topic_memories, key=lambda m: m["importance"], reverse=True)
    
    def get_recent_memories(self, days: int = 7) -> List[Dict]:
        """Get recent memories from last N days."""
        cutoff = time.time() - (days * 86400)
        recent = [m for m in self.memories if m["timestamp"] > cutoff]
        return sorted(recent, key=lambda m: m["importance"], reverse=True)
    
    def get_summary_stats(self) -> Dict:
        """Get statistics about stored memories."""
        if not self.memories:
            return {
                "total": 0,
                "distribution": {},
                "topics": {}
            }
        
        # Category distribution
        distribution = {}
        for m in self.memories:
            cat = m["category"]
            distribution[cat] = distribution.get(cat, 0) + 1
        
        # Topic distribution
        topics = {}
        for m in self.memories:
            topic = m["topic"]
            topics[topic] = topics.get(topic, 0) + 1
        
        return {
            "total": len(self.memories),
            "capacity": self.max_memories,
            "average_importance": sum(m["importance"] for m in self.memories) / len(self.memories),
            "distribution": distribution,
            "topics": topics
        }


# Singleton instance
_calculator = None


def get_importance_calculator() -> MemoryImportanceCalculator:
    """Get or create calculator instance."""
    global _calculator
    if _calculator is None:
        _calculator = MemoryImportanceCalculator()
    return _calculator
