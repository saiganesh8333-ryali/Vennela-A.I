"""ML Training - Phase 2 pattern detector."""

import logging
from typing import Dict, List, Optional
from collections import defaultdict, Counter
import re

logger = logging.getLogger(__name__)


def detect_favorite_topics(messages: List[str], weights: List[float] = None) -> List[str]:
    """
    Detect favorite topics from message frequency.
    
    Args:
        messages: List of messages
        weights: Optional weights (higher = more important)
    
    Returns:
        List of favorite topics sorted by frequency
    """
    if not messages or not isinstance(messages, list):
        return []
    
    try:
        weights = weights or [1.0] * len(messages)
        
        # Topic keywords
        topic_patterns = {
            "technology": ["code", "programming", "python", "javascript", "tech", "software", "app", "api"],
            "business": ["business", "startup", "market", "sales", "profit", "revenue", "customer"],
            "health": ["health", "fitness", "diet", "exercise", "workout", "medicine", "doctor"],
            "art": ["art", "painting", "music", "creative", "design", "photo", "drawing"],
            "sports": ["sport", "game", "play", "score", "team", "player", "match", "win"],
            "education": ["learn", "study", "course", "school", "university", "class", "teaching"],
            "travel": ["travel", "trip", "vacation", "destination", "flight", "hotel", "visit"],
            "food": ["food", "recipe", "cook", "eat", "restaurant", "meal", "cooking"],
            "entertainment": ["movie", "show", "series", "film", "watch", "episode", "character"],
            "relationships": ["friend", "family", "relationship", "love", "dating", "partner"]
        }
        
        topic_scores = defaultdict(float)
        
        for msg, weight in zip(messages, weights):
            lower_msg = msg.lower()
            for topic, keywords in topic_patterns.items():
                for keyword in keywords:
                    if keyword in lower_msg:
                        topic_scores[topic] += weight
        
        sorted_topics = sorted(topic_scores.items(), key=lambda x: x[1], reverse=True)
        return [topic for topic, _ in sorted_topics[:5]]
    
    except Exception as e:
        logger.error(f"Error detecting favorite topics: {e}")
        return []


def detect_emotional_triggers(messages: List[str], emotions: Dict = None) -> Dict:
    """
    Detect emotional triggers and sensitivity patterns.
    
    Returns:
        Dict with triggers, frequencies, and associated emotions
    """
    if not messages or not isinstance(messages, list):
        return {"triggers": {}, "sensitive_topics": []}
    
    try:
        emotions = emotions or {}
        
        triggers = defaultdict(lambda: {"frequency": 0, "associated_emotion": None})
        sensitive_topics = []
        
        # Trigger keywords
        trigger_patterns = {
            "failure": ["fail", "failed", "failure", "mistake", "error", "wrong"],
            "criticism": ["bad", "terrible", "useless", "stupid", "dumb", "wrong"],
            "success": ["great", "excellent", "success", "achieved", "won", "perfect"],
            "loss": ["lost", "lost", "grief", "miss", "nostalgia", "forgotten"],
            "stress": ["stressed", "overwhelmed", "pressure", "deadline", "urgent"]
        }
        
        sensitivity_keywords = [
            "health", "money", "death", "illness", "accident", "trauma",
            "divorce", "rejection", "failure", "discrimination"
        ]
        
        # Count triggers
        for msg in messages:
            lower_msg = msg.lower()
            for trigger_type, keywords in trigger_patterns.items():
                for keyword in keywords:
                    if keyword in lower_msg:
                        triggers[trigger_type]["frequency"] += 1
            
            for sensitive in sensitivity_keywords:
                if sensitive in lower_msg:
                    if sensitive not in sensitive_topics:
                        sensitive_topics.append(sensitive)
        
        # Get dominant emotion for each trigger
        if emotions:
            main_emotion = max(emotions, key=emotions.get) if emotions else None
            for trigger in triggers:
                triggers[trigger]["associated_emotion"] = main_emotion
        
        return {
            "triggers": dict(triggers),
            "sensitive_topics": sensitive_topics,
            "trigger_count": sum(t["frequency"] for t in triggers.values())
        }
    
    except Exception as e:
        logger.error(f"Error detecting emotional triggers: {e}")
        return {"triggers": {}, "sensitive_topics": []}


def detect_time_patterns(timestamps: List[float] = None, message_count: int = None) -> Dict:
    """
    Detect time patterns in interactions.
    
    Args:
        timestamps: Message timestamps
        message_count: Total messages
    
    Returns:
        Dict with time patterns
    """
    try:
        patterns = {
            "peak_activity_time": None,
            "activity_frequency": "unknown",
            "avg_response_gap": None,
            "message_count": message_count or 0
        }
        
        if timestamps and len(timestamps) > 1:
            # Determine activity frequency
            time_diffs = []
            for i in range(1, len(timestamps)):
                diff = timestamps[i] - timestamps[i - 1]
                if diff > 0:
                    time_diffs.append(diff)
            
            if time_diffs:
                avg_gap = sum(time_diffs) / len(time_diffs)
                patterns["avg_response_gap"] = avg_gap
                
                if avg_gap < 3600:
                    patterns["activity_frequency"] = "very_high"
                elif avg_gap < 86400:
                    patterns["activity_frequency"] = "high"
                elif avg_gap < 604800:
                    patterns["activity_frequency"] = "medium"
                else:
                    patterns["activity_frequency"] = "low"
        
        elif message_count:
            if message_count > 100:
                patterns["activity_frequency"] = "very_high"
            elif message_count > 50:
                patterns["activity_frequency"] = "high"
            elif message_count > 10:
                patterns["activity_frequency"] = "medium"
            else:
                patterns["activity_frequency"] = "low"
        
        return patterns
    
    except Exception as e:
        logger.error(f"Error detecting time patterns: {e}")
        return {"peak_activity_time": None, "activity_frequency": "unknown"}


def detect_recurring_tasks(messages: List[str]) -> List[Dict]:
    """
    Detect recurring tasks mentioned in messages.
    
    Returns:
        List of recurring task dicts with frequency
    """
    if not messages or not isinstance(messages, list):
        return []
    
    try:
        recurring_keywords = [
            "every", "daily", "weekly", "monthly", "yearly",
            "usually", "always", "often", "frequently", "regularly"
        ]
        
        tasks = []
        task_pattern = r'(?:every|daily|weekly|monthly|usually|always|often)\s+([^.!?]+)'
        
        for msg in messages:
            lower_msg = msg.lower()
            
            # Check if message mentions recurring activity
            for keyword in recurring_keywords:
                if keyword in lower_msg:
                    matches = re.findall(task_pattern, lower_msg)
                    for match in matches:
                        task_text = match.strip()
                        # Check if task already exists
                        existing = next(
                            (t for t in tasks if t["task"] == task_text),
                            None
                        )
                        if existing:
                            existing["frequency"] += 1
                        else:
                            tasks.append({
                                "task": task_text,
                                "frequency": 1,
                                "pattern": keyword
                            })
        
        # Sort by frequency
        tasks.sort(key=lambda x: x["frequency"], reverse=True)
        return tasks[:10]
    
    except Exception as e:
        logger.error(f"Error detecting recurring tasks: {e}")
        return []


def detect_all_patterns(user_memory: Dict, timestamps: List[float] = None) -> Dict:
    """
    Orchestrate all pattern detection.
    
    Args:
        user_memory: User memory dict
        timestamps: Optional message timestamps
    
    Returns:
        Complete patterns dict
    """
    if not user_memory or not isinstance(user_memory, dict):
        return {"topics": [], "triggers": {}, "time_patterns": {}, "recurring_tasks": []}
    
    try:
        # Extract messages
        short_term = user_memory.get("short_term", [])
        long_term = user_memory.get("long_term", [])
        
        messages = [
            item.get("content", item) if isinstance(item, dict) else item
            for item in short_term + long_term
        ]
        
        # Get emotions if available
        emotions = user_memory.get("emotions", {})
        
        # Get importance scores for weighting
        importance = user_memory.get("importance", [])
        weights = [item.get("score", 1.0) for item in importance][:len(messages)]
        
        patterns = {
            "favorite_topics": detect_favorite_topics(messages, weights),
            "emotional_triggers": detect_emotional_triggers(messages, emotions),
            "time_patterns": detect_time_patterns(timestamps, len(messages)),
            "recurring_tasks": detect_recurring_tasks(messages),
            "pattern_detection_timestamp": len(messages) > 0
        }
        
        logger.debug("All patterns detected successfully")
        return patterns
    
    except Exception as e:
        logger.error(f"Error detecting all patterns: {e}")
        return {"topics": [], "triggers": {}, "time_patterns": {}, "recurring_tasks": []}
