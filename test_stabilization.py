"""
Test suite for Stabilization Phase: Safety systems & performance monitoring
Ensures all guardrails work correctly before Phase 4.
"""

import logging
import time
from stabilization_engine import (
    MemoryLimiter,
    PredictionCooldown,
    ReinforcementDecay,
    PerformanceMonitor,
    AsyncTaskScheduler,
    StabilizationEngine,
    get_stabilization_engine
)

logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_memory_limiter():
    """Test memory cleanup and limits."""
    logger.info("\n🧪 TEST 1: Memory Limiter")
    
    limiter = MemoryLimiter(max_long_term=5)
    
    # Create dummy memories
    memories = [
        {"id": i, "importance": 0.1 + (i * 0.1)} 
        for i in range(10)
    ]
    
    # Enforce limits
    cleaned = limiter.enforce_limits(memories)
    
    assert len(cleaned) == 5, f"Expected 5 memories, got {len(cleaned)}"
    logger.info(f"✅ Memory limit enforced: {len(memories)} → {len(cleaned)}")


def test_prediction_cooldown():
    """Test prediction spam prevention."""
    logger.info("\n🧪 TEST 2: Prediction Cooldown")
    
    cooldown = PredictionCooldown(min_interval_seconds=1, max_predictions_per_hour=5)
    
    # First prediction should work
    assert cooldown.can_predict(), "First prediction should be allowed"
    cooldown.record_prediction()
    logger.info("✅ First prediction recorded")
    
    # Immediate second prediction should be blocked
    assert not cooldown.can_predict(), "Cooldown should prevent immediate prediction"
    logger.info("✅ Cooldown prevented spam prediction")
    
    # After delay, should work
    time.sleep(1.1)
    assert cooldown.can_predict(), "Should be ready after cooldown"
    logger.info("✅ Prediction ready after cooldown period")


def test_hourly_rate_limit():
    """Test hourly prediction rate limit."""
    logger.info("\n🧪 TEST 3: Hourly Rate Limit")
    
    cooldown = PredictionCooldown(min_interval_seconds=0, max_predictions_per_hour=3)
    
    # Record 3 predictions
    for i in range(3):
        cooldown.record_prediction()
    
    # Should be able to record but rate limit kicks in
    assert cooldown.get_predictions_last_hour() == 3
    assert not cooldown.has_cooldown_ready(), "Should be rate-limited"
    
    logger.info(f"✅ Rate limit enforced: {cooldown.max_per_hour}/hour")


def test_reward_decay():
    """Test reward decay for old habits."""
    logger.info("\n🧪 TEST 4: Reward Decay")
    
    decay = ReinforcementDecay(decay_rate=0.95, decay_interval_seconds=1)
    
    # Create sample rewards
    rewards = {
        "explanation": [0.8, 0.9, 0.7],
        "suggestion": [0.5, 0.6]
    }
    
    # Apply decay
    time.sleep(1.1)
    decayed = decay.apply_decay(rewards)
    
    # Check decay was applied
    original_avg = sum(rewards["explanation"]) / len(rewards["explanation"])
    decayed_avg = sum(decayed["explanation"]) / len(decayed["explanation"])
    
    assert decayed_avg < original_avg, "Decay should reduce rewards"
    logger.info(f"✅ Rewards decayed: {original_avg:.2f} → {decayed_avg:.2f}")


def test_performance_monitor():
    """Test performance monitoring."""
    logger.info("\n🧪 TEST 5: Performance Monitor")
    
    monitor = PerformanceMonitor(window_size=10)
    
    # Record some metrics
    for i in range(5):
        monitor.record_response_time(100 + (i * 10))
        monitor.record_memory_usage(50 + (i * 5))
        monitor.record_prediction_accuracy(0.7 + (i * 0.02))
    
    # Check averages
    avg_time = monitor.get_average_response_time()
    avg_mem = monitor.get_avg_memory()
    avg_acc = monitor.get_avg_accuracy()
    
    assert 100 < avg_time < 200, f"Expected avg ~130ms, got {avg_time:.0f}ms"
    assert 50 < avg_mem < 100, f"Expected avg ~70MB, got {avg_mem:.0f}MB"
    assert 0.7 < avg_acc < 0.85, f"Expected avg ~0.78, got {avg_acc:.2f}"
    
    logger.info(f"✅ Metrics tracked: {avg_time:.0f}ms, {avg_mem:.0f}MB, {avg_acc:.0%}")


def test_degradation_detection():
    """Test detection of performance degradation."""
    logger.info("\n🧪 TEST 6: Degradation Detection")
    
    monitor = PerformanceMonitor()
    
    # Record bad metrics
    for _ in range(10):
        monitor.record_response_time(600)  # Slow
        monitor.record_memory_usage(250)   # High
        monitor.record_prediction_accuracy(0.3)  # Low
    
    # Check degradation warnings
    warnings = monitor.check_performance_degradation()
    
    assert warnings["slow_response"], "Should detect slow response"
    assert warnings["high_memory"], "Should detect high memory"
    assert warnings["low_accuracy"], "Should detect low accuracy"
    
    logger.info(f"✅ Degradation detected: {sum(warnings.values())}/3 issues")


def test_async_scheduler():
    """Test async task scheduling."""
    logger.info("\n🧪 TEST 7: Async Task Scheduler")
    
    scheduler = AsyncTaskScheduler()
    
    # Schedule tasks
    scheduler.schedule_pattern_learning({"data": "test"})
    scheduler.schedule_memory_scoring({"data": "test"})
    scheduler.schedule_analytics("test_event", {"data": "test"})
    
    # Check pending count
    assert scheduler.get_pending_count() == 3, "Should have 3 pending tasks"
    
    stats = scheduler.get_stats()
    assert stats["pending"] == 3
    
    logger.info(f"✅ Tasks scheduled: {scheduler.get_pending_count()} pending")


def test_stabilization_engine():
    """Test main stabilization engine."""
    logger.info("\n🧪 TEST 8: Stabilization Engine")
    
    engine = get_stabilization_engine()
    
    # Check initial health
    health = engine.check_system_health()
    assert "healthy" in health
    assert "issues" in health
    
    logger.info(f"✅ Engine healthy: {health['healthy']}")
    
    # Record some activity
    engine.record_api_call(150, success=True)
    engine.record_api_call(200, success=True)
    
    # Check diagnostics
    diag = engine.get_diagnostics()
    assert "metrics" in diag
    assert "memory_limits" in diag
    assert "predictions" in diag
    
    logger.info(f"✅ Diagnostics available with {len(diag)} categories")


def test_safety_insights():
    """Test safety insight generation."""
    logger.info("\n🧪 TEST 9: Safety Insights")
    
    engine = get_stabilization_engine()
    
    # Generate insights
    insights = engine.extract_safety_insights()
    
    assert len(insights) > 0, "Should generate insights"
    
    logger.info(f"✅ Safety insights: {len(insights)} generated")
    for insight in insights:
        logger.info(f"   {insight}")


def test_integrated_safety():
    """Test all safety systems working together."""
    logger.info("\n🧪 TEST 10: Integrated Safety")
    
    engine = get_stabilization_engine()
    
    # Simulate multiple prediction attempts
    can_predict_attempts = []
    for i in range(5):
        can_predict = engine.should_allow_prediction()
        can_predict_attempts.append(can_predict)
        
        if can_predict:
            logger.info(f"   Prediction {i+1}: allowed ✓")
        else:
            logger.info(f"   Prediction {i+1}: blocked (safety)")
    
    # At least some should be allowed, preventing spam
    assert any(can_predict_attempts), "Should allow some predictions"
    
    logger.info(f"✅ Integrated safety working: {sum(can_predict_attempts)}/5 allowed")


def run_all_tests():
    """Run all stabilization tests."""
    logger.info("=" * 70)
    logger.info("🚀 STABILIZATION PHASE TEST SUITE")
    logger.info("Safety Systems & Performance Monitoring")
    logger.info("=" * 70)
    
    tests = [
        test_memory_limiter,
        test_prediction_cooldown,
        test_hourly_rate_limit,
        test_reward_decay,
        test_performance_monitor,
        test_degradation_detection,
        test_async_scheduler,
        test_stabilization_engine,
        test_safety_insights,
        test_integrated_safety,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            logger.error(f"❌ {test.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            logger.error(f"❌ {test.__name__} ERROR: {e}")
            failed += 1
    
    logger.info("\n" + "=" * 70)
    logger.info(f"📊 RESULTS: {passed} passed, {failed} failed")
    logger.info("=" * 70)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
