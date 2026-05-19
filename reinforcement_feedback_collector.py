"""Reinforcement layer - Phase 1 feedback collector."""

import logging
from typing import Dict, List, Optional
from reinforcement_reward_scorer import score_response

logger = logging.getLogger(__name__)


def collect_implicit_feedback(message_metadata: Dict) -> Dict:
    """
    Extract implicit feedback from message metadata.
    
    Args:
        message_metadata: Metadata about the message
    
    Returns:
        Dict with implicit feedback signals
    """
    if not message_metadata or not isinstance(message_metadata, dict):
        return {"signal": None, "confidence": 0.0}
    
    try:
        feedback = {
            "signal": None,
            "confidence": 0.0,
            "indicators": []
        }
        
        # Continuation signal
        if message_metadata.get("is_continuation", False):
            feedback["signal"] = "positive_continuation"
            feedback["confidence"] = 0.7
            feedback["indicators"].append("User continued conversation")
        
        # Message length patterns
        msg_len = message_metadata.get("message_length", 0)
        if msg_len < 5:
            feedback["signal"] = "low_engagement"
            feedback["confidence"] = 0.6
            feedback["indicators"].append("Very short message")
        elif msg_len > 200:
            feedback["signal"] = "high_engagement"
            feedback["confidence"] = 0.6
            feedback["indicators"].append("Detailed response")
        
        # Response time patterns
        response_time = message_metadata.get("response_time_seconds", 0)
        if response_time < 5:
            feedback["indicators"].append("Quick response")
        elif response_time > 300:
            feedback["indicators"].append("Delayed response")
        
        # Editing patterns
        if message_metadata.get("was_edited", False):
            feedback["indicators"].append("Message was edited")
            feedback["confidence"] = min(1.0, feedback["confidence"] + 0.1)
        
        return feedback
    
    except Exception as e:
        logger.error(f"Error collecting implicit feedback: {e}")
        return {"signal": None, "confidence": 0.0, "indicators": []}


def collect_explicit_feedback(user_input: str, feedback_type: str = None) -> Dict:
    """
    Extract explicit feedback from user input or endpoint.
    
    Args:
        user_input: User message or rating input
        feedback_type: Type of feedback (rating/keyword/command)
    
    Returns:
        Dict with explicit feedback
    """
    if not user_input or not isinstance(user_input, str):
        return {"rating": None, "type": None, "keywords": [], "confidence": 0.0}
    
    try:
        lower_input = user_input.lower()
        feedback = {
            "rating": None,
            "type": feedback_type or "keyword_detection",
            "keywords": [],
            "confidence": 0.0
        }
        
        # Rating patterns
        rating_map = {
            "excellent": 1.0,
            "great": 0.8,
            "good": 0.6,
            "okay": 0.3,
            "okay": 0.2,
            "bad": -0.4,
            "terrible": -0.8,
            "useless": -1.0
        }
        
        for keyword, rating in rating_map.items():
            if keyword in lower_input:
                feedback["rating"] = rating
                feedback["keywords"].append(keyword)
                feedback["confidence"] = 0.85
                break
        
        # Explicit rating commands (/rate 0.5)
        if "/rate " in lower_input:
            try:
                rating_str = lower_input.split("/rate ")[1].split()[0]
                rating = float(rating_str)
                feedback["rating"] = max(-1.0, min(1.0, rating))
                feedback["confidence"] = 1.0
                feedback["type"] = "explicit_rating"
            except (ValueError, IndexError):
                pass
        
        # Correction keywords
        if "wrong" in lower_input or "incorrect" in lower_input or "mistake" in lower_input:
            feedback["keywords"].append("correction")
            feedback["confidence"] = max(feedback["confidence"], 0.75)
        
        return feedback
    
    except Exception as e:
        logger.error(f"Error collecting explicit feedback: {e}")
        return {"rating": None, "type": None, "keywords": [], "confidence": 0.0}


def process_feedback(
    message: str,
    previous_response: str = "",
    metadata: Dict = None,
    explicit_input: str = None
) -> Dict:
    """
    Combine implicit and explicit feedback into single score.
    
    Args:
        message: User message
        previous_response: Previous AI response
        metadata: Message metadata
        explicit_input: Optional explicit feedback
    
    Returns:
        Combined feedback with reinforcement score
    """
    try:
        metadata = metadata or {}
        
        # Get implicit feedback
        implicit = collect_implicit_feedback(metadata)
        
        # Get explicit feedback
        explicit = collect_explicit_feedback(explicit_input or message) if explicit_input else {"rating": None, "type": None, "keywords": [], "confidence": 0.0}
        
        # Get response score
        response_score = score_response(message, previous_response, metadata.get("is_continuation", False))
        
        # Combine scores
        final_score = response_score["score"]
        if explicit.get("rating") is not None:
            final_score = (final_score * 0.5) + (explicit["rating"] * 0.5)
        
        return {
            "reinforcement_score": final_score,
            "implicit_feedback": implicit,
            "explicit_feedback": explicit,
            "response_score": response_score,
            "combined_confidence": max(implicit.get("confidence", 0), explicit.get("confidence", 0))
        }
    
    except Exception as e:
        logger.error(f"Error processing feedback: {e}")
        return {
            "reinforcement_score": 0.0,
            "implicit_feedback": {},
            "explicit_feedback": {},
            "response_score": {},
            "combined_confidence": 0.0
        }


def get_feedback_summary(feedback_list: List[Dict]) -> Dict:
    """
    Generate summary statistics from feedback list.
    
    Args:
        feedback_list: List of feedback dicts
    
    Returns:
        Summary statistics
    """
    if not feedback_list or not isinstance(feedback_list, list):
        return {"avg_score": 0.0, "total_count": 0, "positive_count": 0, "negative_count": 0}
    
    try:
        scores = [f.get("reinforcement_score", 0) for f in feedback_list]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        positive_count = sum(1 for s in scores if s > 0.2)
        negative_count = sum(1 for s in scores if s < -0.2)
        
        return {
            "avg_score": avg_score,
            "total_count": len(feedback_list),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "min_score": min(scores) if scores else 0.0,
            "max_score": max(scores) if scores else 0.0
        }
    
    except Exception as e:
        logger.error(f"Error generating feedback summary: {e}")
        return {"avg_score": 0.0, "total_count": 0, "positive_count": 0, "negative_count": 0}
