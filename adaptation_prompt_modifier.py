"""Adaptation Engine - Phase 3 prompt modifier."""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class PromptModifier:
    """Build dynamic system prompts with personality and context."""
    
    def __init__(self):
        """Initialize prompt modifier."""
        self.base_system_prompt = (
            "You are a helpful, adaptive AI assistant that learns and adapts to user preferences. "
            "You adjust your communication style to match the user's needs and personality."
        )
    
    def build_tone_instruction(self, tone: float) -> str:
        """
        Build tone instruction [-1 formal to 1 casual].
        
        Args:
            tone: Tone value [-1, 1]
        
        Returns:
            Tone instruction string
        """
        if tone < -0.6:
            return "Use formal, professional language with proper grammar and complete sentences."
        elif tone < -0.2:
            return "Use slightly formal but friendly tone. Be professional yet approachable."
        elif tone < 0.2:
            return "Use neutral, balanced tone. Be clear and respectful."
        elif tone < 0.6:
            return "Use casual, friendly tone. Be conversational and warm."
        else:
            return "Use very casual, relaxed tone. Feel free to use colloquial language and emojis."
    
    def build_length_instruction(self, length: float) -> str:
        """
        Build length instruction [-1 concise to 1 detailed].
        
        Args:
            length: Length value [-1, 1]
        
        Returns:
            Length instruction string
        """
        if length < -0.6:
            return "Keep responses very brief and concise, max 1-2 sentences."
        elif length < -0.2:
            return "Provide brief but clear responses, typically 2-3 sentences."
        elif length < 0.2:
            return "Provide balanced responses with necessary detail."
        elif length < 0.6:
            return "Provide detailed responses with explanations and examples."
        else:
            return "Provide comprehensive, in-depth responses with multiple examples and deep analysis."
    
    def build_humor_instruction(self, humor_level: float) -> str:
        """
        Build humor instruction [0 no humor to 1 very humorous].
        
        Args:
            humor_level: Humor level [0, 1]
        
        Returns:
            Humor instruction string
        """
        if humor_level < 0.2:
            return "Be serious and avoid humor."
        elif humor_level < 0.4:
            return "Be straightforward with minimal humor."
        elif humor_level < 0.6:
            return "Use occasional light humor appropriately."
        elif humor_level < 0.8:
            return "Use humor frequently to make responses engaging."
        else:
            return "Be playful and use humor liberally to entertain the user."
    
    def build_emotional_support_instruction(self, support_level: float) -> str:
        """
        Build emotional support instruction [0 technical to 1 very supportive].
        
        Args:
            support_level: Support level [0, 1]
        
        Returns:
            Support instruction string
        """
        if support_level < 0.3:
            return "Focus on facts and technical accuracy. Minimal emotional engagement."
        elif support_level < 0.5:
            return "Be helpful and respectful. Include some acknowledgment of user feelings."
        elif support_level < 0.7:
            return "Be empathetic and supportive. Acknowledge emotions and validate concerns."
        else:
            return "Be deeply empathetic and supportive. Actively listen and provide emotional comfort."
    
    def build_user_preference_section(self, user_profile: Dict) -> str:
        """Build section with specific user preferences."""
        if not user_profile or not isinstance(user_profile, dict):
            return ""
        
        try:
            preferences = []
            
            # Speaking style preferences
            speaking_style = user_profile.get("speaking_style", {})
            if speaking_style.get("emoji_count", 0) > 5:
                preferences.append("The user enjoys using emojis.")
            
            if speaking_style.get("abbreviations", []):
                preferences.append(f"The user commonly uses abbreviations like: {', '.join(speaking_style['abbreviations'][:3])}")
            
            # Response preferences
            response_prefs = user_profile.get("preferred_responses", {})
            if response_prefs.get("preferred_length"):
                preferences.append(f"The user prefers {response_prefs['preferred_length']} responses.")
            
            # Topics
            topics = user_profile.get("routines", {}).get("favorite_topics", [])
            if topics:
                preferences.append(f"The user is interested in: {', '.join(topics[:3])}")
            
            if not preferences:
                return ""
            
            return "\n".join([
                "User Preferences:",
                "\n".join([f"- {pref}" for pref in preferences])
            ])
        
        except Exception as e:
            logger.error(f"Error building user preferences: {e}")
            return ""
    
    def build_context_section(self, context: Dict) -> str:
        """Build section with current context."""
        if not context or not isinstance(context, dict):
            return ""
        
        try:
            context_parts = []
            
            mood = context.get("overall_mood", "neutral")
            if mood != "neutral":
                context_parts.append(f"The user appears to be feeling {mood}.")
            
            sensitivity = context.get("sensitivity_level", 0.5)
            if sensitivity > 0.7:
                context_parts.append("Be especially sensitive and supportive in your response.")
            
            interaction_ctx = context.get("interaction_context", {})
            engagement = interaction_ctx.get("engagement", 0.5)
            if engagement > 0.7:
                context_parts.append("The user is highly engaged; feel free to explore topics in depth.")
            elif engagement < 0.3:
                context_parts.append("Keep the conversation concise and focused.")
            
            if not context_parts:
                return ""
            
            return "\n".join([
                "Current Context:",
                "\n".join([f"- {part}" for part in context_parts])
            ])
        
        except Exception as e:
            logger.error(f"Error building context section: {e}")
            return ""
    
    def modify_prompt(
        self,
        base_prompt: str = None,
        personality: Dict = None,
        user_profile: Dict = None,
        context: Dict = None
    ) -> str:
        """
        Build complete modified system prompt.
        
        Args:
            base_prompt: Optional base prompt
            personality: Personality adjustments dict
            user_profile: User profile dict
            context: Context dict
        
        Returns:
            Modified system prompt
        """
        base_prompt = base_prompt or self.base_system_prompt
        personality = personality or {}
        user_profile = user_profile or {}
        context = context or {}
        
        try:
            prompt_parts = [base_prompt, ""]
            
            # Add tone instruction
            tone = personality.get("tone", 0.0)
            prompt_parts.append(self.build_tone_instruction(tone))
            
            # Add length instruction
            length = personality.get("length", 0.0)
            prompt_parts.append(self.build_length_instruction(length))
            
            # Add humor instruction
            humor = personality.get("humor", 0.5)
            prompt_parts.append(self.build_humor_instruction(humor))
            
            # Add support instruction
            support = personality.get("emotional_support", 0.5)
            prompt_parts.append(self.build_emotional_support_instruction(support))
            
            # Add user preferences section
            user_section = self.build_user_preference_section(user_profile)
            if user_section:
                prompt_parts.extend(["", user_section])
            
            # Add context section
            context_section = self.build_context_section(context)
            if context_section:
                prompt_parts.extend(["", context_section])
            
            # Add closing instruction
            prompt_parts.extend([
                "",
                "Maintain this adaptive approach throughout the conversation, "
                "adjusting as you learn more about the user."
            ])
            
            return "\n".join(prompt_parts)
        
        except Exception as e:
            logger.error(f"Error modifying prompt: {e}")
            return base_prompt
