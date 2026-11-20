"""
Phase 4-5 Test Suite: Proactive & Autonomous Intelligence
"""
import time
from proactive_engine import (
    get_proactive_engine, IntentForecaster, SuggestionRanker, 
    TimingOptimizer, SafetyGuardrails, Suggestion
)
from autonomous_engine import (
    get_autonomous_engine, GoalTracker, ActionPlanner, 
    AutonomousLearner, Goal
)


def test_proactive_intent_forecaster():
    """Test intent prediction"""
    forecaster = IntentForecaster()
    
    # Add interactions
    forecaster.add_interaction("physics", "ask_concept", True)
    forecaster.add_interaction("physics", "request_example", True)
    forecaster.add_interaction("physics", "ask_clarification", True)
    forecaster.add_interaction("physics", "request_example", True)
    
    # Predict next intent after "ask_concept"
    predictions = forecaster.predict_next_intents("physics", "ask_concept")
    assert len(predictions) > 0, "Should predict next intents"
    assert predictions[0][0] == "request_example", "Should predict most common next"
    assert predictions[0][1] > 0.3, "Should have confidence"
    print("✅ Intent forecasting works")


def test_proactive_suggestion_ranker():
    """Test suggestion ranking"""
    ranker = SuggestionRanker()
    
    # Create test suggestions
    s1 = Suggestion(
        text="Example 1", type="test1",
        confidence=0.9, urgency=0.5, relevance=0.8, interruption_cost=0.1,
        timestamp=time.time()
    )
    s2 = Suggestion(
        text="Example 2", type="test2",
        confidence=0.3, urgency=0.2, relevance=0.4, interruption_cost=0.8,
        timestamp=time.time()
    )
    
    ranked = ranker.rank_suggestions([s1, s2], max_show=1)
    assert len(ranked) == 1, "Should return max_show items"
    assert ranked[0].text == "Example 1", "Should rank higher-scoring first"
    print("✅ Suggestion ranking works")


def test_proactive_timing_optimizer():
    """Test timing optimization"""
    timer = TimingOptimizer()
    
    # Should allow first suggestion
    assert timer.should_show_suggestion("study_tip"), "Should allow first suggestion"
    timer.mark_suggestion_shown("study_tip")
    
    # Should block immediate second
    assert not timer.should_show_suggestion("study_tip"), "Should block within min interval"
    
    # Should allow after cooldown
    timer.min_interval_seconds = 0
    assert timer.should_show_suggestion("study_tip"), "Should allow after cooldown"
    
    # Should respect hourly limit
    timer.max_per_hour = 1
    timer.mark_suggestion_shown("study_tip")
    assert not timer.should_show_suggestion("study_tip"), "Should respect hourly limit"
    
    print("✅ Timing optimization works")


def test_proactive_safety_guardrails():
    """Test safety filtering"""
    safety = SafetyGuardrails()
    
    # Safe suggestion
    safe = Suggestion(
        text="Would you like to see an example?", type="test",
        confidence=0.8, urgency=0.5, relevance=0.8, interruption_cost=0.1,
        timestamp=time.time()
    )
    assert safety.is_safe(safe), "Should allow safe suggestion"
    
    # Unsafe suggestion (guilt-inducing)
    unsafe = Suggestion(
        text="You must study harder, why haven't you done this?", type="test",
        confidence=0.8, urgency=0.5, relevance=0.8, interruption_cost=0.1,
        timestamp=time.time()
    )
    assert not safety.is_safe(unsafe), "Should block guilt-inducing message"
    
    filtered = safety.filter_suggestions([safe, unsafe])
    assert len(filtered) == 1, "Should filter out unsafe"
    assert filtered[0] == safe, "Should keep safe"
    
    print("✅ Safety guardrails work")


def test_proactive_engine_full_pipeline():
    """Test complete proactive engine"""
    engine = get_proactive_engine()
    
    # Generate suggestions
    patterns = {
        "study_time_confidence": 0.7,
        "progress_tracking": True
    }
    suggestions = engine.generate_suggestions("physics", "ask_concept", patterns)
    assert len(suggestions) > 0, "Should generate suggestions"
    
    # Filter and rank
    best = engine.filter_and_rank(suggestions)
    assert len(best) <= 2, "Should limit to max_show"
    
    # Record interaction
    engine.record_interaction("physics", "ask_concept", True, patterns)
    
    # Get proactive suggestions
    proactive = engine.get_proactive_suggestions("physics", "ask_concept", patterns)
    assert isinstance(proactive, list), "Should return list"
    
    print("✅ Proactive engine full pipeline works")


def test_autonomous_goal_tracker():
    """Test goal tracking"""
    tracker = GoalTracker()
    
    # Create goal
    goal_id = tracker.create_goal(
        "Master Physics",
        "Complete advanced physics topics",
        target_days=30
    )
    assert goal_id in tracker.goals, "Should create goal"
    
    goal = tracker.goals[goal_id]
    assert goal.status == "active", "Should be active initially"
    
    # Update progress
    tracker.update_goal_progress(goal_id, 0.5)
    assert goal.progress_percentage == 0.5, "Should update progress"
    
    # Mark complete
    tracker.mark_goal_complete(goal_id)
    assert goal.status == "completed", "Should mark complete"
    
    # Get active goals
    tracker.create_goal("Another goal", "Test", 30)
    active = tracker.get_active_goals()
    assert len(active) == 1, "Should have 1 active goal"
    
    print("✅ Goal tracking works")


def test_autonomous_inferred_goals():
    """Test goal inference from patterns"""
    tracker = GoalTracker()
    
    patterns = {
        "study_frequency": 0.8,
        "has_exams": True,
        "interest_robotics": 0.6,
        "learning_style": "project_based"
    }
    
    inferred = tracker.infer_goals_from_patterns(patterns)
    assert len(inferred) > 2, "Should infer multiple goals"
    
    goal_titles = [g[0] for g in inferred]
    assert any("exam" in g.lower() for g in goal_titles), "Should infer exam prep"
    
    print("✅ Goal inference works")


def test_autonomous_action_planner():
    """Test action planning"""
    tracker = GoalTracker()
    planner = ActionPlanner()
    
    # Create goal
    goal_id = tracker.create_goal("Master Physics", "Advanced topics", 30)
    goal = tracker.goals[goal_id]
    
    # Plan actions
    actions = planner.plan_actions_for_goal(goal, {})
    assert len(actions) > 0, "Should generate actions"
    assert len(actions) >= 5, "Should generate multiple phases"
    
    # Get next action
    next_action = planner.get_next_action(goal)
    assert next_action is not None, "Should have next action"
    
    # Execute action
    planner.record_action_execution(next_action, success=True)
    assert next_action.id in planner.executed_actions, "Should record execution"
    
    # Confidence should increase on success
    assert next_action.confidence > 0.7, "Should increase confidence on success"
    
    print("✅ Action planning works")


def test_autonomous_learner():
    """Test autonomous learning"""
    learner = AutonomousLearner()
    
    # Record outcomes
    learner.record_outcome("study_session", True, 0.8)
    learner.record_outcome("study_session", True, 0.7)
    learner.record_outcome("study_session", False, 0.6)
    
    # Check success rate
    assert "study_session" in learner.action_success_rate, "Should track success"
    assert learner.action_success_rate["study_session"] == 2/3, "Should calculate correctly"
    
    # Check autonomy decision
    for i in range(15):
        learner.record_outcome("test_action", i > 10, 0.7)
    
    should_increase = learner.should_increase_autonomy()
    # Should be True if enough actions have good success
    
    print("✅ Autonomous learner works")


def test_autonomous_engine_full_pipeline():
    """Test complete autonomous engine"""
    engine = get_autonomous_engine()
    
    patterns = {
        "study_frequency": 0.8,
        "has_exams": True,
        "interest_robotics": 0.6
    }
    
    # Suggest goal
    goal_suggestion = engine.suggest_goal(patterns)
    assert goal_suggestion is not None, "Should suggest goal"
    
    # Create and plan goal
    plan = engine.create_and_plan_goal(
        "Master Physics",
        "Advanced topics",
        patterns,
        target_days=30
    )
    assert "goal_id" in plan, "Should create goal with plan"
    assert "plan" in plan, "Should include action plan"
    
    goal_id = plan["goal_id"]
    
    # Get recommended action
    action = engine.get_recommended_action(goal_id)
    assert action is not None, "Should have recommended action"
    
    # Execute action (with approval)
    result = engine.execute_recommended_action(action["action_id"], approved=True)
    assert result["status"] in ["executing", "awaiting_approval"], "Should process"
    
    # Update progress
    engine.update_goal_progress(goal_id, 5, 15)
    
    # Check autonomy status
    status = engine.get_autonomy_status()
    assert "autonomous_mode" in status, "Should have autonomy status"
    
    print("✅ Autonomous engine full pipeline works")


def test_phase4_safety_mechanisms():
    """Test all Phase 4 safety mechanisms"""
    engine = get_proactive_engine()
    
    # 1. Suggestion spam prevention
    suggestions = engine.get_proactive_suggestions("physics", "test", {})
    initial_count = len(suggestions)
    
    # Immediately ask again - should get fewer suggestions
    suggestions2 = engine.get_proactive_suggestions("physics", "test", {})
    assert len(suggestions2) <= initial_count, "Should prevent spam"
    
    # 2. Safety guardrails
    blocked = Suggestion(
        text="You must study harder or you'll fail", type="test",
        confidence=0.9, urgency=0.5, relevance=0.8, interruption_cost=0.1,
        timestamp=time.time()
    )
    
    filtered = engine.safety.filter_suggestions([blocked])
    assert len(filtered) == 0, "Should block manipulative content"
    
    # 3. Timing awareness
    engine.timer.set_user_busy(True, duration_seconds=60)
    assert not engine.timer.should_show_suggestion("test"), "Should not interrupt busy user"
    
    print("✅ Phase 4 safety mechanisms work")


def test_phase5_user_control():
    """Test Phase 5 user control mechanisms"""
    engine = get_autonomous_engine()
    
    # User approval always required by default
    assert engine.user_approval_required, "Should require approval by default"
    
    # Create goal and action
    plan = engine.create_and_plan_goal(
        "Test", "Test goal", {},
        target_days=7
    )
    
    action = engine.get_recommended_action(plan["goal_id"])
    
    # Should ask for approval
    result = engine.execute_recommended_action(
        action["action_id"], 
        approved=False
    )
    assert result["status"] == "awaiting_approval", "Should wait for approval"
    
    # With approval
    result2 = engine.execute_recommended_action(
        action["action_id"], 
        approved=True
    )
    assert result2["status"] == "executing", "Should execute with approval"
    
    print("✅ Phase 5 user control works")


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*50)
    print("Phase 4-5 Test Suite")
    print("="*50 + "\n")
    
    tests = [
        # Phase 4 Tests
        ("Intent Forecasting", test_proactive_intent_forecaster),
        ("Suggestion Ranking", test_proactive_suggestion_ranker),
        ("Timing Optimization", test_proactive_timing_optimizer),
        ("Safety Guardrails", test_proactive_safety_guardrails),
        ("Proactive Engine", test_proactive_engine_full_pipeline),
        ("Phase 4 Safety", test_phase4_safety_mechanisms),
        
        # Phase 5 Tests
        ("Goal Tracking", test_autonomous_goal_tracker),
        ("Goal Inference", test_autonomous_inferred_goals),
        ("Action Planning", test_autonomous_action_planner),
        ("Autonomous Learning", test_autonomous_learner),
        ("Autonomous Engine", test_autonomous_engine_full_pipeline),
        ("Phase 5 Control", test_phase5_user_control),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {name}: ERROR: {e}")
            failed += 1
    
    print("\n" + "="*50)
    print(f"📊 RESULTS: {passed} passed, {failed} failed")
    print("="*50)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)

