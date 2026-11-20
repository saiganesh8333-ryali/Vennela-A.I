"""Adaptation Engine - Phase 3 mood detector."""

import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


def detect_emotion_from_text(text: str) -> Tuple[str, float]:
    """
    Detect emotion from text content.
    
    Args:
        text: User message
    
    Returns:
        Tuple of (emotion, confidence)
    """
    if not text or not isinstance(text, str):
        return "neutral", 0.0
    
    try:
        lower_text = text.lower()
        
        # Emotion keywords with confidence weights
        emotion_keywords = {
            "happy": {
                "keywords": ["happy", "great", "awesome", "excellent", "wonderful", "love", "excited"],
                "confidence": 0.8
            },
            "sad": {
                "keywords": ["sad", "depressed", "unhappy", "miserable", "grief", "lost", "miss"],
                "confidence": 0.8
            },
            "angry": {
                "keywords": ["angry", "furious", "frustrated", "annoyed", "mad", "rage", "hate"],
                "confidence": 0.85
            },
            "anxious": {
                "keywords": ["worried", "anxious", "stressed", "nervous", "scared", "afraid", "concerned"],
                "confidence": 0.75
            },
            "confident": {
                "keywords": ["sure", "confident", "certain", "determined", "ready", "capable"],
                "confidence": 0.7
            },
            "confused": {
                "keywords": ["confused", "lost", "unclear", "puzzled", "bewildered", "uncertain"],
                "confidence": 0.7
            }
        }
        
        detected_emotions = {}
        
        for emotion, data in emotion_keywords.items():
            keyword_count = 0
            for keyword in data["keywords"]:
                keyword_count += lower_text.count(keyword)
            
            if keyword_count > 0:
                detected_emotions[emotion] = {
                    "count": keyword_count,
                    "confidence": min(1.0, data["confidence"] * keyword_count / 2)
                }
        
        # Get highest confidence emotion
        if detected_emotions:
            best_emotion = max(
                detected_emotions.items(),
                key=lambda x: x[1]["confidence"]
            )
            return best_emotion[0], best_emotion[1]["confidence"]
        
        return "neutral", 0.0
    
    except Exception as e:
        logger.error(f"Error detecting emotion: {e}")
        return "neutral", 0.0


def detect_mood_from_metadata(message_metadata: Dict) -> Tuple[str, float]:
    """
    Detect mood from message metadata.
    
    Args:
        message_metadata: Metadata dict
    
    Returns:
        Tuple of (mood, confidence)
    """
    if not message_metadata or not isinstance(message_metadata, dict):
        return "neutral", 0.0
    
    try:
        mood = "neutral"
        confidence = 0.0
        
        # Response time analysis
        response_time = message_metadata.get("response_time_seconds", 0)
        if response_time < 5:
            mood = "engaged"
            confidence = 0.5
        elif response_time > 300:
            mood = "delayed"
            confidence = 0.5
        
        # Message length patterns
        msg_len = message_metadata.get("message_length", 0)
        if msg_len < 5:
            if mood == "neutral":
                mood = "disengaged"
            confidence = max(confidence, 0.4)
        
        # Editing behavior
        if message_metadata.get("was_edited", False):
            confidence = max(confidence, 0.6)
        
        return mood, confidence
    
    except Exception as e:
        logger.error(f"Error detecting mood from metadata: {e}")
        return "neutral", 0.0


def detect_sensitivity_level(user_memory: Dict, current_message: str = "") -> float:
    """
    Detect current sensitivity level based on patterns and context.
    
    Args:
        user_memory: User memory dict
        current_message: Current user message
    
    Returns:
        Sensitivity level [0, 1]
    """
    if not user_memory or not isinstance(user_memory, dict):
        return 0.5
    
    try:
        sensitivity = 0.5
        
        # Check emotional patterns
        emotions = user_memory.get("emotions", {})
        if emotions:
            distressed_emotions = ["sad", "angry", "anxious"]
            distressed_count = sum(
                emotions.get(e, 0) for e in distressed_emotions
            )
            total_emotions = sum(emotions.values())
            
            if total_emotions > 0:
                sensitivity = min(1.0, distressed_count / total_emotions)
        
        # Check current message for sensitive content
        if current_message:
            sensitive_keywords = ["sad", "angry", "hurt", "pain", "worry", "fear"]
            for keyword in sensitive_keywords:
                if keyword in current_message.lower():
                    sensitivity = max(sensitivity, 0.8)
                    break
        
        return max(0.0, min(1.0, sensitivity))
    
    except Exception as e:
        logger.error(f"Error detecting sensitivity: {e}")
        return 0.5


def real_time_mood_detection(
    current_message: str,
    message_metadata: Dict = None,
    user_memory: Dict = None
) -> Dict:
    """
    Detect mood in real-time from current message.
    
    Args:
        current_message: Current user message
        message_metadata: Optional metadata
        user_memory: Optional user memory
    
    Returns:
        Dict with mood analysis
    """
    message_metadata = message_metadata or {}
    user_memory = user_memory or {}
    
    try:
        # Detect emotion from text
        emotion, emotion_confidence = detect_emotion_from_text(current_message)
        
        # Detect mood from metadata
        mood, metadata_confidence = detect_mood_from_metadata(message_metadata)
        
        # Detect sensitivity
        sensitivity = detect_sensitivity_level(user_memory, current_message)
        
        # Combine analyses
        result = {
            "primary_emotion": emotion,
            "emotion_confidence": emotion_confidence,
            "metadata_mood": mood,
            "metadata_confidence": metadata_confidence,
            "sensitivity_level": sensitivity,
            "overall_mood": emotion if emotion_confidence > metadata_confidence else mood,
            "overall_confidence": max(emotion_confidence, metadata_confidence)
        }
        
        logger.debug(f"Detected mood: {result['overall_mood']} ({result['overall_confidence']:.2f})")
        return result
    
    except Exception as e:
        logger.error(f"Error in real-time mood detection: {e}")
        return {
            "primary_emotion": "neutral",
            "emotion_confidence": 0.0,
            "metadata_mood": "neutral",
            "metadata_confidence": 0.0,
            "sensitivity_level": 0.5,
            "overall_mood": "neutral",
            "overall_confidence": 0.0
        }
