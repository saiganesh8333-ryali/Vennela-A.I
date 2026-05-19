"""Reinforcement layer - Phase 1 reward scorer."""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


def calculate_engagement_score(message: str, previous_response: str = "") -> float:
    """Score engagement [-0.5, 0.5] based on length, sentiment, continuation."""
    if not message or not isinstance(message, str):
        return 0.0
    
    try:
        score = 0.0
        msg_len = len(message.strip())
        
        if msg_len < 10:
            score -= 0.1
        elif msg_len > 100:
            score += 0.1
        
        if '?' in message:
            score += 0.15
        if '!' in message:
            score += 0.1
        if previous_response and message.lower() != previous_response.lower():
            score += 0.05
        
        return max(-0.5, min(0.5, score))
    except Exception as e:
        logger.error(f"Error calculating engagement score: {e}")
        return 0.0


def calculate_keyword_score(message: str) -> float:
    """Score [-0.5, 0.5] based on positive/negative keywords."""
    if not message or not isinstance(message, str):
        return 0.0
    
    try:
        score = 0.0
        lower_msg = message.lower()
        
        positive = ["good", "great", "excellent", "awesome", "perfect", "thanks", "thank you", "appreciate", "love", "like"]
        for keyword in positive:
            if keyword in lower_msg:
                score += 0.25
        
        negative = ["wrong", "incorrect", "error", "mistake", "bad", "don't like", "hate", "terrible", "useless"]
        for keyword in negative:
            if keyword in lower_msg:
                score -= 0.15
        
        return max(-0.5, min(0.5, score))
    except Exception as e:
        logger.error(f"Error calculating keyword score: {e}")
        return 0.0


def calculate_implicit_score(message: str, is_continuation: bool = False, message_quality: str = "normal") -> float:
    """Score [-0.2, 0.2] based on implicit engagement patterns."""
    try:
        score = 0.0
        
        if is_continuation:
            score += 0.1
        
        if message_quality == "short" and len(message.strip()) < 10:
            score -= 0.1
        elif message_quality == "detailed" and len(message.strip()) > 50:
            score += 0.1
        
        return max(-0.2, min(0.2, score))
    except Exception as e:
        logger.error(f"Error calculating implicit score: {e}")
        return 0.0


def score_response(message: str, previous_response: str = "", is_continuation: bool = False, metadata: Dict = None) -> Dict:
    """Calculate composite reward score [-1, 1] for a response."""
    if not message or not isinstance(message, str):
        return {"score": 0.0, "components": {"engagement": 0.0, "keywords": 0.0, "implicit": 0.0}, "reasoning": "Invalid message"}
    
    try:
        metadata = metadata or {}
        
        engagement = calculate_engagement_score(message, previous_response)
        keywords = calculate_keyword_score(message)
        implicit = calculate_implicit_score(message, is_continuation, metadata.get("quality", "normal"))
        
        score = engagement * 0.4 + keywords * 0.35 + implicit * 0.25
        score = max(-1.0, min(1.0, score))
        
        return {
            "score": score,
            "components": {"engagement": engagement, "keywords": keywords, "implicit": implicit},
            "reasoning": _generate_reasoning(score, engagement, keywords, implicit)
        }
    except Exception as e:
        logger.error(f"Error scoring response: {e}")
        return {"score": 0.0, "components": {"engagement": 0.0, "keywords": 0.0, "implicit": 0.0}, "reasoning": f"Error: {str(e)}"}


def _generate_reasoning(score: float, engagement: float, keywords: float, implicit: float) -> str:
    """Generate reasoning for score."""
    reasons = []
    
    if engagement > 0.2:
        reasons.append("High engagement")
    elif engagement < -0.2:
        reasons.append("Low engagement")
    
    if keywords > 0.2:
        reasons.append("Positive keywords")
    elif keywords < -0.2:
        reasons.append("Negative keywords")
    
    if score > 0.5:
        return f"Excellent: {', '.join(reasons) if reasons else 'Generally positive'}"
    elif score > 0.2:
        return f"Good: {', '.join(reasons) if reasons else 'Positive engagement'}"
    elif score > -0.2:
        return "Neutral: Mixed feedback"
    elif score > -0.5:
        return f"Poor: {', '.join(reasons) if reasons else 'Negative engagement'}"
    else:
        return f"Very Poor: {', '.join(reasons) if reasons else 'Strongly negative'}"


def batch_score_responses(messages: List[str], context: Dict = None) -> List[Dict]:
    """Score multiple responses efficiently."""
    if not messages or not isinstance(messages, list):
        return []
    
    context = context or {}
    results = []
    
    for i, msg in enumerate(messages):
        prev_response = messages[i - 1] if i > 0 else ""
        result = score_response(msg, prev_response, context.get("is_continuation", False))
        results.append(result)
    
    return results
