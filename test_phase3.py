"""
Test suite for Phase 3: Context Prediction & Reinforcement Learning
Tests context prediction, intent tracking, and reward-based adaptation.
"""

import logging
from context_predictor import (
    IntentPredictor,
    ContextPredictor,
    ResponseContextBuilder,
    PredictionEngine,
    get_prediction_engine
)
from reinforcement_engine import (
    RewardTracker,
    PredictionAccuracyTracker,
    ResponseQualityTracker,
    ReinforcementLearningEngine,
    get_reinforcement_engine
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_intent_prediction():
    """Test intent sequence prediction."""
    logger.info("\n🧪 TEST 1: Intent Sequence Prediction")
    
    predictor = IntentPredictor()
    
    # Record a sequence: ask -> explain -> clarify
    predictor.record_intent("ask_question")
    predictor.record_intent("request_explanation")
    predictor.record_intent("ask_clarification")
    
    # Predict next after "ask_question"
    predictions = predictor.predict_next_intent("ask_question")
    
    assert len(predictions) > 0, "Expected predictions"
    assert predictions[0][0] == "request_explanation", \
        f"Expected 'request_explanation', got {predictions[0][0]}"
    
    logger.info(f"✅ Intent sequence learned: {[p[0] for p in predictions]}")


def test_context_detection():
    """Test context detection from messages."""
    logger.info("\n🧪 TEST 2: Context Detection")
    
    detector = ContextPredictor()
    
    # Test different contexts
    test_cases = [
        ("My code has an error", "debugging"),
        ("Explain quantum physics", "learning"),
        ("Show me an example", "code_example"),
        ("Let's plan the project", "planning"),
        ("Can you help me?", "help_request"),
    ]
    
    for message, expected_context in test_cases:
        context = detector.detect_context(message)
        assert context == expected_context, \
            f"Expected {expected_context}, got {context}"
        logger.info(f"  ✅ Detected '{context}' from: {message[:30]}...")


def test_context_sequencing():
    """Test context sequence prediction."""
    logger.info("\n🧪 TEST 3: Context Sequencing")
    
    detector = ContextPredictor()
    
    # Simulate typical flow: learn -> ask clarification -> get example
    detector.record_context("learning")
    detector.record_context("help_request")
    detector.record_context("code_example")
    
    pattern = detector.extract_pattern()
    
    assert "context_distribution" in pattern
    assert len(pattern["context_distribution"]) > 0
    
    logger.info(f"✅ Context distribution: {pattern['context_distribution']}")


def test_response_context_building():
    """Test building response context from conversation."""
    logger.info("\n🧪 TEST 4: Response Context Building")
    
    builder = ResponseContextBuilder()
    
    # Add some exchanges
    builder.add_exchange(
        "How do I learn robotics?",
        "Start with basic concepts and practice projects."
    )
    builder.add_exchange(
        "Can you give an example?",
        "Sure! A simple robot arm project..."
    )
    
    # Check context
    conv_len = builder.get_conversation_length()
    topic = builder.get_topic_from_history()
    recent = builder.get_recent_context(2)
    
    assert conv_len == 2, f"Expected 2 exchanges, got {conv_len}"
    assert "robotics" in topic.lower() or topic == "general", f"Expected robotics or general topic"
    assert "robotics" in recent.lower() or "arm" in recent.lower()
    
    logger.info(f"✅ Conversation context built: {conv_len} exchanges, topic={topic}")


def test_prediction_engine():
    """Test full prediction engine."""
    logger.info("\n🧪 TEST 5: Full Prediction Engine")
    
    engine = get_prediction_engine()
    
    # Process exchanges
    exchanges = [
        ("How do I learn Python?", "Start with basics..."),
        ("Show me an example", "Here's a simple example..."),
        ("How do I debug this?", "Use print statements..."),
    ]
    
    for user_msg, ai_resp in exchanges:
        engine.process_exchange(
            user_msg,
            ai_resp,
            user_intent="ask_for_help",
            confidence=0.8
        )
    
    # Get next turn prediction
    prediction = engine.predict_next_turn()
    
    assert "conversation_length" in prediction
    assert prediction["conversation_length"] == 3
    
    logger.info(f"✅ Prediction engine ready: {prediction['conversation_length']} exchanges")


def test_reward_tracker():
    """Test reward tracking."""
    logger.info("\n🧪 TEST 6: Reward Tracking")
    
    tracker = RewardTracker()
    
    # Record rewards for different actions
    tracker.record_reward("suggestion", 0.8)  # Good suggestion
    tracker.record_reward("suggestion", 0.7)  # Another good suggestion
    tracker.record_reward("suggestion", -0.2) # Bad suggestion
    tracker.record_reward("explanation", 0.9) # Great explanation
    
    # Check quality
    suggestion_quality = tracker.get_action_quality("suggestion")
    explanation_quality = tracker.get_action_quality("explanation")
    
    assert suggestion_quality > 0, "Suggestion should have positive quality"
    assert explanation_quality > suggestion_quality, "Explanation should be better"
    
    top_actions = tracker.get_top_actions(2)
    logger.info(f"✅ Top actions: {[(a[0], f'{a[1]:.2f}') for a in top_actions]}")


def test_prediction_accuracy_tracking():
    """Test tracking prediction accuracy."""
    logger.info("\n🧪 TEST 7: Prediction Accuracy Tracking")
    
    tracker = PredictionAccuracyTracker()
    
    # Record correct predictions
    tracker.record_prediction("intent", "ask_question", "ask_question", confidence=0.9)
    tracker.record_prediction("intent", "ask_question", "ask_question", confidence=0.85)
    tracker.record_prediction("intent", "ask_question", "request_code", confidence=0.8)  # Wrong
    
    accuracy = tracker.get_accuracy()
    high_conf_accuracy = tracker.get_high_confidence_accuracy()
    
    assert 0.6 < accuracy < 1.0, f"Expected accuracy between 0.6-1.0, got {accuracy}"
    assert high_conf_accuracy >= accuracy, "High confidence should have better or equal accuracy"
    
    logger.info(f"✅ Prediction accuracy: overall={accuracy:.0%}, high_conf={high_conf_accuracy:.0%}")


def test_reinforcement_learning():
    """Test reinforcement learning engine."""
    logger.info("\n🧪 TEST 8: Reinforcement Learning Engine")
    
    engine = get_reinforcement_engine()
    
    # Record several interactions
    for i in range(5):
        engine.record_interaction(
            "explanation",
            user_feedback={
                "engaged": i % 2 == 0,  # Every other user is engaged
                "helpful": True,
                "quick": True
            },
            response_quality=0.7 + (i * 0.05)
        )
    
    # Check learning
    practices = engine.get_best_practices()
    insights = engine.extract_insights()
    
    assert len(practices["best_actions"]) > 0
    assert len(insights) > 0
    
    logger.info(f"✅ Learned best practices: {practices['best_actions'][0]}")
    for insight in insights:
        logger.info(f"   {insight}")


def test_reward_calculation():
    """Test comprehensive reward calculation."""
    logger.info("\n🧪 TEST 9: Reward Calculation")
    
    engine = get_reinforcement_engine()
    
    # Test different scenarios
    scenarios = [
        {
            "name": "Perfect interaction",
            "params": {
                "user_engaged": True,
                "response_helpful": True,
                "prediction_accurate": True,
                "response_time_good": True,
                "suggestion_accepted": True
            },
            "expected_sign": "positive"
        },
        {
            "name": "Poor interaction",
            "params": {
                "user_engaged": False,
                "response_helpful": False,
                "prediction_accurate": False,
                "response_time_good": False,
                "suggestion_accepted": False
            },
            "expected_sign": "negative"
        }
    ]
    
    for scenario in scenarios:
        reward = engine.calculate_reward(**scenario["params"])
        expected_positive = scenario["expected_sign"] == "positive"
        assert (reward > 0) == expected_positive, \
            f"Failed for {scenario['name']}"
        logger.info(f"✅ {scenario['name']}: reward={reward:.2f}")


def test_learning_curve():
    """Test learning curve generation."""
    logger.info("\n🧪 TEST 10: Learning Curve")
    
    engine = get_reinforcement_engine()
    
    # Create some learning history
    for i in range(30):
        reward = -0.5 + (i * 0.03)  # Gradually improving
        engine.record_interaction(
            "suggestion",
            response_quality=0.4 + (i * 0.02)
        )
    
    curve = engine.get_learning_curve()
    
    assert len(curve) > 0, "Expected learning curve data"
    
    if len(curve) > 1:
        # Check if improving
        first_reward = curve[0][1]
        last_reward = curve[-1][1]
        improving = last_reward >= first_reward
        logger.info(f"✅ Learning curve: {len(curve)} points, improving={improving}")
    else:
        logger.info(f"✅ Learning curve started: {len(curve)} point")


def run_all_tests():
    """Run all Phase 3 tests."""
    logger.info("=" * 60)
    logger.info("🚀 PHASE 3 TEST SUITE: Context Prediction & RL Learning")
    logger.info("=" * 60)
    
    tests = [
        test_intent_prediction,
        test_context_detection,
        test_context_sequencing,
        test_response_context_building,
        test_prediction_engine,
        test_reward_tracker,
        test_prediction_accuracy_tracking,
        test_reinforcement_learning,
        test_reward_calculation,
        test_learning_curve,
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
