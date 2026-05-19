"""Adaptation Engine - Phase 3 personality engine."""

import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class PersonalityEngine:
    """Adjust AI personality based on user profile and mood."""
    
    def __init__(self):
        """Initialize personality engine."""
        self.base_personality = {
            "tone": 0.0,
            "length": 0.0,
            "humor": 0.5,
            "emotional_support": 0.5
        }
    
    def adjust_tone(
        self,
        user_profile: Dict,
        current_mood: str = "neutral",
        formality_override: float = None
    ) -> float:
        """
        Adjust tone from formal (-1) to casual (1).
        
        Args:
            user_profile: User profile dict
            current_mood: Current mood (happy, sad, angry, neutral)
            formality_override: Optional override value
        
        Returns:
            Tone adjustment [-1, 1]
        """
        try:
            if formality_override is not None:
                return max(-1.0, min(1.0, formality_override))
            
            tone = 0.0
            
            # Base on speaking style
            speaking_style = user_profile.get("speaking_style", {})
            formality = speaking_style.get("formality", 0.5)
            
            if formality > 0.7:
                tone -= 0.5
            elif formality < 0.3:
                tone += 0.5
            
            # Adjust by mood
            mood_adjustments = {
                "happy": 0.3,
                "sad": -0.2,
                "angry": -0.3,
                "anxious": -0.2,
                "neutral": 0.0
            }
            
            tone += mood_adjustments.get(current_mood, 0.0)
            
            return max(-1.0, min(1.0, tone))
        
        except Exception as e:
            logger.error(f"Error adjusting tone: {e}")
            return 0.0
    
    def adjust_length(
        self,
        user_profile: Dict,
        current_mood: str = "neutral",
        context: str = "general"
    ) -> float:
        """
        Adjust response length from concise (-1) to detailed (1).
        
        Args:
            user_profile: User profile dict
            current_mood: Current mood
            context: Response context
        
        Returns:
            Length adjustment [-1, 1]
        """
        try:
            length = 0.0
            
            # Base on preferences
            preferences = user_profile.get("preferred_responses", {})
            pref_length = preferences.get("preferred_length", "medium")
            
            if pref_length == "concise":
                length -= 0.5
            elif pref_length == "detailed":
                length += 0.5
            
            # Adjust by mood
            if current_mood == "sad":
                length += 0.2
            elif current_mood == "angry":
                length -= 0.2
            
            # Context adjustments
            if context == "urgent":
                length -= 0.3
            elif context == "exploratory":
                length += 0.2
            
            return max(-1.0, min(1.0, length))
        
        except Exception as e:
            logger.error(f"Error adjusting length: {e}")
            return 0.0
    
    def adjust_humor(
        self,
        user_profile: Dict,
        current_mood: str = "neutral"
    ) -> float:
        """
        Adjust humor level [0, 1].
        
        Args:
            user_profile: User profile dict
            current_mood: Current mood
        
        Returns:
            Humor level [0, 1]
        """
        try:
            humor = 0.5
            
            # Base on preferences
            preferences = user_profile.get("preferred_responses", {})
            base_humor = preferences.get("humor_level", 0.5)
            humor = base_humor
            
            # Reduce humor when user is sad or angry
            if current_mood in ["sad", "angry", "anxious"]:
                humor = max(0.0, humor - 0.3)
            elif current_mood == "happy":
                humor = min(1.0, humor + 0.2)
            
            return max(0.0, min(1.0, humor))
        
        except Exception as e:
            logger.error(f"Error adjusting humor: {e}")
            return 0.5
    
    def adjust_emotional_support(
        self,
        user_profile: Dict,
        current_mood: str = "neutral",
        sensitivity_level: float = 0.5
    ) -> float:
        """
        Adjust emotional support level [0, 1].
        
        Args:
            user_profile: User profile dict
            current_mood: Current mood
            sensitivity_level: User sensitivity [0, 1]
        
        Returns:
            Emotional support level [0, 1]
        """
        try:
            support = 0.5
            
            # Increase support when user is distressed
            if current_mood in ["sad", "anxious", "angry"]:
                support = max(support, 0.7)
            
            # Factor in sensitivity
            if sensitivity_level > 0.7:
                support += 0.2
            
            # Reduce for very positive mood
            if current_mood == "happy":
                support = min(support, 0.6)
            
            return max(0.0, min(1.0, support))
        
        except Exception as e:
            logger.error(f"Error adjusting emotional support: {e}")
            return 0.5
    
    def calculate_personality(
        self,
        user_profile: Dict,
        current_mood: str = "neutral",
        context: Dict = None
    ) -> Dict:
        """
        Calculate complete personality adjustments.
        
        Args:
            user_profile: User profile dict
            current_mood: Current mood
            context: Optional context dict
        
        Returns:
            Dict with all personality adjustments
        """
        context = context or {}
        
        try:
            sensitivity = context.get("sensitivity_level", 0.5)
            context_type = context.get("type", "general")
            
            personality = {
                "tone": self.adjust_tone(user_profile, current_mood),
                "length": self.adjust_length(user_profile, current_mood, context_type),
                "humor": self.adjust_humor(user_profile, current_mood),
                "emotional_support": self.adjust_emotional_support(
                    user_profile,
                    current_mood,
                    sensitivity
                ),
                "mood": current_mood,
                "sensitivity": sensitivity
            }
            
            logger.debug(f"Personality calculated for mood: {current_mood}")
            return personality
        
        except Exception as e:
            logger.error(f"Error calculating personality: {e}")
            return self.base_personality
