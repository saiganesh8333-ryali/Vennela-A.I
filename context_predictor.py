"""
🔮 Context Predictor
Predicts user's next intent and context for proactive responses.

Uses:
- Conversation history
- User patterns (from Phase 2)
- Memory importance scores
- Temporal patterns
"""

import logging
import time
from typing import Dict, List, Tuple, Optional
from collections import Counter, defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class IntentPredictor:
    """Predict user's next intent from conversation patterns."""
    
    def __init__(self):
        """Initialize intent prediction."""
        self.intent_sequences = []  # List of [intent1, intent2, intent3] sequences
        self.intent_transitions = defaultdict(Counter)  # Intent -> next_intent counts
        self.intent_frequency = Counter()  # Intent -> frequency
    
    def record_intent(self, intent: str) -> None:
        """Record user intent."""
        self.intent_frequency[intent] += 1
        
        # Track transitions
        if self.intent_sequences and self.intent_sequences[-1]:
            prev_intent = self.intent_sequences[-1][-1]
            self.intent_transitions[prev_intent][intent] += 1
        
        # Add to current sequence
        if not self.intent_sequences or len(self.intent_sequences[-1]) >= 5:
            self.intent_sequences.append([])
        self.intent_sequences[-1].append(intent)
    
    def predict_next_intent(self, current_intent: str) -> List[Tuple[str, float]]:
        """
        Predict next intent given current one.
        
        Returns: List of (intent, probability) tuples
        """
        if current_intent not in self.intent_transitions:
            return []
        
        transitions = self.intent_transitions[current_intent]
        total = sum(transitions.values())
        
        # Return sorted by probability
        predictions = [
            (intent, count / total)
            for intent, count in transitions.most_common(5)
        ]
        
        return predictions
    
    def get_top_intents(self, n: int = 5) -> List[Tuple[str, int]]:
        """Get most common intents."""
        return self.intent_frequency.most_common(n)
    
    def extract_pattern(self) -> Dict:
        """Extract intent pattern."""
        return {
            "top_intents": dict(self.get_top_intents()),
            "intent_count": len(self.intent_frequency),
            "total_transitions": sum(
                sum(v.values()) for v in self.intent_transitions.values()
            )
        }


class ContextPredictor:
    """Predict user context from messages."""
    
    def __init__(self):
        """Initialize context prediction."""
        self.context_types = Counter()  # Context type -> frequency
        self.context_sequences = []  # Sequences of contexts
        self.temporal_context = defaultdict(list)  # Time -> contexts
    
    def detect_context(self, text: str) -> str:
        """
        Detect context from message.
        
        Context types: learning, debugging, explaining, planning, reviewing, etc.
        """
        text_lower = text.lower()
        
        if any(w in text_lower for w in ["error", "bug", "problem", "not working", "wrong"]):
            return "debugging"
        elif any(w in text_lower for w in ["explain", "why", "how", "what is", "teach me"]):
            return "learning"
        elif any(w in text_lower for w in ["show me", "example", "demo", "code"]):
            return "code_example"
        elif any(w in text_lower for w in ["plan", "schedule", "organize", "structure"]):
            return "planning"
        elif any(w in text_lower for w in ["check", "review", "evaluate", "correct"]):
            return "reviewing"
        elif any(w in text_lower for w in ["help", "assist", "how do", "can you"]):
            return "help_request"
        else:
            return "general_conversation"
    
    def record_context(self, context: str) -> None:
        """Record a context."""
        self.context_types[context] += 1
        
        # Track sequences
        if self.context_sequences and self.context_sequences[-1]:
            self.context_sequences[-1].append(context)
        else:
            self.context_sequences.append([context])
        
        # Track temporal
        hour = datetime.now().hour
        self.temporal_context[hour].append(context)
    
    def predict_next_context(self, current_context: str) -> Optional[str]:
        """Predict next context given current."""
        for seq in self.context_sequences[-10:]:  # Check last 10 sequences
            try:
                idx = seq.index(current_context)
                if idx + 1 < len(seq):
                    return seq[idx + 1]
            except ValueError:
                continue
        
        return None
    
    def extract_pattern(self) -> Dict:
        """Extract context pattern."""
        return {
            "context_distribution": dict(self.context_types),
            "context_count": len(self.context_types),
            "temporal_patterns": {
                hour: Counter(contexts).most_common(3)
                for hour, contexts in self.temporal_context.items()
            }
        }


class ResponseContextBuilder:
    """Build response context from user and system state."""
    
    def __init__(self):
        """Initialize context builder."""
        self.history = []  # Recent conversation
        self.max_history = 10
    
    def add_exchange(self, user_msg: str, assistant_msg: str) -> None:
        """Add user-assistant exchange to history."""
        self.history.append({
            "user": user_msg,
            "assistant": assistant_msg,
            "timestamp": time.time()
        })
        
        # Keep only recent exchanges
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
    
    def get_recent_context(self, n_exchanges: int = 3) -> str:
        """Get recent conversation context as string."""
        recent = self.history[-n_exchanges:]
        context = "\n".join(
            f"User: {ex['user']}\nAssistant: {ex['assistant']}"
            for ex in recent
        )
        return context or "No recent context"
    
    def get_conversation_length(self) -> int:
        """Get number of exchanges so far."""
        return len(self.history)
    
    def get_topic_from_history(self) -> str:
        """Extract main topic from conversation history."""
        if not self.history:
            return "general"
        
        # Combine all recent messages
        all_text = " ".join(
            ex["user"] + " " + ex["assistant"]
            for ex in self.history[-3:]
        )
        
        # Simple topic detection
        topics = {
            "physics": ["physics", "mechanics", "quantum"],
            "robotics": ["robot", "automation", "servo"],
            "programming": ["code", "function", "variable"],
            "math": ["equation", "calculus", "algebra"],
        }
        
        for topic, keywords in topics.items():
            if any(k in all_text.lower() for k in keywords):
                return topic
        
        return "general"


class PredictionEngine:
    """Main prediction engine combining all predictors."""
    
    def __init__(self):
        """Initialize prediction engine."""
        self.intent_predictor = IntentPredictor()
        self.context_predictor = ContextPredictor()
        self.context_builder = ResponseContextBuilder()
        
        self.prediction_accuracy = []  # Track accuracy
        self.version = 1
    
    def process_exchange(
        self,
        user_message: str,
        assistant_response: str,
        user_intent: Optional[str] = None,
        confidence: float = 0.5
    ) -> None:
        """
        Process a conversation exchange for learning.
        
        Args:
            user_message: What user said
            assistant_response: What AI responded
            user_intent: Detected user intent (if known)
            confidence: Confidence in the detection
        """
        # Record context
        context = self.context_predictor.detect_context(user_message)
        self.context_predictor.record_context(context)
        
        # Record intent if known
        if user_intent:
            self.intent_predictor.record_intent(user_intent)
        
        # Add to history
        self.context_builder.add_exchange(user_message, assistant_response)
        
        self.version += 1
    
    def predict_next_turn(self) -> Dict:
        """
        Predict what happens in the next turn.
        
        Returns prediction context for AI to prepare response
        """
        # Get conversation state
        conv_length = self.context_builder.get_conversation_length()
        topic = self.context_builder.get_topic_from_history()
        recent_context = self.context_builder.get_recent_context(3)
        
        # Predict next intent and context
        # (Would need current intent to predict next - would be passed in)
        
        prediction = {
            "conversation_length": conv_length,
            "main_topic": topic,
            "recent_context": recent_context,
            "confidence": min(self.version / 10.0, 1.0),
            "timestamp": time.time()
        }
        
        return prediction
    
    def record_prediction_result(
        self,
        predicted: str,
        actual: str,
        prediction_type: str = "intent"
    ) -> None:
        """
        Record if a prediction was correct for learning.
        
        Args:
            predicted: What we predicted
            actual: What actually happened
            prediction_type: Type of prediction (intent, context, etc.)
        """
        was_correct = predicted.lower() == actual.lower()
        self.prediction_accuracy.append({
            "type": prediction_type,
            "correct": was_correct,
            "confidence": 0.5,  # Would be set during prediction
            "timestamp": time.time()
        })
    
    def get_prediction_accuracy(
        self,
        prediction_type: Optional[str] = None
    ) -> float:
        """
        Get prediction accuracy.
        
        Returns: Percentage of correct predictions (0-1)
        """
        if not self.prediction_accuracy:
            return 0.0
        
        if prediction_type:
            relevant = [
                p for p in self.prediction_accuracy
                if p["type"] == prediction_type
            ]
        else:
            relevant = self.prediction_accuracy
        
        if not relevant:
            return 0.0
        
        correct = sum(1 for p in relevant if p["correct"])
        return correct / len(relevant)
    
    def extract_all_patterns(self) -> Dict:
        """Extract all prediction patterns."""
        return {
            "intent_patterns": self.intent_predictor.extract_pattern(),
            "context_patterns": self.context_predictor.extract_pattern(),
            "prediction_accuracy": {
                "overall": self.get_prediction_accuracy(),
                "intent": self.get_prediction_accuracy("intent"),
                "context": self.get_prediction_accuracy("context"),
            },
            "metadata": {
                "version": self.version,
                "conversation_exchanges": self.context_builder.get_conversation_length()
            }
        }
    
    def get_adaptation_hints(self) -> List[str]:
        """Generate hints for system adaptation."""
        hints = []
        
        # Intent hints
        top_intents = self.intent_predictor.get_top_intents(3)
        if top_intents:
            hints.append(f"User frequently needs: {', '.join(i[0] for i in top_intents)}")
        
        # Context hints
        context_dist = self.context_predictor.context_types
        if context_dist:
            top_context = context_dist.most_common(1)[0][0]
            hints.append(f"Most common context: {top_context}")
        
        # Accuracy hints
        accuracy = self.get_prediction_accuracy()
        if accuracy > 0.6:
            hints.append("✅ Predictions becoming reliable")
        
        return hints


# Singleton instance
_engine = None


def get_prediction_engine() -> PredictionEngine:
    """Get or create prediction engine instance."""
    global _engine
    if _engine is None:
        _engine = PredictionEngine()
    return _engine
