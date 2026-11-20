"""
Phase F: Adaptive Personality Layer - Complete Implementation
Mood detection, personality engine, and adaptive prompt modification
"""

import logging
import json
from typing import Optional, Dict
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class MoodType(Enum):
    """User mood types."""
    HAPPY = "happy"
    EXCITED = "excited"
    CALM = "calm"
    FRUSTRATED = "frustrated"
    SAD = "sad"
    NEUTRAL = "neutral"


class PersonalityTraits(Enum):
    """Personality traits for Vennela."""
    FRIENDLY = "friendly"
    PROFESSIONAL = "professional"
    HUMOROUS = "humorous"
    EMPATHETIC = "empathetic"
    ANALYTICAL = "analytical"
    CREATIVE = "creative"


@dataclass
class MoodContext:
    """Context for mood detection."""
    text: str
    tone_indicators: list = None
    sentiment_score: float = 0.5  # 0=negative, 1=positive
    intensity: float = 0.5  # 0=low, 1=high
    timestamp: datetime = None


@dataclass
class PersonalityProfile:
    """Vennela's personality configuration."""
    active_traits: Dict[str, float] = None  # Trait -> weight (0-1)
    communication_style: str = "friendly"
    humor_level: float = 0.5
    formality: float = 0.5
    empathy_level: float = 0.8


class MoodDetector:
    """Detects user mood from text."""
    
    def __init__(self):
        """Initialize mood detector."""
        self.mood_indicators = {
            "happy": ["great", "love", "awesome", "wonderful", "excited", "happy"],
            "frustrated": ["angry", "frustrated", "annoyed", "upset", "hate"],
            "sad": ["sad", "depressed", "unhappy", "down", "miserable"],
            "calm": ["calm", "peaceful", "relaxed", "serene"],
        }
        logger.info("Mood detector initialized")
    
    def detect_mood(self, text: str) -> MoodType:
        """Detect user mood from text.
        
        Args:
            text: User input text
            
        Returns:
            Detected MoodType
        """
        lower_text = text.lower()
        scores = {}
        
        for mood, indicators in self.mood_indicators.items():
            matches = sum(1 for indicator in indicators if indicator in lower_text)
            scores[mood] = matches
        
        if not any(scores.values()):
            return MoodType.NEUTRAL
        
        detected_mood = max(scores, key=scores.get)
        mood_map = {
            "happy": MoodType.HAPPY,
            "frustrated": MoodType.FRUSTRATED,
            "sad": MoodType.SAD,
            "calm": MoodType.CALM,
        }
        
        return mood_map.get(detected_mood, MoodType.NEUTRAL)


class PersonalityEngine:
    """Manages Vennela's personality traits and adaptation."""
    
    def __init__(self):
        """Initialize personality engine."""
        self.profile = PersonalityProfile(
            active_traits={
                "friendly": 0.9,
                "empathetic": 0.8,
                "professional": 0.7,
                "humorous": 0.5,
                "analytical": 0.6,
                "creative": 0.6,
            }
        )
        self.adaptation_history = []
        logger.info("Personality engine initialized")
    
    def adapt_to_mood(self, mood: MoodType) -> None:
        """Adapt personality traits based on detected mood.
        
        Args:
            mood: User's detected mood
        """
        if mood == MoodType.FRUSTRATED:
            self.profile.empathy_level = 0.95
            self.profile.humor_level = 0.2
            self.profile.communication_style = "understanding"
        
        elif mood == MoodType.HAPPY:
            self.profile.humor_level = 0.8
            self.profile.active_traits["creative"] = 0.9
            self.profile.communication_style = "engaging"
        
        elif mood == MoodType.SAD:
            self.profile.empathy_level = 1.0
            self.profile.humor_level = 0.1
            self.profile.communication_style = "supportive"
        
        else:
            self.profile.empathy_level = 0.8
            self.profile.humor_level = 0.5
            self.profile.communication_style = "friendly"
        
        self.adaptation_history.append({
            "mood": mood.value,
            "timestamp": datetime.now(),
            "traits": self.profile.active_traits.copy(),
        })
        
        logger.info(f"Personality adapted to mood: {mood.value}")
    
    def get_personality_prompt(self) -> str:
        """Generate system prompt based on current personality.
        
        Returns:
            Personality-based system prompt
        """
        traits_str = ", ".join([
            f"{trait.replace('_', ' ')}: {weight:.1f}"
            for trait, weight in self.profile.active_traits.items()
        ])
        
        return f"""You are Vennela, an adaptive AI assistant with the following personality:
- Communication style: {self.profile.communication_style}
- Empathy level: {self.profile.empathy_level:.1f}
- Humor level: {self.profile.humor_level:.1f}
- Active traits: {traits_str}

Adapt your responses to match this personality while remaining helpful and honest."""
    
    def get_profile(self) -> PersonalityProfile:
        """Get current personality profile."""
        return self.profile


class AdaptivePromptModifier:
    """Modifies prompts based on personality and context."""
    
    def __init__(self, personality_engine: PersonalityEngine):
        """Initialize prompt modifier.
        
        Args:
            personality_engine: PersonalityEngine instance
        """
        self.personality_engine = personality_engine
        self.mood_detector = MoodDetector()
        logger.info("Adaptive prompt modifier initialized")
    
    def modify_prompt(self, base_prompt: str, user_message: str) -> str:
        """Modify prompt based on personality and mood.
        
        Args:
            base_prompt: Original system prompt
            user_message: User's current message
            
        Returns:
            Adapted system prompt
        """
        # Detect mood
        mood = self.mood_detector.detect_mood(user_message)
        self.personality_engine.adapt_to_mood(mood)
        
        # Get personality-based additions
        personality_prompt = self.personality_engine.get_personality_prompt()
        
        # Combine prompts
        adapted_prompt = f"{base_prompt}\n\n{personality_prompt}"
        
        # Add mood-specific instructions
        if mood != MoodType.NEUTRAL:
            adapted_prompt += f"\n\nUser mood appears to be: {mood.value}. Respond with appropriate empathy and tone."
        
        return adapted_prompt
    
    def get_tone_instructions(self, mood: MoodType) -> str:
        """Get tone instructions for specific mood.
        
        Args:
            mood: User mood
            
        Returns:
            Tone instructions to append to prompt
        """
        instructions = {
            MoodType.HAPPY: "Be enthusiastic, engaging, and match their positive energy.",
            MoodType.FRUSTRATED: "Be patient, empathetic, and help resolve their issue.",
            MoodType.SAD: "Be supportive, understanding, and offer encouragement.",
            MoodType.CALM: "Be clear, concise, and informative.",
            MoodType.NEUTRAL: "Be your normal helpful self.",
        }
        
        return instructions.get(mood, instructions[MoodType.NEUTRAL])


# Singleton instances
_mood_detector_instance: Optional[MoodDetector] = None
_personality_engine_instance: Optional[PersonalityEngine] = None
_adaptive_prompt_modifier_instance: Optional[AdaptivePromptModifier] = None


def get_mood_detector() -> MoodDetector:
    """Get singleton mood detector."""
    global _mood_detector_instance
    if _mood_detector_instance is None:
        _mood_detector_instance = MoodDetector()
    return _mood_detector_instance


def get_personality_engine() -> PersonalityEngine:
    """Get singleton personality engine."""
    global _personality_engine_instance
    if _personality_engine_instance is None:
        _personality_engine_instance = PersonalityEngine()
    return _personality_engine_instance


def get_adaptive_prompt_modifier() -> AdaptivePromptModifier:
    """Get singleton adaptive prompt modifier."""
    global _adaptive_prompt_modifier_instance
    if _adaptive_prompt_modifier_instance is None:
        modifier = AdaptivePromptModifier(get_personality_engine())
        _adaptive_prompt_modifier_instance = modifier
    return _adaptive_prompt_modifier_instance
