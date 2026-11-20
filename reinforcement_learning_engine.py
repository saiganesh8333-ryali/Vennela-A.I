"""
Phase E: Autonomous Learning and Reinforcement - Complete Implementation
Reward scoring, feedback collection, and reinforcement learning loop
"""

import asyncio
import logging
import time
from typing import Optional, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    """Types of user feedback."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    CORRECTION = "correction"
    REFINEMENT = "refinement"


@dataclass
class RewardScore:
    """Reward score for interaction."""
    base_score: float  # 0-1
    accuracy_bonus: float = 0.0
    relevance_bonus: float = 0.0
    timeliness_bonus: float = 0.0
    user_satisfaction: float = 0.0
    final_score: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class UserFeedback:
    """User feedback on response."""
    feedback_type: FeedbackType
    rating: float  # 0-1
    comment: Optional[str] = None
    context: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


class RewardScorer:
    """Scores rewards for responses based on multiple factors."""
    
    def __init__(self):
        """Initialize reward scorer."""
        self.scoring_history = []
        self.accuracy_scores = {}
        self.relevance_scores = {}
        logger.info("Reward scorer initialized")
    
    def score_response(self, response_text: str, context: dict) -> RewardScore:
        """Score response quality.
        
        Args:
            response_text: Generated response
            context: Context including user query, history, etc
            
        Returns:
            RewardScore with detailed breakdown
        """
        score = RewardScore(base_score=0.5)
        
        # Accuracy scoring
        accuracy = self._score_accuracy(response_text, context)
        score.accuracy_bonus = accuracy * 0.3
        
        # Relevance scoring
        relevance = self._score_relevance(response_text, context)
        score.relevance_bonus = relevance * 0.35
        
        # Timeliness scoring
        timeliness = self._score_timeliness(context)
        score.timeliness_bonus = timeliness * 0.2
        
        # Final combined score
        score.final_score = min(1.0, score.base_score + 
                                score.accuracy_bonus + 
                                score.relevance_bonus + 
                                score.timeliness_bonus)
        
        self.scoring_history.append(score)
        return score
    
    def _score_accuracy(self, response: str, context: dict) -> float:
        """Score response accuracy."""
        if not response or len(response) == 0:
            return 0.0
        
        # Check for factual indicators
        confidence_words = ["certainly", "definitely", "absolutely", "yes"]
        uncertainty_words = ["maybe", "perhaps", "uncertain", "might"]
        
        confidence_count = sum(1 for word in confidence_words if word in response.lower())
        uncertainty_count = sum(1 for word in uncertainty_words if word in response.lower())
        
        return (1.0 - (uncertainty_count * 0.1)) if confidence_count > 0 else 0.7
    
    def _score_relevance(self, response: str, context: dict) -> float:
        """Score response relevance to query."""
        if "query" not in context or not response:
            return 0.5
        
        query_words = set(context["query"].lower().split())
        response_words = set(response.lower().split())
        
        # Jaccard similarity
        intersection = len(query_words & response_words)
        union = len(query_words | response_words)
        
        return intersection / union if union > 0 else 0.0
    
    def _score_timeliness(self, context: dict) -> float:
        """Score response timeliness."""
        if "response_time_ms" not in context:
            return 0.8
        
        response_time = context["response_time_ms"]
        
        # Ideal: 500-2000ms
        if 500 <= response_time <= 2000:
            return 1.0
        elif response_time < 500:
            return 0.9  # Very fast is good
        elif response_time <= 5000:
            return 0.7  # Acceptable
        else:
            return 0.3  # Slow


class FeedbackCollector:
    """Collects and stores user feedback."""
    
    def __init__(self):
        """Initialize feedback collector."""
        self.feedback_history: List[UserFeedback] = []
        self.feedback_stats = {
            "total_feedback": 0,
            "positive": 0,
            "negative": 0,
            "neutral": 0,
            "avg_rating": 0.0,
        }
        logger.info("Feedback collector initialized")
    
    def collect_feedback(self, feedback_type: FeedbackType, rating: float, 
                        comment: Optional[str] = None) -> UserFeedback:
        """Collect user feedback.
        
        Args:
            feedback_type: Type of feedback
            rating: Rating 0-1
            comment: Optional feedback comment
            
        Returns:
            UserFeedback object
        """
        feedback = UserFeedback(
            feedback_type=feedback_type,
            rating=max(0.0, min(1.0, rating)),
            comment=comment
        )
        
        self.feedback_history.append(feedback)
        self._update_stats(feedback)
        
        logger.info(f"Feedback collected: {feedback_type.value}, rating: {rating:.2f}")
        return feedback
    
    def _update_stats(self, feedback: UserFeedback) -> None:
        """Update feedback statistics."""
        self.feedback_stats["total_feedback"] += 1
        
        if feedback.feedback_type == FeedbackType.POSITIVE:
            self.feedback_stats["positive"] += 1
        elif feedback.feedback_type == FeedbackType.NEGATIVE:
            self.feedback_stats["negative"] += 1
        else:
            self.feedback_stats["neutral"] += 1
        
        # Update average rating
        total = self.feedback_stats["total_feedback"]
        current_avg = self.feedback_stats["avg_rating"]
        new_avg = (current_avg * (total - 1) + feedback.rating) / total
        self.feedback_stats["avg_rating"] = new_avg
    
    def get_recent_feedback(self, limit: int = 10) -> List[UserFeedback]:
        """Get recent feedback."""
        return self.feedback_history[-limit:]
    
    def get_stats(self) -> dict:
        """Get feedback statistics."""
        return self.feedback_stats.copy()


class ReinforcementLoop:
    """Main reinforcement learning loop."""
    
    def __init__(self):
        """Initialize reinforcement loop."""
        self.scorer = RewardScorer()
        self.collector = FeedbackCollector()
        self.learning_history = []
        self.convergence_threshold = 0.85
        logger.info("Reinforcement loop initialized")
    
    async def process_interaction(self, response_text: str, context: dict) -> dict:
        """Process complete interaction (response + feedback).
        
        Args:
            response_text: Generated response
            context: Interaction context
            
        Returns:
            Processing result with scores and learning updates
        """
        # Score response
        reward = self.scorer.score_response(response_text, context)
        
        # Wait for user feedback (async)
        feedback = await self._wait_for_feedback()
        
        if feedback:
            self.collector.collect_feedback(feedback.feedback_type, feedback.rating)
        
        # Store in learning history
        self.learning_history.append({
            "response": response_text,
            "reward": reward.final_score,
            "feedback": feedback,
            "timestamp": datetime.now(),
        })
        
        return {
            "reward_score": reward.final_score,
            "feedback_received": feedback is not None,
            "learning_updated": True,
        }
    
    async def _wait_for_feedback(self, timeout: float = 30.0) -> Optional[UserFeedback]:
        """Wait for user feedback (mock implementation).
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            UserFeedback or None if timeout
        """
        # Mock: would integrate with event bus in production
        await asyncio.sleep(0.1)
        return None
    
    def get_learning_metrics(self) -> dict:
        """Get learning metrics."""
        if not self.learning_history:
            return {"status": "no_data"}
        
        scores = [item["reward"] for item in self.learning_history]
        avg_score = sum(scores) / len(scores)
        
        return {
            "total_interactions": len(self.learning_history),
            "avg_reward_score": avg_score,
            "converged": avg_score >= self.convergence_threshold,
            "feedback_rate": self.collector.feedback_stats["total_feedback"] / len(self.learning_history) if self.learning_history else 0,
        }


# Singleton instances
_reward_scorer_instance: Optional[RewardScorer] = None
_feedback_collector_instance: Optional[FeedbackCollector] = None
_reinforcement_loop_instance: Optional[ReinforcementLoop] = None


def get_reward_scorer() -> RewardScorer:
    """Get singleton reward scorer."""
    global _reward_scorer_instance
    if _reward_scorer_instance is None:
        _reward_scorer_instance = RewardScorer()
    return _reward_scorer_instance


def get_feedback_collector() -> FeedbackCollector:
    """Get singleton feedback collector."""
    global _feedback_collector_instance
    if _feedback_collector_instance is None:
        _feedback_collector_instance = FeedbackCollector()
    return _feedback_collector_instance


def get_reinforcement_loop() -> ReinforcementLoop:
    """Get singleton reinforcement loop."""
    global _reinforcement_loop_instance
    if _reinforcement_loop_instance is None:
        _reinforcement_loop_instance = ReinforcementLoop()
    return _reinforcement_loop_instance
