# core/memory_core.py
"""
Enhanced Memory Core with Phase 2 Pattern Detection.
Importance-based memory scoring with emotional + repetition + recency weights.
"""

import logging
import time
from typing import Dict, Optional

from core.memory_classifier import classify_memory
from core.memory_compressor import compress_memory
from memory.configuration import (
    MAX_MEMORY_INPUT_LENGTH,
    PREFERENCE_SCORE_THRESHOLD,
    PERSISTENT_SCORE_THRESHOLD,
    MemoryLifecycle,
    has_explicit_memory_marker,
    infer_domain,
    is_transient_input,
)
from memory.models import MemoryDomain
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
    extract_patterns: bool = True,
    domain=None,
) -> Dict:
    """
    Main memory processing pipeline with Phase 2 enhancements.
    
    Args:
        user_message: User's message
        extract_patterns: Whether to extract behavioral patterns
        
    Returns:
        Memory processing data with importance score
    """
    
    if not isinstance(user_message, str) or not user_message.strip():
        return {
            "type": "general",
            "category": "Fact",
            "domain": infer_domain("", domain).value,
            "importance": 0.0,
            "should_store": False,
            "lifecycle": MemoryLifecycle.TEMPORARY.value,
            "reason": "empty",
        }

    user_message = user_message[:MAX_MEMORY_INPUT_LENGTH].strip()
    memory_type = classify_memory(user_message)
    compressed_memory = compress_memory(user_message)
    topic = extract_topic_from_message(user_message)
    score = importance_score(user_message, topic=topic)
    explicit_memory = has_explicit_memory_marker(user_message) or "favorite" in user_message.lower()
    transient = is_transient_input(user_message)
    resolved_domain = infer_domain(user_message, domain)

    if extract_patterns:
        detector = get_pattern_detector()
        detector.process_conversation(
            user_message,
            ai_response="",
            subject_tags=[topic],
            timestamp=time.time(),
        )

    persistent_signal = memory_type in {"profile", "preference", "goal", "project", "skill", "fact"}
    should_store = not transient and (
        explicit_memory
        or resolved_domain is MemoryDomain.VENNELA_CORE
        or score >= PERSISTENT_SCORE_THRESHOLD
        or (persistent_signal and score >= PREFERENCE_SCORE_THRESHOLD)
    )
    lifecycle = MemoryLifecycle.PERSISTENT if should_store else (
        MemoryLifecycle.TEMPORARY if transient else MemoryLifecycle.CANDIDATE
    )
    category = {
        "profile": "Profile",
        "preference": "Preference",
        "goal": "Goal",
        "project": "Project",
        "skill": "Skill",
        "event": "Event",
        "fact": "Fact",
    }.get(memory_type, "Fact")
    memory_data = {
        "type": memory_type,
        "category": category,
        "compressed": compressed_memory,
        "topic": topic,
        "domain": resolved_domain.value,
        "importance": score,
        "should_store": should_store,
        "lifecycle": lifecycle.value,
        "importance_category": (
            "critical" if score >= 0.7 else
            "high" if score >= 0.6 else
            "medium" if score >= 0.4 else
            "low"
        ),
    }
    logger.info(
        "Memory processed: %s (%.2f) - %s",
        memory_data["lifecycle"],
        score,
        topic,
    )
    return memory_data