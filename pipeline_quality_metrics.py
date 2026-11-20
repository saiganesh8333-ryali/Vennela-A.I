"""Phase 5 - Quality metrics computation."""

import logging
from typing import Dict, List
import time

logger = logging.getLogger(__name__)


class QualityMetricsComputer:
    """Compute real-time reinforcement scores and quality metrics."""
    
    def __init__(self):
        """Initialize metrics computer."""
        self.metrics_history = []
        self.window_size = 100
    
    def compute_response_quality(
        self,
        user_message: str,
        ai_response: str,
        reinforcement_score: float,
        metadata: Dict = None
    ) -> Dict:
        """
        Compute comprehensive response quality metrics.
        
        Returns:
            Dict with quality scores and breakdown
        """
        metadata = metadata or {}
        
        try:
            metrics = {
                "timestamp": time.time(),
                "reinforcement_score": reinforcement_score,
                "relevance_score": self._calculate_relevance(user_message, ai_response),
                "coherence_score": self._calculate_coherence(ai_response),
                "completeness_score": self._calculate_completeness(ai_response, metadata),
                "engagement_score": self._calculate_engagement(ai_response, user_message),
                "overall_quality": 0.0
            }
            
            # Weighted composite
            metrics["overall_quality"] = (
                reinforcement_score * 0.3 +
                metrics["relevance_score"] * 0.25 +
                metrics["coherence_score"] * 0.15 +
                metrics["completeness_score"] * 0.15 +
                metrics["engagement_score"] * 0.15
            )
            
            # Track in history
            self.metrics_history.append(metrics)
            if len(self.metrics_history) > self.window_size:
                self.metrics_history = self.metrics_history[-self.window_size:]
            
            return metrics
        
        except Exception as e:
            logger.error(f"Error computing quality: {e}")
            return self._default_metrics()
    
    def _calculate_relevance(self, user_msg: str, ai_response: str) -> float:
        """Calculate response relevance to user message."""
        if not user_msg or not ai_response:
            return 0.0
        
        try:
            user_words = set(user_msg.lower().split())
            response_words = set(ai_response.lower().split())
            
            intersection = user_words & response_words
            
            if not intersection or not user_words:
                return 0.3
            
            relevance = len(intersection) / len(user_words)
            return min(1.0, relevance)
        
        except Exception as e:
            logger.error(f"Error calculating relevance: {e}")
            return 0.5
    
    def _calculate_coherence(self, text: str) -> float:
        """Calculate response coherence."""
        if not text:
            return 0.0
        
        try:
            coherence = 0.5
            
            # Length sanity
            if 50 < len(text) < 2000:
                coherence += 0.2
            elif len(text) > 2000:
                coherence -= 0.1
            
            # Sentence structure
            sentences = text.split('.')
            avg_sent_len = len(text) / max(len(sentences), 1)
            
            if 10 < avg_sent_len < 30:
                coherence += 0.15
            
            # Punctuation variety
            punct_types = sum(1 for p in '.!?,;:' if p in text)
            if punct_types > 2:
                coherence += 0.15
            
            return min(1.0, max(0.0, coherence))
        
        except Exception as e:
            logger.error(f"Error calculating coherence: {e}")
            return 0.5
    
    def _calculate_completeness(self, response: str, metadata: Dict) -> float:
        """Calculate response completeness."""
        if not response:
            return 0.0
        
        try:
            completeness = 0.5
            
            # Has introduction
            intro_words = ["i'll", "let me", "here's", "the", "some", "several"]
            if any(word in response.lower()[:50] for word in intro_words):
                completeness += 0.15
            
            # Has conclusion
            conclusion_words = ["hope", "helpful", "let me know", "feel free", "if you have", "any other"]
            if any(word in response.lower()[-100:] for word in conclusion_words):
                completeness += 0.15
            
            # Has supporting details
            if any(marker in response for marker in ["1.", "2.", "-", "•", "for example", "such as"]):
                completeness += 0.2
            
            return min(1.0, max(0.0, completeness))
        
        except Exception as e:
            logger.error(f"Error calculating completeness: {e}")
            return 0.5
    
    def _calculate_engagement(self, response: str, user_msg: str) -> float:
        """Calculate engagement level."""
        if not response:
            return 0.0
        
        try:
            engagement = 0.4
            
            # Questions in response
            questions = response.count('?')
            if questions > 0:
                engagement += min(0.2, questions * 0.1)
            
            # Personalization (if user name detected)
            if any(phrase in user_msg for phrase in ["my name", "i'm", "i am", "call me"]):
                if "you" in response or "your" in response:
                    engagement += 0.2
            
            # Enthusiasm
            if response.count('!') > 0:
                engagement += 0.1
            
            # Friendly tone
            friendly_words = ["happy", "great", "wonderful", "perfect", "awesome", "thanks", "please"]
            friendly_count = sum(response.lower().count(word) for word in friendly_words)
            if friendly_count > 0:
                engagement += min(0.15, friendly_count * 0.05)
            
            return min(1.0, max(0.0, engagement))
        
        except Exception as e:
            logger.error(f"Error calculating engagement: {e}")
            return 0.5
    
    def _default_metrics(self) -> Dict:
        """Return default metrics dict."""
        return {
            "timestamp": time.time(),
            "reinforcement_score": 0.0,
            "relevance_score": 0.5,
            "coherence_score": 0.5,
            "completeness_score": 0.5,
            "engagement_score": 0.5,
            "overall_quality": 0.5
        }
    
    def get_average_metrics(self, time_window: int = 3600) -> Dict:
        """
        Get average metrics over time window.
        
        Args:
            time_window: Time window in seconds
        
        Returns:
            Average metrics dict
        """
        try:
            current_time = time.time()
            recent = [
                m for m in self.metrics_history
                if current_time - m["timestamp"] < time_window
            ]
            
            if not recent:
                return {}
            
            avg = {}
            metric_keys = [
                "reinforcement_score",
                "relevance_score",
                "coherence_score",
                "completeness_score",
                "engagement_score",
                "overall_quality"
            ]
            
            for key in metric_keys:
                values = [m[key] for m in recent if key in m]
                if values:
                    avg[key] = sum(values) / len(values)
            
            avg["sample_count"] = len(recent)
            avg["time_window_seconds"] = time_window
            
            return avg
        
        except Exception as e:
            logger.error(f"Error calculating average metrics: {e}")
            return {}
    
    def get_trend_analysis(self, window_size: int = 20) -> Dict:
        """Analyze quality trends."""
        if len(self.metrics_history) < 2:
            return {"trend": "insufficient_data"}
        
        try:
            recent = self.metrics_history[-window_size:]
            
            qualities = [m["overall_quality"] for m in recent]
            avg_recent = sum(qualities[-5:]) / 5 if len(qualities) >= 5 else sum(qualities) / len(qualities)
            avg_older = sum(qualities[:5]) / 5 if len(qualities) >= 10 else 0.5
            
            trend = "improving" if avg_recent > avg_older else "declining" if avg_recent < avg_older else "stable"
            
            return {
                "trend": trend,
                "average_quality": avg_recent,
                "quality_delta": avg_recent - avg_older,
                "samples": len(recent)
            }
        
        except Exception as e:
            logger.error(f"Error analyzing trend: {e}")
            return {"trend": "error"}
