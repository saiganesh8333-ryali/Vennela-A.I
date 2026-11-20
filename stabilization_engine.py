"""
🛡️ Stabilization Phase: Safety Systems & Performance Monitoring
Prevents memory loops, latency spikes, and recursive prediction abuse.

Critical safeguards before Phase 4 (Proactive Intelligence).
"""

import logging
import time
from typing import Dict, Optional, List
from collections import deque
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class MemoryLimiter:
    """Enforce memory capacity limits and auto-cleanup."""
    
    def __init__(
        self,
        max_short_term: int = 100,
        max_long_term: int = 1000,
        cleanup_interval_seconds: int = 3600
    ):
        """
        Initialize memory limiter.
        
        Args:
            max_short_term: Max recent memories (1-2 days)
            max_long_term: Max total memories (all-time)
            cleanup_interval_seconds: How often to run cleanup
        """
        self.max_short_term = max_short_term
        self.max_long_term = max_long_term
        self.cleanup_interval = cleanup_interval_seconds
        
        self.last_cleanup = time.time()
        self.memory_count = 0
        self.cleanup_runs = 0
    
    def should_cleanup(self) -> bool:
        """Check if cleanup is due."""
        return time.time() - self.last_cleanup > self.cleanup_interval
    
    def cleanup_old_memories(
        self,
        all_memories: List[Dict],
        importance_threshold: float = 0.3
    ) -> List[Dict]:
        """
        Remove old, low-importance memories.
        
        Keeps:
        - Recent memories (< 1 week)
        - Important memories (score > threshold)
        
        Returns: Cleaned memory list
        """
        now = time.time()
        week_ago = now - (7 * 24 * 3600)
        
        cleaned = []
        for mem in all_memories:
            timestamp = mem.get("timestamp", 0)
            importance = mem.get("importance", 0)
            
            # Keep if recent or important
            if timestamp > week_ago or importance > importance_threshold:
                cleaned.append(mem)
        
        removed = len(all_memories) - len(cleaned)
        self.cleanup_runs += 1
        
        logger.info(f"🧹 Cleanup: removed {removed} old/low-importance memories")
        self.last_cleanup = time.time()
        
        return cleaned
    
    def enforce_limits(
        self,
        all_memories: List[Dict],
        per_importance_sort: bool = True
    ) -> List[Dict]:
        """
        Enforce memory count limits.
        
        If over limit, remove lowest importance memories.
        """
        if len(all_memories) <= self.max_long_term:
            return all_memories
        
        # Sort by importance (keep highest)
        if per_importance_sort:
            sorted_mem = sorted(
                all_memories,
                key=lambda x: x.get("importance", 0),
                reverse=True
            )
        else:
            sorted_mem = all_memories
        
        # Keep only top memories
        kept = sorted_mem[:self.max_long_term]
        removed = len(all_memories) - len(kept)
        
        logger.warning(
            f"⚠️ Memory limit enforced: removed {removed} memories "
            f"(kept top {self.max_long_term})"
        )
        
        return kept


class PredictionCooldown:
    """Prevent spam predictions with cooldown periods."""
    
    def __init__(
        self,
        min_interval_seconds: int = 5,
        max_predictions_per_hour: int = 10
    ):
        """Initialize prediction cooldown."""
        self.min_interval = min_interval_seconds
        self.max_per_hour = max_predictions_per_hour
        
        self.last_prediction_time = 0
        self.prediction_history = deque(maxlen=60)  # Last 60 predictions
    
    def can_predict(self) -> bool:
        """Check if enough time has passed since last prediction."""
        now = time.time()
        return now - self.last_prediction_time >= self.min_interval
    
    def record_prediction(self) -> None:
        """Record a prediction attempt."""
        now = time.time()
        self.prediction_history.append(now)
        self.last_prediction_time = now
    
    def get_predictions_last_hour(self) -> int:
        """Count predictions in last hour."""
        now = time.time()
        hour_ago = now - 3600
        
        return sum(
            1 for pred_time in self.prediction_history
            if pred_time > hour_ago
        )
    
    def has_cooldown_ready(self) -> bool:
        """Check if cooldown period is ready."""
        if not self.can_predict():
            return False
        
        if self.get_predictions_last_hour() >= self.max_per_hour:
            logger.warning(
                f"⏰ Prediction cooldown: max {self.max_per_hour}/hour reached"
            )
            return False
        
        return True


class ReinforcementDecay:
    """Apply decay to old rewards to prevent stagnation."""
    
    def __init__(
        self,
        decay_rate: float = 0.95,
        decay_interval_seconds: int = 86400  # 1 day
    ):
        """
        Initialize reward decay.
        
        Args:
            decay_rate: Multiply rewards by this daily (0.95 = 5% decay/day)
            decay_interval_seconds: Apply decay this often
        """
        self.decay_rate = decay_rate
        self.decay_interval = decay_interval_seconds
        self.last_decay_time = time.time()
    
    def should_apply_decay(self) -> bool:
        """Check if decay is due."""
        return time.time() - self.last_decay_time >= self.decay_interval
    
    def apply_decay(
        self,
        action_rewards: Dict[str, List[float]]
    ) -> Dict[str, List[float]]:
        """
        Apply decay to all recorded rewards.
        
        Prevents AI from getting stuck in old habits.
        """
        decayed = {}
        
        for action, rewards in action_rewards.items():
            decayed[action] = [r * self.decay_rate for r in rewards]
        
        logger.info(f"📉 Applied reward decay ({self.decay_rate:.0%})")
        self.last_decay_time = time.time()
        
        return decayed


class PerformanceMonitor:
    """Track performance metrics to detect degradation."""
    
    def __init__(self, window_size: int = 100):
        """Initialize performance monitor."""
        self.response_times = deque(maxlen=window_size)
        self.memory_usage = deque(maxlen=window_size)
        self.prediction_accuracy = deque(maxlen=window_size)
        
        self.start_time = time.time()
    
    def record_response_time(self, response_time_ms: float) -> None:
        """Record response time."""
        self.response_times.append(response_time_ms)
    
    def record_memory_usage(self, memory_mb: float) -> None:
        """Record memory usage."""
        self.memory_usage.append(memory_mb)
    
    def record_prediction_accuracy(self, accuracy: float) -> None:
        """Record prediction accuracy (0-1)."""
        self.prediction_accuracy.append(accuracy)
    
    def get_average_response_time(self) -> float:
        """Get average response time."""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)
    
    def get_peak_memory(self) -> float:
        """Get peak memory usage."""
        return max(self.memory_usage) if self.memory_usage else 0.0
    
    def get_avg_memory(self) -> float:
        """Get average memory usage."""
        if not self.memory_usage:
            return 0.0
        return sum(self.memory_usage) / len(self.memory_usage)
    
    def get_avg_accuracy(self) -> float:
        """Get average prediction accuracy."""
        if not self.prediction_accuracy:
            return 0.0
        return sum(self.prediction_accuracy) / len(self.prediction_accuracy)
    
    def check_performance_degradation(self) -> Dict[str, bool]:
        """Check if performance is degrading."""
        warnings = {}
        
        # Response time warning: >500ms average
        avg_response = self.get_average_response_time()
        warnings["slow_response"] = avg_response > 500
        
        # Memory warning: >200MB average
        avg_memory = self.get_avg_memory()
        warnings["high_memory"] = avg_memory > 200
        
        # Accuracy warning: <50% average
        avg_accuracy = self.get_avg_accuracy()
        warnings["low_accuracy"] = avg_accuracy < 0.5
        
        # Log warnings
        if warnings["slow_response"]:
            logger.warning(f"⚠️ Slow response time: {avg_response:.0f}ms avg")
        if warnings["high_memory"]:
            logger.warning(f"⚠️ High memory usage: {avg_memory:.0f}MB avg")
        if warnings["low_accuracy"]:
            logger.warning(f"⚠️ Low prediction accuracy: {avg_accuracy:.0%}")
        
        return warnings
    
    def get_metrics_report(self) -> Dict:
        """Get full metrics report."""
        return {
            "uptime_seconds": time.time() - self.start_time,
            "avg_response_time_ms": self.get_average_response_time(),
            "peak_memory_mb": self.get_peak_memory(),
            "avg_memory_mb": self.get_avg_memory(),
            "avg_prediction_accuracy": self.get_avg_accuracy(),
            "samples_collected": len(self.response_times),
            "degradation_warnings": self.check_performance_degradation()
        }


class AsyncTaskScheduler:
    """Schedule async background tasks (learning, scoring, analytics)."""
    
    def __init__(self):
        """Initialize task scheduler."""
        self.pending_tasks = []
        self.completed_tasks = 0
        self.failed_tasks = 0
    
    def schedule_pattern_learning(self, conversation_data: Dict) -> None:
        """
        Schedule pattern detection as background task.
        
        Should NOT block response.
        """
        logger.debug("📅 Scheduled: pattern learning")
        self.pending_tasks.append({
            "type": "pattern_learning",
            "data": conversation_data,
            "priority": "normal"
        })
    
    def schedule_memory_scoring(self, memory_data: Dict) -> None:
        """Schedule memory importance scoring as background task."""
        logger.debug("📅 Scheduled: memory scoring")
        self.pending_tasks.append({
            "type": "memory_scoring",
            "data": memory_data,
            "priority": "normal"
        })
    
    def schedule_analytics(self, event: str, data: Dict) -> None:
        """Schedule analytics collection as background task."""
        logger.debug("📅 Scheduled: analytics")
        self.pending_tasks.append({
            "type": "analytics",
            "event": event,
            "data": data,
            "priority": "low"
        })
    
    def get_pending_count(self) -> int:
        """Get number of pending background tasks."""
        return len(self.pending_tasks)
    
    def get_stats(self) -> Dict:
        """Get task statistics."""
        return {
            "pending": len(self.pending_tasks),
            "completed": self.completed_tasks,
            "failed": self.failed_tasks
        }


class StabilizationEngine:
    """Main stabilization engine coordinating all safety systems."""
    
    def __init__(self):
        """Initialize stabilization engine."""
        self.memory_limiter = MemoryLimiter()
        self.prediction_cooldown = PredictionCooldown()
        self.reward_decay = ReinforcementDecay()
        self.performance_monitor = PerformanceMonitor()
        self.async_scheduler = AsyncTaskScheduler()
        
        self.version = 1
    
    def should_allow_prediction(self) -> bool:
        """Check if prediction is safe right now."""
        return self.prediction_cooldown.has_cooldown_ready()
    
    def record_api_call(
        self,
        response_time_ms: float,
        success: bool = True
    ) -> None:
        """Record an API call for monitoring."""
        self.performance_monitor.record_response_time(response_time_ms)
        
        if response_time_ms > 500:
            logger.warning(f"⚠️ Slow API call: {response_time_ms:.0f}ms")
    
    def check_system_health(self) -> Dict[str, bool]:
        """
        Check overall system health.
        
        Returns: Health status dict
        """
        degradation = self.performance_monitor.check_performance_degradation()
        
        return {
            "healthy": not any(degradation.values()),
            "issues": degradation,
            "pending_tasks": self.async_scheduler.get_pending_count(),
            "version": self.version
        }
    
    def get_diagnostics(self) -> Dict:
        """Get full system diagnostics for debugging."""
        return {
            "metrics": self.performance_monitor.get_metrics_report(),
            "memory_limits": {
                "max_short_term": self.memory_limiter.max_short_term,
                "max_long_term": self.memory_limiter.max_long_term,
                "cleanups_run": self.memory_limiter.cleanup_runs
            },
            "predictions": {
                "cooldown_ready": self.prediction_cooldown.has_cooldown_ready(),
                "last_hour_count": self.prediction_cooldown.get_predictions_last_hour(),
                "max_per_hour": self.prediction_cooldown.max_per_hour
            },
            "async_tasks": self.async_scheduler.get_stats()
        }
    
    def extract_safety_insights(self) -> List[str]:
        """Generate safety insights."""
        insights = []
        
        # Memory status
        if self.memory_limiter.cleanup_runs > 0:
            insights.append(f"✅ Memory auto-cleanup active ({self.memory_limiter.cleanup_runs} runs)")
        
        # Prediction throttling
        pred_per_hour = self.prediction_cooldown.get_predictions_last_hour()
        if pred_per_hour > 5:
            insights.append(f"⚠️ High prediction rate: {pred_per_hour} per hour")
        
        # Performance
        health = self.check_system_health()
        if health["healthy"]:
            insights.append("✅ System health: GOOD")
        else:
            issues = [k for k, v in health["issues"].items() if v]
            insights.append(f"⚠️ System issues: {', '.join(issues)}")
        
        return insights


# Singleton instance
_engine = None


def get_stabilization_engine() -> StabilizationEngine:
    """Get or create stabilization engine instance."""
    global _engine
    if _engine is None:
        _engine = StabilizationEngine()
    return _engine
