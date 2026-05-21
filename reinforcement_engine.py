"""
🎮 Reinforcement Learning Engine
Reward-based adaptive learning from user interactions.

Not heavy RL — lightweight reward tracking for pattern optimization.
"""

import logging
import time
from typing import Dict, Optional, List, Tuple
from collections import defaultdict, Counter
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RewardTracker:
    """Track rewards for AI actions."""
    
    def __init__(self, max_history: int = 1000):
        """Initialize reward tracking."""
        self.rewards = []  # List of (action, reward, timestamp)
        self.action_rewards = defaultdict(list)  # Action type -> rewards
        self.max_history = max_history
    
    def record_reward(
        self,
        action: str,
        reward: float,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Record a reward for an action.
        
        Args:
            action: Type of action (e.g., "suggestion", "explanation", "code_example")
            reward: Reward value (-1.0 to 1.0, 0=neutral)
            metadata: Additional context
        """
        reward_entry = {
            "action": action,
            "reward": max(-1.0, min(1.0, reward)),  # Clamp to [-1, 1]
            "timestamp": time.time(),
            "metadata": metadata or {}
        }
        
        self.rewards.append(reward_entry)
        self.action_rewards[action].append(reward_entry)
        
        # Keep only recent history
        if len(self.rewards) > self.max_history:
            self.rewards = self.rewards[-self.max_history:]
    
    def get_action_quality(self, action: str) -> float:
        """
        Get average quality (reward) for an action.
        
        Returns: -1.0 (bad) to 1.0 (good), 0.0 (neutral)
        """
        if action not in self.action_rewards:
            return 0.0
        
        rewards = self.action_rewards[action]
        if not rewards:
            return 0.0
        
        avg_reward = sum(r["reward"] for r in rewards) / len(rewards)
        return avg_reward
    
    def get_top_actions(self, n: int = 5) -> List[Tuple[str, float]]:
        """Get best-performing actions."""
        actions = [
            (action, self.get_action_quality(action))
            for action in self.action_rewards.keys()
        ]
        return sorted(actions, key=lambda x: x[1], reverse=True)[:n]
    
    def get_bottom_actions(self, n: int = 5) -> List[Tuple[str, float]]:
        """Get worst-performing actions."""
        actions = [
            (action, self.get_action_quality(action))
            for action in self.action_rewards.keys()
        ]
        return sorted(actions, key=lambda x: x[1])[:n]


class PredictionAccuracyTracker:
    """Track accuracy of predictions over time."""
    
    def __init__(self):
        """Initialize accuracy tracking."""
        self.predictions = []  # List of predictions with outcomes
        self.prediction_types = defaultdict(list)  # Type -> predictions
    
    def record_prediction(
        self,
        prediction_type: str,
        predicted_value: str,
        actual_value: str,
        confidence: float = 0.5
    ) -> bool:
        """
        Record a prediction and whether it was correct.
        
        Args:
            prediction_type: Type of prediction (intent, context, etc.)
            predicted_value: What we predicted
            actual_value: What actually happened
            confidence: Our confidence in the prediction
            
        Returns: Whether prediction was correct
        """
        was_correct = predicted_value.lower() == actual_value.lower()
        
        prediction_entry = {
            "type": prediction_type,
            "predicted": predicted_value,
            "actual": actual_value,
            "correct": was_correct,
            "confidence": confidence,
            "timestamp": time.time()
        }
        
        self.predictions.append(prediction_entry)
        self.prediction_types[prediction_type].append(prediction_entry)
        
        return was_correct
    
    def get_accuracy(
        self,
        prediction_type: Optional[str] = None,
        min_confidence: float = 0.0,
        time_window_hours: Optional[int] = None
    ) -> float:
        """
        Get accuracy for predictions.
        
        Args:
            prediction_type: Filter by type (None = all)
            min_confidence: Only include predictions above this confidence
            time_window_hours: Only include predictions from last N hours
            
        Returns: Accuracy 0.0-1.0
        """
        if prediction_type:
            predictions = self.prediction_types.get(prediction_type, [])
        else:
            predictions = self.predictions
        
        # Filter by confidence
        predictions = [p for p in predictions if p["confidence"] >= min_confidence]
        
        # Filter by time window
        if time_window_hours:
            cutoff = time.time() - (time_window_hours * 3600)
            predictions = [p for p in predictions if p["timestamp"] > cutoff]
        
        if not predictions:
            return 0.5  # Default neutral
        
        correct = sum(1 for p in predictions if p["correct"])
        return correct / len(predictions)
    
    def get_high_confidence_accuracy(self) -> float:
        """Get accuracy on high-confidence predictions (>0.7)."""
        return self.get_accuracy(min_confidence=0.7)


class ResponseQualityTracker:
    """Track quality of responses based on user feedback."""
    
    def __init__(self):
        """Initialize response quality tracking."""
        self.responses = []
        self.response_types = defaultdict(list)
    
    def record_response(
        self,
        response_type: str,
        quality_score: float,  # 0-1, 0=poor, 1=excellent
        engagement: Optional[float] = None,  # Did user engage?
        follow_up_count: int = 0  # How many follow-ups did it generate?
    ) -> None:
        """Record response quality."""
        response_entry = {
            "type": response_type,
            "quality": max(0.0, min(1.0, quality_score)),
            "engagement": engagement,
            "follow_ups": follow_up_count,
            "timestamp": time.time()
        }
        
        self.responses.append(response_entry)
        self.response_types[response_type].append(response_entry)
    
    def get_response_quality(self, response_type: str) -> float:
        """Get average quality for a response type."""
        if response_type not in self.response_types:
            return 0.5
        
        responses = self.response_types[response_type]
        if not responses:
            return 0.5
        
        avg = sum(r["quality"] for r in responses) / len(responses)
        return avg


class ReinforcementLearningEngine:
    """Main reinforcement learning engine."""
    
    def __init__(self):
        """Initialize RL engine."""
        self.reward_tracker = RewardTracker()
        self.accuracy_tracker = PredictionAccuracyTracker()
        self.quality_tracker = ResponseQualityTracker()
        
        # Learning state
        self.total_interactions = 0
        self.learning_rate = 0.1  # How fast to adapt
        self.exploration_rate = 0.2  # Try new things 20% of the time
        
        self.version = 1
    
    def calculate_reward(
        self,
        user_engaged: bool = False,
        response_helpful: bool = False,
        prediction_accurate: bool = False,
        response_time_good: bool = True,
        suggestion_accepted: Optional[bool] = None
    ) -> float:
        """
        Calculate overall reward for an interaction.
        
        Combines multiple feedback signals.
        """
        reward = 0.0
        
        # Base: user engagement
        if user_engaged:
            reward += 0.3
        
        # Helpfulness of response
        if response_helpful:
            reward += 0.3
        
        # Prediction accuracy
        if prediction_accurate:
            reward += 0.2
        
        # Response timing
        if response_time_good:
            reward += 0.1
        
        # Suggestion acceptance (if applicable)
        if suggestion_accepted is not None:
            reward += 0.1 if suggestion_accepted else -0.05
        
        # Normalize to [-1, 1]
        reward = reward * 2 - 1 if reward > 0.5 else reward - 0.5
        reward = max(-1.0, min(1.0, reward))
        
        return reward
    
    def record_interaction(
        self,
        action_type: str,
        user_feedback: Optional[Dict] = None,
        prediction_accuracy: Optional[bool] = None,
        response_quality: Optional[float] = None
    ) -> None:
        """
        Record a complete interaction for learning.
        
        Args:
            action_type: Type of AI action
            user_feedback: Dict with keys like engaged, helpful, accepted
            prediction_accuracy: Was prediction correct?
            response_quality: Quality score 0-1
        """
        user_feedback = user_feedback or {}
        
        # Calculate reward
        reward = self.calculate_reward(
            user_engaged=user_feedback.get("engaged", False),
            response_helpful=user_feedback.get("helpful", False),
            prediction_accurate=prediction_accuracy or False,
            response_time_good=user_feedback.get("quick", True),
            suggestion_accepted=user_feedback.get("accepted")
        )
        
        # Record reward
        self.reward_tracker.record_reward(action_type, reward, user_feedback)
        
        # Record quality if provided
        if response_quality is not None:
            self.quality_tracker.record_response(
                action_type,
                response_quality,
                engagement=user_feedback.get("engagement")
            )
        
        self.total_interactions += 1
        self.version += 1
    
    def get_best_practices(self) -> Dict[str, any]:
        """Get learned best practices."""
        top_actions = self.reward_tracker.get_top_actions(5)
        bottom_actions = self.reward_tracker.get_bottom_actions(3)
        
        return {
            "best_actions": [
                {"action": a[0], "quality": a[1]} for a in top_actions
            ],
            "actions_to_improve": [
                {"action": a[0], "quality": a[1]} for a in bottom_actions
            ],
            "prediction_accuracy": {
                "high_confidence": self.accuracy_tracker.get_high_confidence_accuracy(),
                "overall": self.accuracy_tracker.get_accuracy()
            }
        }
    
    def should_explore_new_action(self) -> bool:
        """
        Decide if we should try a new action (exploration vs exploitation).
        
        Uses epsilon-greedy strategy.
        """
        import random
        return random.random() < self.exploration_rate
    
    def get_learning_curve(self) -> List[Tuple[float, float]]:
        """
        Get learning progress over time.
        
        Returns: List of (timestamp, average_reward) pairs
        """
        if not self.reward_tracker.rewards:
            return []
        
        # Group rewards into windows (every 10 interactions)
        window_size = 10
        curve = []
        
        for i in range(0, len(self.reward_tracker.rewards), window_size):
            window = self.reward_tracker.rewards[i:i+window_size]
            if window:
                avg_reward = sum(r["reward"] for r in window) / len(window)
                timestamp = window[-1]["timestamp"]
                curve.append((timestamp, avg_reward))
        
        return curve
    
    def extract_insights(self) -> List[str]:
        """Generate insights from learning data."""
        insights = []
        
        # Best practices
        best = self.reward_tracker.get_top_actions(1)
        if best:
            action, quality = best[0]
            insights.append(f"✅ Best performing action: {action} ({quality:.2f} quality)")
        
        # Areas to improve
        worst = self.reward_tracker.get_bottom_actions(1)
        if worst:
            action, quality = worst[0]
            insights.append(f"⚠️ Needs improvement: {action} ({quality:.2f} quality)")
        
        # Prediction accuracy
        acc = self.accuracy_tracker.get_accuracy()
        if acc > 0.6:
            insights.append(f"🎯 Predictions are reliable ({acc:.0%} accuracy)")
        else:
            insights.append(f"📊 Predictions improving ({acc:.0%} accuracy)")
        
        # Learning progress
        if self.total_interactions > 50:
            curve = self.get_learning_curve()
            if curve:
                first_avg = curve[0][1]
                last_avg = curve[-1][1]
                if last_avg > first_avg:
                    improvement = (last_avg - first_avg) / abs(first_avg) * 100
                    insights.append(f"📈 Learning progress: +{improvement:.0f}% improvement")
        
        return insights
    
    def extract_all_patterns(self) -> Dict:
        """Extract all learning patterns."""
        return {
            "best_practices": self.get_best_practices(),
            "learning_curve_length": len(self.get_learning_curve()),
            "total_interactions": self.total_interactions,
            "insights": self.extract_insights(),
            "metadata": {
                "version": self.version,
                "learning_rate": self.learning_rate,
                "exploration_rate": self.exploration_rate
            }
        }


# Singleton instance
_engine = None


def get_reinforcement_engine() -> ReinforcementLearningEngine:
    """Get or create RL engine instance."""
    global _engine
    if _engine is None:
        _engine = ReinforcementLearningEngine()
    return _engine
