"""
Phase G: Predictive Intent Engine - Complete Implementation
Pattern detection, predictive intent, and context prediction
"""

import logging
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """Common user intents."""
    GREETING = "greeting"
    QUERY = "query"
    COMMAND = "command"
    CONVERSATION = "conversation"
    HELP = "help"
    FEEDBACK = "feedback"
    CREATIVE = "creative"
    ANALYTICAL = "analytical"


@dataclass
class Pattern:
    """Detected pattern in user behavior."""
    pattern_id: str
    user_messages: List[str]
    responses: List[str]
    predicted_intent: IntentType
    confidence: float
    frequency: int = 1


@dataclass
class PredictionResult:
    """Result from intent prediction."""
    predicted_intent: IntentType
    confidence: float
    supporting_patterns: List[Pattern] = field(default_factory=list)
    suggested_context: Dict = field(default_factory=dict)


class PatternDetector:
    """Detects patterns in user interactions."""
    
    def __init__(self):
        """Initialize pattern detector."""
        self.patterns: Dict[str, Pattern] = {}
        self.interaction_history: List[Tuple[str, str]] = []
        logger.info("Pattern detector initialized")
    
    def detect_patterns(self, messages: List[str], responses: List[str]) -> List[Pattern]:
        """Detect patterns in message/response pairs.
        
        Args:
            messages: List of user messages
            responses: List of responses
            
        Returns:
            List of detected patterns
        """
        detected = []
        
        for i in range(len(messages) - 1):
            # Look for message pairs that follow a pattern
            msg1, msg2 = messages[i:i+2]
            resp1, resp2 = responses[i:i+2]
            
            # Detect intent patterns
            intent = self._classify_intent(msg1)
            
            # Check if this pattern has been seen before
            pattern_key = f"{msg1.lower()[:50]}:{intent.value}"
            
            if pattern_key in self.patterns:
                self.patterns[pattern_key].frequency += 1
            else:
                pattern = Pattern(
                    pattern_id=pattern_key,
                    user_messages=[msg1, msg2],
                    responses=[resp1, resp2],
                    predicted_intent=intent,
                    confidence=self._calculate_confidence(msg1),
                )
                self.patterns[pattern_key] = pattern
                detected.append(pattern)
        
        return detected
    
    def _classify_intent(self, message: str) -> IntentType:
        """Classify message intent.
        
        Args:
            message: User message
            
        Returns:
            Classified intent
        """
        lower_msg = message.lower()
        
        if any(word in lower_msg for word in ["hello", "hi", "hey", "greetings"]):
            return IntentType.GREETING
        elif any(word in lower_msg for word in ["what", "how", "why", "where", "when"]):
            return IntentType.QUERY
        elif any(word in lower_msg for word in ["do", "make", "create", "help", "assist"]):
            return IntentType.COMMAND
        elif any(word in lower_msg for word in ["think", "analyze", "evaluate"]):
            return IntentType.ANALYTICAL
        elif any(word in lower_msg for word in ["write", "create", "imagine", "story"]):
            return IntentType.CREATIVE
        else:
            return IntentType.CONVERSATION
    
    def _calculate_confidence(self, message: str) -> float:
        """Calculate confidence in intent classification.
        
        Args:
            message: User message
            
        Returns:
            Confidence score 0-1
        """
        # Confidence based on message clarity and length
        if len(message) < 3:
            return 0.4
        elif len(message) < 10:
            return 0.6
        else:
            return 0.85


class PredictiveIntentEngine:
    """Predicts user intent based on patterns."""
    
    def __init__(self):
        """Initialize predictive intent engine."""
        self.pattern_detector = PatternDetector()
        self.prediction_history: List[PredictionResult] = []
        self.intent_weights = {intent: 0.0 for intent in IntentType}
        logger.info("Predictive intent engine initialized")
    
    def predict_intent(self, message: str, context: Optional[Dict] = None) -> PredictionResult:
        """Predict user intent.
        
        Args:
            message: User message
            context: Optional context (previous messages, etc)
            
        Returns:
            PredictionResult with predicted intent
        """
        # Detect intent
        intent = self.pattern_detector._classify_intent(message)
        confidence = self.pattern_detector._calculate_confidence(message)
        
        # Apply context weighting
        if context and "conversation_topic" in context:
            confidence *= 1.1  # Boost confidence with context
        
        confidence = min(1.0, confidence)
        
        # Find supporting patterns
        supporting = [p for p in self.pattern_detector.patterns.values() 
                     if p.predicted_intent == intent][:3]
        
        result = PredictionResult(
            predicted_intent=intent,
            confidence=confidence,
            supporting_patterns=supporting,
            suggested_context=context or {}
        )
        
        self.prediction_history.append(result)
        self.intent_weights[intent] += confidence
        
        logger.info(f"Intent predicted: {intent.value} (confidence: {confidence:.2f})")
        return result
    
    def get_intent_probabilities(self) -> Dict[str, float]:
        """Get probability distribution over intents.
        
        Returns:
            Intent -> probability mapping
        """
        total = sum(self.intent_weights.values())
        if total == 0:
            return {intent.value: 1.0 / len(IntentType) for intent in IntentType}
        
        return {intent.value: weight / total 
                for intent, weight in self.intent_weights.items()}


class ContextPredictor:
    """Predicts contextual information for next interaction."""
    
    def __init__(self):
        """Initialize context predictor."""
        self.context_history: List[Dict] = []
        self.topic_continuity = {}
        logger.info("Context predictor initialized")
    
    def predict_next_context(self, current_context: Dict) -> Dict:
        """Predict next interaction context.
        
        Args:
            current_context: Current interaction context
            
        Returns:
            Predicted context for next interaction
        """
        predicted = current_context.copy()
        
        # Topic continuity
        if "topic" in current_context:
            topic = current_context["topic"]
            if topic not in self.topic_continuity:
                self.topic_continuity[topic] = 1
            else:
                self.topic_continuity[topic] += 1
            
            # Predict same topic continuation
            if self.topic_continuity[topic] > 2:
                predicted["likely_topic_continuation"] = topic
        
        # Add temporal context
        if "timestamp" in current_context:
            predicted["time_of_day"] = self._predict_time_of_day()
        
        # Add user state predictions
        predicted["predicted_user_state"] = self._predict_user_state(current_context)
        
        return predicted
    
    def _predict_time_of_day(self) -> str:
        """Predict relevant time of day."""
        from datetime import datetime
        hour = datetime.now().hour
        
        if 6 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 21:
            return "evening"
        else:
            return "night"
    
    def _predict_user_state(self, context: Dict) -> Dict:
        """Predict user's emotional/cognitive state.
        
        Args:
            context: Current context
            
        Returns:
            Predicted user state
        """
        state = {
            "engagement_level": "medium",
            "cognitive_load": "moderate",
            "time_available": "medium",
        }
        
        # Adjust based on context
        if "conversation_length" in context:
            length = context["conversation_length"]
            if length > 10:
                state["engagement_level"] = "high"
                state["cognitive_load"] = "high"
            elif length < 2:
                state["engagement_level"] = "low"
        
        return state


# Singleton instances
_pattern_detector_instance: Optional[PatternDetector] = None
_predictive_intent_engine_instance: Optional[PredictiveIntentEngine] = None
_context_predictor_instance: Optional[ContextPredictor] = None


def get_pattern_detector() -> PatternDetector:
    """Get singleton pattern detector."""
    global _pattern_detector_instance
    if _pattern_detector_instance is None:
        _pattern_detector_instance = PatternDetector()
    return _pattern_detector_instance


def get_predictive_intent_engine() -> PredictiveIntentEngine:
    """Get singleton predictive intent engine."""
    global _predictive_intent_engine_instance
    if _predictive_intent_engine_instance is None:
        _predictive_intent_engine_instance = PredictiveIntentEngine()
    return _predictive_intent_engine_instance


def get_context_predictor() -> ContextPredictor:
    """Get singleton context predictor."""
    global _context_predictor_instance
    if _context_predictor_instance is None:
        _context_predictor_instance = ContextPredictor()
    return _context_predictor_instance
