"""
Test suite for Phase 2: Pattern Detection & Memory Importance
Tests memory importance calculator, pattern detector, and core memory integration.
"""

import time
import logging
from pattern_detector import PatternDetector, get_pattern_detector
from memory_importance_calculator import (
    MemoryImportanceCalculator,
    get_importance_calculator
)
from core.memory_core import process_memory, importance_score

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_memory_importance_emotional():
    """Test emotional scoring in importance calculator."""
    logger.info("\n🧪 TEST 1: Memory Importance - Emotional Scoring")
    
    calculator = get_importance_calculator()
    
    # High emotional content
    emotional_text = "I'm really anxious about my physics exam!!! 😭"
    score = calculator.calculate_importance(emotional_text)
    
    assert score > 0.6, f"Expected >0.6 for emotional text, got {score}"
    logger.info(f"✅ Emotional text scored: {score:.2f}")
    
    # Low emotional content
    neutral_text = "The sky is blue."
    score = calculator.calculate_importance(neutral_text)
    
    assert score < 0.4, f"Expected <0.4 for neutral text, got {score}"
    logger.info(f"✅ Neutral text scored: {score:.2f}")


def test_memory_importance_repetition():
    """Test repetition scoring."""
    logger.info("\n🧪 TEST 2: Memory Importance - Repetition Scoring")
    
    calculator = get_importance_calculator()
    
    # First mention
    text = "I like robotics"
    score1 = calculator.calculate_importance(text, topic="robotics")
    
    # Repeated mentions
    score2 = calculator.calculate_importance(text, topic="robotics")
    score3 = calculator.calculate_importance(text, topic="robotics")
    
    # Later mentions should have higher scores (repetition increases weight)
    assert score3 >= score1, f"Expected repetition to increase score"
    logger.info(f"✅ Repetition scoring: {score1:.2f} → {score3:.2f}")


def test_memory_importance_recency():
    """Test recency decay."""
    logger.info("\n🧪 TEST 3: Memory Importance - Recency Decay")
    
    calculator = get_importance_calculator()
    
    text = "I love studying"
    
    # Recent timestamp
    now = time.time()
    score_now = calculator.calculate_importance(text, timestamp=now)
    
    # Old timestamp (30 days ago)
    old = now - (30 * 24 * 3600)
    score_old = calculator.calculate_importance(text, timestamp=old)
    
    # Recency should make recent scores higher
    assert score_now >= score_old, f"Expected recency to affect score"
    logger.info(f"✅ Recency: Recent={score_now:.2f}, Old={score_old:.2f}")


def test_pattern_detector_schedule():
    """Test schedule pattern detection."""
    logger.info("\n🧪 TEST 4: Pattern Detection - Schedule")
    
    detector = PatternDetector()
    
    # Simulate morning activities
    morning_time = time.time()
    for i in range(5):
        detector.schedule.record_activity(morning_time + (i * 3600))
    
    pattern = detector.schedule.extract_pattern()
    peak_hours = pattern["peak_study_hours"]
    
    assert len(peak_hours) > 0, "Expected peak hours detected"
    logger.info(f"✅ Peak study hours: {peak_hours}")


def test_pattern_detector_interests():
    """Test interest pattern detection."""
    logger.info("\n🧪 TEST 5: Pattern Detection - Interests")
    
    detector = PatternDetector()
    
    # Record mentions with different sentiments
    detector.interests.record_mention("physics", sentiment=0.2)  # Anxious
    detector.interests.record_mention("physics", sentiment=0.1)  # More anxious
    detector.interests.record_mention("robotics", sentiment=0.9) # Enthusiastic
    detector.interests.record_mention("robotics", sentiment=0.95)
    
    pattern = detector.interests.extract_pattern()
    anxiety = pattern["anxiety_levels"]
    
    assert anxiety.get("physics", 0) > 0.7, "Physics should show high anxiety"
    assert anxiety.get("robotics", 0) < 0.2, "Robotics should show low anxiety"
    
    logger.info(f"✅ Anxiety levels: {anxiety}")


def test_pattern_detector_learning_style():
    """Test learning style detection."""
    logger.info("\n🧪 TEST 6: Pattern Detection - Learning Style")
    
    detector = PatternDetector()
    
    messages = [
        "Can you show me an example?",
        "I need visual diagrams",
        "Explain the theory please"
    ]
    
    for msg in messages:
        detector.communication.record_message(msg)
        if "example" in msg.lower():
            detector.learning_style.record_preference("example-based")
        if "visual" in msg.lower() or "diagram" in msg.lower():
            detector.learning_style.record_preference("visual")
        if "explain" in msg.lower():
            detector.learning_style.record_preference("analytical")
    
    pattern = detector.learning_style.extract_pattern()
    
    assert pattern["dominant_style"] in ["example-based", "visual", "analytical"], \
        "Expected a detected learning style"
    
    logger.info(f"✅ Dominant learning style: {pattern['dominant_style']}")


def test_user_profile_generation():
    """Test full user profile generation."""
    logger.info("\n🧪 TEST 7: User Profile Generation")
    
    detector = get_pattern_detector()
    
    # Simulate a user pattern
    for i in range(3):
        detector.process_conversation(
            f"I'm studying physics and it makes me anxious",
            "Let me help you",
            subject_tags=["physics"],
            sentiment=0.3,
            engagement=0.7,
            timestamp=time.time()
        )
    
    profile = detector.get_user_profile()
    
    assert "prefers_morning_study" in profile
    assert "anxiety_levels" in profile
    assert "communication_style" in profile
    assert profile["confidence"] > 0.0
    
    logger.info(f"✅ User profile confidence: {profile['confidence']:.2f}")
    logger.info(f"   Top interests: {profile['top_interests']}")
    logger.info(f"   Communication style: {profile['communication_style']}")


def test_actionable_insights():
    """Test actionable insights generation."""
    logger.info("\n�912 TEST 8: Actionable Insights")
    
    detector = PatternDetector()
    
    # Build patterns
    detector.process_conversation(
        "I love robotics and prefer morning study",
        "",
        subject_tags=["robotics"],
        sentiment=0.9,
        timestamp=time.time()
    )
    
    insights = detector.get_actionable_insights()
    
    assert len(insights) > 0, "Expected actionable insights"
    logger.info(f"✅ Generated insights:")
    for insight in insights:
        logger.info(f"   - {insight}")


def test_memory_core_integration():
    """Test integration of importance calculator with memory core."""
    logger.info("\n🧪 TEST 9: Memory Core Integration")
    
    # Critical memory
    critical_memory = "I'm terrified of physics exams!!! 😭😭😭"
    result = process_memory(critical_memory)
    
    assert result["importance"] > 0.7, "Expected high importance"
    assert result["importance_category"] == "critical"
    logger.info(f"✅ Critical memory: {result['importance_category']} ({result['importance']:.2f})")
    
    # Medium importance
    medium_memory = "I like learning new things"
    result = process_memory(medium_memory)
    
    assert 0.3 < result["importance"] < 0.7, "Expected medium importance"
    logger.info(f"✅ Medium memory: {result['importance_category']} ({result['importance']:.2f})")
    
    # Low importance
    low_memory = "The sky is blue"
    result = process_memory(low_memory)
    
    assert result["importance"] < 0.4, "Expected low importance"
    logger.info(f"✅ Low memory: {result['importance_category']} ({result['importance']:.2f})")


def test_importance_score_function():
    """Test the importance_score function with topic."""
    logger.info("\n🧪 TEST 10: Direct Importance Score Function")
    
    # Test physics anxiety
    text = "Physics makes me very anxious! I don't understand it at all 😞"
    score = importance_score(text, topic="physics")
    
    assert score > 0.5, f"Expected >0.5 for anxious physics text, got {score}"
    logger.info(f"✅ Physics anxiety score: {score:.2f}")
    
    # Test neutral
    text = "2 + 2 = 4"
    score = importance_score(text, topic="math")
    
    assert score < 0.5, f"Expected <0.5 for neutral math text, got {score}"
    logger.info(f"✅ Neutral math score: {score:.2f}")


def run_all_tests():
    """Run all Phase 2 tests."""
    logger.info("=" * 60)
    logger.info("🚀 PHASE 2 TEST SUITE: Pattern Detection & Memory Importance")
    logger.info("=" * 60)
    
    tests = [
        test_memory_importance_emotional,
        test_memory_importance_repetition,
        test_memory_importance_recency,
        test_pattern_detector_schedule,
        test_pattern_detector_interests,
        test_pattern_detector_learning_style,
        test_user_profile_generation,
        test_actionable_insights,
        test_memory_core_integration,
        test_importance_score_function,
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
    
    logger.info("\n" + "=" * 60)
    logger.info(f"📊 RESULTS: {passed} passed, {failed} failed")
    logger.info("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
