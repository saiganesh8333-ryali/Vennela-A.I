# core/memory_core.py
"""
🧠 Enhanced Memory Core with Phase 2 Pattern Detection
Importance-based memory scoring with emotional + repetition + recency weights.
"""

import logging
import time
from typing import Dict, Optional

from core.memory_classifier import classify_memory
from core.memory_compressor import compress_memory
from memory_importance_calculator import get_importance_calculator
from pattern_detector import get_pattern_detector

logger = logging.getLogger(__name__)


def importance_score(text: str, topic: Optional[str] = None) -> float:
    """
    Calculate importance score using Phase 2 advanced scoring.
    
    Formula: (emotional * 0.4) + (repetition * 0.3) + (recency * 0.3)
    
    Args:
        text: User message/memory
        topic: Topic category for repetition tracking
        
    Returns:
        Importance score 0.0-1.0 (normalized)
    """
    if not text or not isinstance(text, str):
        return 0.0
    
    calculator = get_importance_calculator()
    
    # Calculate using Phase 2 algorithm
    score = calculator.calculate_importance(
        text,
        timestamp=time.time(),
        topic=topic or "general"
    )
    
    return score


def extract_topic_from_message(user_message: str) -> str:
    """
    Extract primary topic from message for pattern tracking.
    
    Looks for academic subjects, interests, etc.
    """
    text_lower = user_message.lower()
    
    # Common topics to detect
    topics = {
        "physics": ["physics", "mechanics", "quantum", "relativity"],
        "math": ["math", "calculus", "algebra", "equation"],
        "robotics": ["robot", "robotics", "automation", "servo"],
        "programming": ["code", "python", "java", "program", "function"],
        "biology": ["biology", "genetics", "cell", "organism"],
        "chemistry": ["chemistry", "reaction", "molecule", "compound"],
        "history": ["history", "war", "civilization", "ancient"],
        "literature": ["book", "novel", "poetry", "story"],
    }
    
    for topic, keywords in topics.items():
        for keyword in keywords:
            if keyword in text_lower:
                return topic
    
    return "general"


def process_memory(
    user_message: str,
    extract_patterns: bool = True
) -> Dict:
    """
    Main memory processing pipeline with Phase 2 enhancements.
    
    Args:
        user_message: User's message
        extract_patterns: Whether to extract behavioral patterns
        
    Returns:
        Memory processing data with importance score
    """
    
    if not user_message:
        return {}
    
    try:
        
        # STEP 1: CLASSIFY
        memory_type = classify_memory(user_message)
        
        # STEP 2: COMPRESS
        compressed_memory = compress_memory(user_message)
        
        # STEP 3: EXTRACT TOPIC
        topic = extract_topic_from_message(user_message)
        
        # STEP 4: IMPORTANCE (Phase 2 - Advanced)
        score = importance_score(user_message, topic=topic)
        
        # STEP 5: PATTERN DETECTION (Phase 2)
        if extract_patterns:
            detector = get_pattern_detector()
            detector.process_conversation(
                user_message,
                ai_response="",  # Will be filled by caller
                subject_tags=[topic],
                timestamp=time.time()
            )
        
        # STEP 6: DECISION
        # Threshold: 0.4 = store (more aggressive than old 4/10 = 0.4)
        should_store = score >= 0.4
        
        memory_data = {
            "type": memory_type,
            "compressed": compressed_memory,
            "topic": topic,
            "importance": score,
            "should_store": should_store,
            "importance_category": (
                "critical" if score >= 0.8 else
                "high" if score >= 0.6 else
                "medium" if score >= 0.4 else
                "low"
            )
        }
        
        logger.info(
            f"🧠 Memory processed: {memory_data['importance_category'].upper()} "
            f"({score:.2f}) - {topic}"
        )
        
        return memory_data
    
    except Exception as e:
        
        logger.error(f"Memory processing failed: {e}")
        
        return {}