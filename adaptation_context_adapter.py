"""Adaptation Engine - Phase 3 context adapter."""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class ContextAdapter:
    """Match response style to context."""
    
    def __init__(self):
        """Initialize context adapter."""
        self.context_cache = {}
    
    def analyze_time_of_day(self, timestamp: float = None) -> Dict:
        """
        Analyze time of day and adjust accordingly.
        
        Returns:
            Dict with time analysis
        """
        try:
            import datetime
            
            if timestamp is None:
                now = datetime.datetime.now()
            else:
                now = datetime.datetime.fromtimestamp(timestamp)
            
            hour = now.hour
            
            time_context = {
                "hour": hour,
                "period": None,
                "energy_level": 0.5
            }
            
            if 5 <= hour < 12:
                time_context["period"] = "morning"
                time_context["energy_level"] = 0.4
            elif 12 <= hour < 17:
                time_context["period"] = "afternoon"
                time_context["energy_level"] = 0.7
            elif 17 <= hour < 21:
                time_context["period"] = "evening"
                time_context["energy_level"] = 0.6
            else:
                time_context["period"] = "night"
                time_context["energy_level"] = 0.3
            
            return time_context
        
        except Exception as e:
            logger.error(f"Error analyzing time: {e}")
            return {"hour": 0, "period": "unknown", "energy_level": 0.5}
    
    def analyze_recent_interactions(self, user_memory: Dict = None) -> Dict:
        """
        Analyze recent conversation patterns.
        
        Returns:
            Dict with interaction analysis
        """
        if not user_memory or not isinstance(user_memory, dict):
            return {"recent_topic": None, "conversation_length": 0, "engagement": 0.5}
        
        try:
            short_term = user_memory.get("short_term", [])
            
            interaction_analysis = {
                "recent_topic": None,
                "conversation_length": len(short_term),
                "engagement": 0.5,
                "sentiment_trend": "neutral"
            }
            
            if short_term:
                # Get last few messages
                recent = short_term[-3:]
                if recent:
                    last_msg = recent[-1]
                    if isinstance(last_msg, dict):
                        interaction_analysis["recent_topic"] = last_msg.get("content", "")[:50]
                
                # Calculate engagement
                interaction_analysis["engagement"] = min(1.0, len(short_term) / 20)
            
            # Sentiment trend
            sentiments = user_memory.get("sentiments", {})
            if sentiments:
                main_sentiment = max(sentiments, key=sentiments.get) if sentiments else "neutral"
                interaction_analysis["sentiment_trend"] = main_sentiment
            
            return interaction_analysis
        
        except Exception as e:
            logger.error(f"Error analyzing interactions: {e}")
            return {"recent_topic": None, "conversation_length": 0, "engagement": 0.5}
    
    def check_topic_sensitivity(self, topic: str = None, user_memory: Dict = None) -> float:
        """
        Check if current topic is sensitive for user.
        
        Returns:
            Sensitivity score [0, 1]
        """
        if not topic:
            return 0.0
        
        user_memory = user_memory or {}
        
        try:
            sensitivity = 0.0
            
            # Check against user's known sensitivities
            profile = user_memory.get("profile", {})
            sensitivities = user_memory.get("sensitivities", [])
            
            topic_lower = topic.lower()
            
            for sensitivity_topic in sensitivities:
                if sensitivity_topic in topic_lower:
                    sensitivity = 0.9
                    break
            
            # Common sensitive topics
            sensitive_words = [
                "health", "money", "death", "illness", "family",
                "relationship", "failure", "discrimination"
            ]
            
            for word in sensitive_words:
                if word in topic_lower:
                    sensitivity = max(sensitivity, 0.6)
            
            return min(1.0, sensitivity)
        
        except Exception as e:
            logger.error(f"Error checking topic sensitivity: {e}")
            return 0.0
    
    def adapt_to_context(
        self,
        current_message: str,
        user_memory: Dict = None,
        timestamp: float = None,
        recent_mood: str = "neutral"
    ) -> Dict:
        """
        Comprehensive context adaptation.
        
        Args:
            current_message: Current user message
            user_memory: User memory dict
            timestamp: Message timestamp
            recent_mood: Recent mood
        
        Returns:
            Complete context adaptation
        """
        user_memory = user_memory or {}
        
        try:
            # Analyze all contexts
            time_context = self.analyze_time_of_day(timestamp)
            interaction_context = self.analyze_recent_interactions(user_memory)
            topic_sensitivity = self.check_topic_sensitivity(current_message, user_memory)
            
            adaptation = {
                "time_context": time_context,
                "interaction_context": interaction_context,
                "topic_sensitivity": topic_sensitivity,
                "recommended_formality": 0.5,
                "recommended_pace": "normal",
                "recommended_depth": 0.5
            }
            
            # Formality adjustment by time
            if time_context["period"] in ["night", "morning"]:
                adaptation["recommended_formality"] -= 0.2
            
            # Pace adjustment by engagement
            if interaction_context["engagement"] > 0.7:
                adaptation["recommended_pace"] = "conversational"
            elif interaction_context["engagement"] < 0.3:
                adaptation["recommended_pace"] = "structured"
            
            # Depth adjustment by sentiment
            if interaction_context["sentiment_trend"] == "positive":
                adaptation["recommended_depth"] = 0.7
            elif interaction_context["sentiment_trend"] == "negative":
                adaptation["recommended_depth"] = 0.4
            
            # Sensitivity override
            if topic_sensitivity > 0.7:
                adaptation["recommended_formality"] = max(0.3, adaptation["recommended_formality"])
            
            return adaptation
        
        except Exception as e:
            logger.error(f"Error adapting to context: {e}")
            return {
                "time_context": {},
                "interaction_context": {},
                "topic_sensitivity": 0.0,
                "recommended_formality": 0.5,
                "recommended_pace": "normal",
                "recommended_depth": 0.5
            }
