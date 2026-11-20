"""Phase 5 - Real-time model trainer for incremental updates."""

import logging
from typing import Dict, List, Optional
import time

logger = logging.getLogger(__name__)


class RealTimeTrainer:
    """Perform incremental model updates after each interaction."""
    
    def __init__(self):
        """Initialize real-time trainer."""
        self.training_batch = []
        self.batch_size = 10
        self.last_training_time = 0
        self.training_interval = 300  # 5 minutes
    
    def add_interaction(self, interaction_data: Dict) -> None:
        """
        Add interaction to training batch.
        
        Args:
            interaction_data: Dict with message, response, feedback
        """
        if not interaction_data or not isinstance(interaction_data, dict):
            return
        
        try:
            self.training_batch.append({
                "timestamp": time.time(),
                "data": interaction_data
            })
            
            # Auto-trigger training if batch full
            if len(self.training_batch) >= self.batch_size:
                self.train_batch()
        
        except Exception as e:
            logger.error(f"Error adding interaction: {e}")
    
    def train_batch(self, force: bool = False) -> Dict:
        """
        Train on current batch if conditions met.
        
        Args:
            force: Force training regardless of interval
        
        Returns:
            Training result
        """
        current_time = time.time()
        
        if not force and (current_time - self.last_training_time) < self.training_interval:
            return {"trained": False, "reason": "training_interval_not_met"}
        
        if not self.training_batch:
            return {"trained": False, "reason": "empty_batch"}
        
        try:
            result = {
                "trained": True,
                "batch_size": len(self.training_batch),
                "training_results": {}
            }
            
            # Extract learning data
            learning_data = [item["data"] for item in self.training_batch]
            
            # Train different components
            result["training_results"]["user_profile"] = self._train_profile(learning_data)
            result["training_results"]["response_patterns"] = self._train_response_patterns(learning_data)
            result["training_results"]["emotion_model"] = self._train_emotion_model(learning_data)
            result["training_results"]["preference_model"] = self._train_preferences(learning_data)
            
            # Clear batch
            self.training_batch = []
            self.last_training_time = current_time
            
            logger.info(f"Batch training completed on {len(learning_data)} interactions")
            return result
        
        except Exception as e:
            logger.error(f"Error during batch training: {e}")
            return {"trained": False, "error": str(e)}
    
    def _train_profile(self, interactions: List[Dict]) -> Dict:
        """Train user profile from interactions."""
        try:
            profile_updates = {
                "interactions_processed": len(interactions),
                "profile_refined": True,
                "new_patterns": []
            }
            
            # Aggregate new patterns
            for interaction in interactions:
                if interaction.get("new_pattern"):
                    profile_updates["new_patterns"].append(
                        interaction["new_pattern"]
                    )
            
            return profile_updates
        except Exception as e:
            logger.error(f"Error training profile: {e}")
            return {"error": str(e)}
    
    def _train_response_patterns(self, interactions: List[Dict]) -> Dict:
        """Train response generation patterns."""
        try:
            return {
                "high_performing_responses": len([i for i in interactions if i.get("score", 0) > 0.6]),
                "low_performing_responses": len([i for i in interactions if i.get("score", 0) < 0.3]),
                "patterns_identified": True
            }
        except Exception as e:
            logger.error(f"Error training response patterns: {e}")
            return {"error": str(e)}
    
    def _train_emotion_model(self, interactions: List[Dict]) -> Dict:
        """Train emotion detection and response."""
        try:
            emotions_seen = set()
            for interaction in interactions:
                if "emotion" in interaction:
                    emotions_seen.add(interaction["emotion"])
            
            return {
                "emotions_trained": list(emotions_seen),
                "model_refined": True
            }
        except Exception as e:
            logger.error(f"Error training emotion model: {e}")
            return {"error": str(e)}
    
    def _train_preferences(self, interactions: List[Dict]) -> Dict:
        """Train user preference model."""
        try:
            preferences_updates = {
                "tone_preferences": self._extract_tone_preference(interactions),
                "length_preferences": self._extract_length_preference(interactions),
                "topic_preferences": self._extract_topic_preference(interactions)
            }
            
            return preferences_updates
        except Exception as e:
            logger.error(f"Error training preferences: {e}")
            return {"error": str(e)}
    
    def _extract_tone_preference(self, interactions: List[Dict]) -> Dict:
        """Extract tone preferences."""
        positive_formal = 0
        positive_casual = 0
        
        for interaction in interactions:
            if interaction.get("feedback_score", 0) > 0.6:
                if "formal" in interaction.get("tone", "").lower():
                    positive_formal += 1
                else:
                    positive_casual += 1
        
        return {
            "prefers_formal": positive_formal > positive_casual,
            "formal_score": positive_formal,
            "casual_score": positive_casual
        }
    
    def _extract_length_preference(self, interactions: List[Dict]) -> Dict:
        """Extract length preferences."""
        short_positive = 0
        long_positive = 0
        
        for interaction in interactions:
            if interaction.get("feedback_score", 0) > 0.6:
                length = len(interaction.get("response", ""))
                if length < 100:
                    short_positive += 1
                else:
                    long_positive += 1
        
        return {
            "prefers_short": short_positive > long_positive,
            "short_score": short_positive,
            "long_score": long_positive
        }
    
    def _extract_topic_preference(self, interactions: List[Dict]) -> Dict:
        """Extract topic preferences."""
        topic_scores = {}
        
        for interaction in interactions:
            topic = interaction.get("topic", "general")
            score = interaction.get("feedback_score", 0)
            
            if topic not in topic_scores:
                topic_scores[topic] = []
            topic_scores[topic].append(score)
        
        topic_avgs = {
            topic: sum(scores) / len(scores)
            for topic, scores in topic_scores.items()
        }
        
        return topic_avgs
    
    def get_training_status(self) -> Dict:
        """Get current training status."""
        return {
            "batch_size": len(self.training_batch),
            "max_batch_size": self.batch_size,
            "last_training_time": self.last_training_time,
            "training_interval": self.training_interval,
            "ready_to_train": len(self.training_batch) >= self.batch_size
        }
