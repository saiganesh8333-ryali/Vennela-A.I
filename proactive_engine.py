"""
Phase 4: Proactive Intelligence Engine
Human-in-the-loop suggestion system with safety guardrails
"""
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict


@dataclass
class Suggestion:
    """Smart suggestion with metadata"""
    text: str
    type: str  # study_timing, memory_reminder, progress, guidance
    confidence: float  # 0.0 to 1.0
    urgency: float  # 0.0 to 1.0
    relevance: float  # 0.0 to 1.0
    interruption_cost: float  # 0.0 to 1.0
    timestamp: float
    user_topic: str = ""
    context_type: str = ""
    
    def score(self) -> float:
        """Calculate suggestion score"""
        return (
            self.relevance * 0.4 +
            self.urgency * 0.3 +
            self.confidence * 0.2 -
            self.interruption_cost * 0.1
        )


class IntentForecaster:
    """Predict user's likely next intent"""
    
    def __init__(self):
        self.intent_sequences = defaultdict(list)  # topic -> [intents]
        self.intent_frequency = defaultdict(int)
        self.last_intents = []
        
    def add_interaction(self, topic: str, intent: str, success: bool = True):
        """Record user interaction"""
        if success:
            self.intent_sequences[topic].append(intent)
            self.intent_frequency[f"{topic}:{intent}"] += 1
        self.last_intents.append((topic, intent, time.time()))
        if len(self.last_intents) > 50:
            self.last_intents.pop(0)
    
    def predict_next_intents(self, current_topic: str, 
                             current_intent: str) -> List[Tuple[str, float]]:
        """Predict top 3 likely next intents"""
        if current_topic not in self.intent_sequences:
            return [
                ("ask_clarification", 0.3),
                ("request_example", 0.25),
                ("ask_related", 0.2)
            ]
        
        sequence = self.intent_sequences[current_topic]
        predictions = defaultdict(float)
        
        # Look at sequences following current intent
        for i, intent in enumerate(sequence):
            if intent == current_intent and i + 1 < len(sequence):
                next_intent = sequence[i + 1]
                freq = self.intent_frequency.get(f"{current_topic}:{next_intent}", 1)
                predictions[next_intent] += freq / (i + 1)  # decay by position
        
        # Normalize and return top 3
        total = sum(predictions.values()) or 1
        result = [(k, v/total) for k, v in predictions.items()]
        result.sort(key=lambda x: x[1], reverse=True)
        return result[:3]


class SuggestionRanker:
    """Score and rank suggestions"""
    
    def __init__(self):
        self.suggestion_acceptance = defaultdict(list)  # suggestion_type -> [accepted]
        self.min_score = 0.5
        
    def score_suggestion(self, suggestion: Suggestion) -> float:
        """Calculate suggestion score"""
        score = suggestion.score()
        # Penalize low-confidence suggestions
        if suggestion.confidence < 0.3:
            score *= 0.7
        return score
    
    def rank_suggestions(self, suggestions: List[Suggestion], 
                        max_show: int = 2) -> List[Suggestion]:
        """Rank and filter suggestions"""
        scored = [(s, self.score_suggestion(s)) for s in suggestions]
        scored = [(s, score) for s, score in scored if score >= self.min_score]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in scored[:max_show]]
    
    def record_acceptance(self, suggestion_type: str, accepted: bool):
        """Track suggestion acceptance for improvement"""
        self.suggestion_acceptance[suggestion_type].append(accepted)
        if len(self.suggestion_acceptance[suggestion_type]) > 100:
            self.suggestion_acceptance[suggestion_type].pop(0)


class TimingOptimizer:
    """Decide when to show suggestions"""
    
    def __init__(self):
        self.last_suggestion_time = {}  # suggestion_type -> timestamp
        self.min_interval_seconds = 30  # min time between suggestions
        self.max_per_hour = 3  # max suggestions per hour
        self.hourly_suggestions = defaultdict(list)  # hour -> [timestamps]
        self.user_busy = False
        self.interruption_cooldown = 0
        
    def should_show_suggestion(self, suggestion_type: str) -> bool:
        """Check if we should show this suggestion now"""
        if self.user_busy or self.interruption_cooldown > time.time():
            return False
        
        # Check min interval
        last_time = self.last_suggestion_time.get(suggestion_type, 0)
        if time.time() - last_time < self.min_interval_seconds:
            return False
        
        # Check hourly limit
        current_hour = datetime.now().hour
        hour_suggestions = self.hourly_suggestions[current_hour]
        hour_suggestions = [t for t in hour_suggestions if time.time() - t < 3600]
        if len(hour_suggestions) >= self.max_per_hour:
            return False
        
        return True
    
    def mark_suggestion_shown(self, suggestion_type: str):
        """Record that suggestion was shown"""
        self.last_suggestion_time[suggestion_type] = time.time()
        current_hour = datetime.now().hour
        self.hourly_suggestions[current_hour].append(time.time())
    
    def set_user_busy(self, busy: bool, duration_seconds: int = 0):
        """Mark user as busy (don't interrupt)"""
        self.user_busy = busy
        if duration_seconds > 0:
            self.interruption_cooldown = time.time() + duration_seconds


class SafetyGuardrails:
    """Prevent manipulative or harmful suggestions"""
    
    def __init__(self):
        self.blocked_words = {
            "must", "should", "forced", "guilty", "lazy", "stupid",
            "failing", "addiction", "desperate", "need me"
        }
        self.suggestion_history = []
        
    def is_safe(self, suggestion: Suggestion) -> bool:
        """Check if suggestion is safe and ethical"""
        text = suggestion.text.lower()
        
        # Check for blocked words
        for word in self.blocked_words:
            if word in text:
                return False
        
        # Check for guilt-inducing patterns
        if any(x in text for x in ["why haven't you", "you never", "you always"]):
            return False
        
        # Check for dependency patterns
        if any(x in text for x in ["need me", "depend on", "can't do without"]):
            return False
        
        # Check for emotional manipulation
        if any(x in text for x in ["cry", "heartbroken", "devastated", "ruin"]):
            return False
        
        return True
    
    def filter_suggestions(self, suggestions: List[Suggestion]) -> List[Suggestion]:
        """Filter out unsafe suggestions"""
        return [s for s in suggestions if self.is_safe(s)]


class ProactiveEngine:
    """Main orchestrator for Phase 4"""
    
    def __init__(self):
        self.forecaster = IntentForecaster()
        self.ranker = SuggestionRanker()
        self.timer = TimingOptimizer()
        self.safety = SafetyGuardrails()
        self.context_state = {}
        self.last_user_message = ""
        self.last_topic = ""
        
    def generate_suggestions(self, current_topic: str, 
                            current_intent: str,
                            user_patterns: Dict) -> List[Suggestion]:
        """Generate proactive suggestions"""
        suggestions = []
        current_time = time.time()
        
        # Get predicted next intents
        predicted_intents = self.forecaster.predict_next_intents(
            current_topic, current_intent
        )
        
        # Create suggestions from predictions
        for intent, confidence in predicted_intents:
            if intent == "ask_clarification":
                suggestion = Suggestion(
                    text=f"Would you like me to explain that more clearly?",
                    type="clarification",
                    confidence=confidence,
                    urgency=0.3,
                    relevance=0.7,
                    interruption_cost=0.2,
                    timestamp=current_time,
                    user_topic=current_topic,
                    context_type=current_intent
                )
                suggestions.append(suggestion)
            
            elif intent == "request_example":
                suggestion = Suggestion(
                    text=f"Want to see a practical example?",
                    type="example",
                    confidence=confidence,
                    urgency=0.4,
                    relevance=0.8,
                    interruption_cost=0.15,
                    timestamp=current_time,
                    user_topic=current_topic,
                    context_type=current_intent
                )
                suggestions.append(suggestion)
            
            elif intent == "ask_related":
                suggestion = Suggestion(
                    text=f"This connects to {current_topic}. Interested?",
                    type="connection",
                    confidence=confidence,
                    urgency=0.25,
                    relevance=0.6,
                    interruption_cost=0.25,
                    timestamp=current_time,
                    user_topic=current_topic,
                    context_type=current_intent
                )
                suggestions.append(suggestion)
        
        # Add study timing suggestions
        if user_patterns.get("study_time_confidence", 0) > 0.6:
            suggestion = Suggestion(
                text=f"You usually study {current_topic} now. Continue?",
                type="study_timing",
                confidence=user_patterns.get("study_time_confidence", 0.6),
                urgency=0.5,
                relevance=0.85,
                interruption_cost=0.1,
                timestamp=current_time,
                user_topic=current_topic,
                context_type="timing"
            )
            suggestions.append(suggestion)
        
        # Add progress tracking suggestions
        if user_patterns.get("progress_tracking", False):
            suggestion = Suggestion(
                text=f"You've made great progress! Want a progress report?",
                type="progress",
                confidence=0.7,
                urgency=0.3,
                relevance=0.65,
                interruption_cost=0.2,
                timestamp=current_time,
                user_topic=current_topic,
                context_type="tracking"
            )
            suggestions.append(suggestion)
        
        return suggestions
    
    def filter_and_rank(self, suggestions: List[Suggestion]) -> List[Suggestion]:
        """Apply all filtering and ranking"""
        # Safety first
        safe_suggestions = self.safety.filter_suggestions(suggestions)
        
        # Rank by score
        ranked = self.ranker.rank_suggestions(safe_suggestions, max_show=2)
        
        return ranked
    
    def should_show_suggestions(self) -> bool:
        """Check if we should show suggestions now"""
        # Don't suggest if user just got one
        if len(self.ranker.suggestion_acceptance) > 0:
            recent = any(
                time.time() - t < 60 
                for t in sum(self.ranker.suggestion_acceptance.values(), [])
            )
            if recent:
                return False
        
        return True
    
    def get_proactive_suggestions(self, current_topic: str, 
                                 current_intent: str,
                                 user_patterns: Dict) -> List[Dict]:
        """Get suggestions to show to user"""
        if not self.should_show_suggestions():
            return []
        
        # Generate candidates
        suggestions = self.generate_suggestions(
            current_topic, current_intent, user_patterns
        )
        
        # Filter and rank
        best = self.filter_and_rank(suggestions)
        
        # Check timing
        result = []
        for suggestion in best:
            if self.timer.should_show_suggestion(suggestion.type):
                self.timer.mark_suggestion_shown(suggestion.type)
                result.append({
                    "text": suggestion.text,
                    "type": suggestion.type,
                    "confidence": suggestion.confidence,
                    "score": suggestion.score()
                })
        
        return result
    
    def record_interaction(self, topic: str, intent: str, 
                         accepted: bool, user_patterns: Dict = None):
        """Record user interaction for learning"""
        self.forecaster.add_interaction(topic, intent, success=accepted)
        self.ranker.record_acceptance(intent, accepted)
        self.last_user_message = topic
        self.last_topic = topic
    
    def set_user_busy(self, busy: bool, duration: int = 0):
        """Mark user as busy"""
        self.timer.set_user_busy(busy, duration)


# Singleton
_proactive_engine = None

def get_proactive_engine() -> ProactiveEngine:
    """Get or create proactive engine"""
    global _proactive_engine
    if _proactive_engine is None:
        _proactive_engine = ProactiveEngine()
    return _proactive_engine

