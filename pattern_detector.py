"""
🔍 Pattern Detector
Identifies behavioral patterns from conversation history.

Patterns detected:
- Study schedules (preferred times/days)
- Subject interests and anxiety levels
- Learning style preferences
- Communication patterns
- Activity patterns
"""

import logging
import time
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from collections import Counter

logger = logging.getLogger(__name__)


class SchedulePattern:
    """Detect when user prefers to study/work."""
    
    def __init__(self):
        """Initialize schedule tracking."""
        self.activity_hours = Counter()  # Hour -> count
        self.activity_days = Counter()   # Day of week -> count
        self.session_lengths = []        # List of session durations (minutes)
    
    def record_activity(self, timestamp: Optional[float] = None) -> None:
        """Record user activity."""
        if not timestamp:
            timestamp = time.time()
        
        dt = datetime.fromtimestamp(timestamp)
        self.activity_hours[dt.hour] += 1
        self.activity_days[dt.strftime("%A")] += 1
    
    def get_peak_hours(self, top_n: int = 3) -> List[Tuple[int, int]]:
        """Get most active hours."""
        return self.activity_hours.most_common(top_n)
    
    def get_peak_days(self, top_n: int = 2) -> List[Tuple[str, int]]:
        """Get most active days."""
        return self.activity_days.most_common(top_n)
    
    def extract_pattern(self) -> Dict:
        """Extract schedule pattern."""
        peak_hours = self.get_peak_hours()
        peak_days = self.get_peak_days()
        
        return {
            "peak_study_hours": [h for h, _ in peak_hours],
            "peak_study_days": [d for d, _ in peak_days],
            "hour_distribution": dict(self.activity_hours),
            "day_distribution": dict(self.activity_days)
        }


class InterestPattern:
    """Detect subject interests and engagement levels."""
    
    def __init__(self):
        """Initialize interest tracking."""
        self.subjects = Counter()           # Subject -> mention count
        self.subject_sentiment = {}         # Subject -> positive/negative score
        self.engagement_levels = {}         # Subject -> engagement score
    
    def record_mention(
        self,
        subject: str,
        sentiment: float = 0.5,
        engagement: float = 0.5
    ) -> None:
        """Record subject mention."""
        self.subjects[subject] += 1
        
        # Track sentiment
        if subject not in self.subject_sentiment:
            self.subject_sentiment[subject] = []
        self.subject_sentiment[subject].append(sentiment)
        
        # Track engagement
        if subject not in self.engagement_levels:
            self.engagement_levels[subject] = []
        self.engagement_levels[subject].append(engagement)
    
    def get_top_interests(self, top_n: int = 5) -> List[Tuple[str, int]]:
        """Get most mentioned subjects."""
        return self.subjects.most_common(top_n)
    
    def get_anxiety_levels(self) -> Dict[str, float]:
        """Get anxiety level per subject (0=calm, 1=anxious)."""
        anxiety = {}
        for subject, sentiments in self.subject_sentiment.items():
            avg_sentiment = sum(sentiments) / len(sentiments)
            anxiety[subject] = 1.0 - avg_sentiment  # Invert: low sentiment = high anxiety
        return anxiety
    
    def extract_pattern(self) -> Dict:
        """Extract interest pattern."""
        interests = dict(self.get_top_interests(10))
        anxiety = self.get_anxiety_levels()
        
        return {
            "top_interests": interests,
            "anxiety_levels": anxiety,
            "subject_count": len(self.subjects)
        }


class LearningStylePattern:
    """Detect how user prefers to learn."""
    
    def __init__(self):
        """Initialize learning style tracking."""
        self.style_preferences = Counter()  # Style -> count
        # Styles: visual, auditory, reading, interactive, example-based
    
    def record_preference(self, style: str) -> None:
        """Record learning style preference."""
        self.style_preferences[style] += 1
    
    def get_dominant_style(self) -> Optional[str]:
        """Get most preferred learning style."""
        if not self.style_preferences:
            return None
        return self.style_preferences.most_common(1)[0][0]
    
    def extract_pattern(self) -> Dict:
        """Extract learning style pattern."""
        return {
            "style_preferences": dict(self.style_preferences),
            "dominant_style": self.get_dominant_style()
        }


class CommunicationPattern:
    """Detect communication preferences."""
    
    def __init__(self):
        """Initialize communication tracking."""
        self.message_lengths = []         # Lengths of user messages
        self.response_expectations = {}   # Type -> expected response format
        self.formality_indicators = Counter()  # Casual vs formal
    
    def record_message(self, text: str) -> None:
        """Record message characteristics."""
        self.message_lengths.append(len(text.split()))
        
        # Track formality
        if "!" in text or "omg" in text.lower() or "wow" in text.lower():
            self.formality_indicators["casual"] += 1
        elif any(p in text for p in ["therefore", "however", "moreover"]):
            self.formality_indicators["formal"] += 1
    
    def get_average_message_length(self) -> float:
        """Get average message length in words."""
        if not self.message_lengths:
            return 0.0
        return sum(self.message_lengths) / len(self.message_lengths)
    
    def extract_pattern(self) -> Dict:
        """Extract communication pattern."""
        formality = dict(self.formality_indicators)
        dominant_formality = max(formality.items(), key=lambda x: x[1])[0] if formality else "neutral"
        
        return {
            "average_message_length": self.get_average_message_length(),
            "formality": dominant_formality,
            "message_count": len(self.message_lengths)
        }


class PatternDetector:
    """Main pattern detection engine."""
    
    def __init__(self):
        """Initialize all pattern detectors."""
        self.schedule = SchedulePattern()
        self.interests = InterestPattern()
        self.learning_style = LearningStylePattern()
        self.communication = CommunicationPattern()
        
        self.update_timestamp = time.time()
        self.pattern_version = 1
    
    def process_conversation(
        self,
        user_message: str,
        ai_response: str,
        subject_tags: Optional[List[str]] = None,
        sentiment: Optional[float] = None,
        engagement: Optional[float] = None,
        timestamp: Optional[float] = None
    ) -> None:
        """
        Process a conversation turn and extract patterns.
        
        Args:
            user_message: User's message
            ai_response: AI's response
            subject_tags: Topics mentioned
            sentiment: User sentiment (0-1, 0=negative, 1=positive)
            engagement: User engagement (0-1, 0=disengaged, 1=highly engaged)
            timestamp: When this occurred
        """
        if not timestamp:
            timestamp = time.time()
        
        # Record activity timing
        self.schedule.record_activity(timestamp)
        
        # Record communication pattern
        self.communication.record_message(user_message)
        
        # Record interests if tagged
        if subject_tags:
            for subject in subject_tags:
                self.interests.record_mention(
                    subject,
                    sentiment=sentiment or 0.5,
                    engagement=engagement or 0.5
                )
        
        # Infer learning style from context
        if "example" in user_message.lower() or "show me" in user_message.lower():
            self.learning_style.record_preference("example-based")
        if "visual" in user_message.lower() or "diagram" in user_message.lower():
            self.learning_style.record_preference("visual")
        if "explain" in user_message.lower() or "why" in user_message.lower():
            self.learning_style.record_preference("analytical")
        
        self.update_timestamp = time.time()
        self.pattern_version += 1
    
    def extract_all_patterns(self) -> Dict:
        """Extract all detected patterns."""
        patterns = {
            "schedule": self.schedule.extract_pattern(),
            "interests": self.interests.extract_pattern(),
            "learning_style": self.learning_style.extract_pattern(),
            "communication": self.communication.extract_pattern(),
            "metadata": {
                "extracted_at": self.update_timestamp,
                "version": self.pattern_version,
                "activity_samples": (
                    len(self.schedule.activity_hours) + 
                    sum(self.schedule.activity_hours.values())
                )
            }
        }
        return patterns
    
    def get_user_profile(self) -> Dict:
        """
        Get comprehensive user profile based on detected patterns.
        
        Returns: User profile dict for AI adaptation
        """
        patterns = self.extract_all_patterns()
        
        profile = {
            # Schedule preferences
            "prefers_morning_study": 8 in patterns["schedule"].get("peak_study_hours", []),
            "prefers_evening_study": any(h >= 18 for h in patterns["schedule"].get("peak_study_hours", [])),
            "preferred_study_times": patterns["schedule"]["peak_study_hours"],
            
            # Subject interests and anxiety
            "top_interests": list(patterns["interests"]["top_interests"].keys())[:3],
            "anxiety_levels": patterns["interests"]["anxiety_levels"],
            
            # Learning preferences
            "preferred_learning_style": patterns["learning_style"]["dominant_style"] or "mixed",
            
            # Communication style
            "formality": patterns["communication"]["formality"],
            "average_message_length": patterns["communication"]["average_message_length"],
            "communication_style": (
                "concise" if patterns["communication"]["average_message_length"] < 5
                else "detailed" if patterns["communication"]["average_message_length"] > 20
                else "balanced"
            ),
            
            # Metadata
            "last_updated": self.update_timestamp,
            "confidence": min(self.pattern_version / 10.0, 1.0)  # More samples = more confident
        }
        
        return profile
    
    def get_actionable_insights(self) -> List[str]:
        """Generate actionable insights from patterns."""
        insights = []
        profile = self.get_user_profile()
        
        # Schedule insights
        if profile["prefers_morning_study"]:
            insights.append("User prefers morning study sessions")
        if profile["prefers_evening_study"]:
            insights.append("User prefers evening study sessions")
        
        # Interest insights
        if profile["top_interests"]:
            insights.append(f"Top interests: {', '.join(profile['top_interests'])}")
        
        # Anxiety insights
        high_anxiety = [s for s, a in profile["anxiety_levels"].items() if a > 0.7]
        if high_anxiety:
            insights.append(f"User shows anxiety with: {', '.join(high_anxiety)}")
        
        # Learning style insights
        if profile["preferred_learning_style"]:
            insights.append(f"Prefers {profile['preferred_learning_style']} learning style")
        
        # Communication insights
        if profile["communication_style"] == "concise":
            insights.append("User prefers concise, direct responses")
        elif profile["communication_style"] == "detailed":
            insights.append("User appreciates detailed, thorough explanations")
        
        return insights


# Singleton instance
_detector = None


def get_pattern_detector() -> PatternDetector:
    """Get or create pattern detector instance."""
    global _detector
    if _detector is None:
        _detector = PatternDetector()
    return _detector
