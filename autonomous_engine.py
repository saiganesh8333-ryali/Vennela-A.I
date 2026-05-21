"""
Phase 5: Autonomous Proactive Intelligence
Multi-step planning, goal tracking, and autonomous learning
"""
import json
import time
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict


@dataclass
class Goal:
    """User goal with tracking"""
    id: str
    title: str
    description: str
    created_at: float
    target_completion: Optional[float] = None
    status: str = "active"  # active, completed, abandoned
    related_topics: List[str] = field(default_factory=list)
    progress_percentage: float = 0.0
    sub_goals: List[str] = field(default_factory=list)
    priority: float = 0.5  # 0.0 to 1.0


@dataclass
class AutonomousAction:
    """Planned action by the system"""
    id: str
    goal_id: str
    action_type: str  # study_session, break, review, practice
    description: str
    suggested_time: float
    duration_minutes: int
    confidence: float
    prerequisites: List[str] = field(default_factory=list)
    expected_outcome: str = ""


class GoalTracker:
    """Track and manage user goals"""
    
    def __init__(self):
        self.goals: Dict[str, Goal] = {}
        self.goal_id_counter = 0
        self.goal_progress_history = defaultdict(list)
        
    def create_goal(self, title: str, description: str, 
                   target_days: int = 30) -> str:
        """Create new goal"""
        goal_id = f"goal_{self.goal_id_counter}"
        self.goal_id_counter += 1
        
        target_completion = time.time() + (target_days * 86400)
        
        goal = Goal(
            id=goal_id,
            title=title,
            description=description,
            created_at=time.time(),
            target_completion=target_completion
        )
        self.goals[goal_id] = goal
        return goal_id
    
    def update_goal_progress(self, goal_id: str, progress: float):
        """Update goal progress"""
        if goal_id in self.goals:
            self.goals[goal_id].progress_percentage = progress
            self.goal_progress_history[goal_id].append({
                "timestamp": time.time(),
                "progress": progress
            })
            if len(self.goal_progress_history[goal_id]) > 500:
                self.goal_progress_history[goal_id].pop(0)
    
    def mark_goal_complete(self, goal_id: str):
        """Mark goal as completed"""
        if goal_id in self.goals:
            self.goals[goal_id].status = "completed"
            self.goals[goal_id].progress_percentage = 1.0
    
    def get_active_goals(self) -> List[Goal]:
        """Get all active goals"""
        return [g for g in self.goals.values() if g.status == "active"]
    
    def infer_goals_from_patterns(self, user_patterns: Dict) -> List[Tuple[str, float]]:
        """Infer likely goals from user patterns"""
        inferred = []
        
        if user_patterns.get("study_frequency", 0) > 0.6:
            inferred.append(("Improve knowledge in main subjects", 0.8))
        
        if user_patterns.get("has_exams", False):
            inferred.append(("Prepare for upcoming exams", 0.9))
        
        if user_patterns.get("interest_robotics", 0) > 0.5:
            inferred.append(("Build robotics expertise", 0.7))
        
        if user_patterns.get("learning_style") == "project_based":
            inferred.append(("Complete practical projects", 0.8))
        
        return inferred


class ActionPlanner:
    """Plan autonomous actions to achieve goals"""
    
    def __init__(self):
        self.planned_actions: Dict[str, AutonomousAction] = {}
        self.action_id_counter = 0
        self.executed_actions = []
        
    def plan_actions_for_goal(self, goal: Goal, 
                             user_patterns: Dict) -> List[AutonomousAction]:
        """Generate plan to achieve goal"""
        actions = []
        
        days_available = (goal.target_completion - time.time()) / 86400
        total_sessions_needed = max(5, int(days_available * 0.7))  # 70% of days
        
        # Phase 1: Foundation building (40% of time)
        foundation_sessions = int(total_sessions_needed * 0.4)
        for i in range(foundation_sessions):
            action_id = f"action_{self.action_id_counter}"
            self.action_id_counter += 1
            
            action = AutonomousAction(
                id=action_id,
                goal_id=goal.id,
                action_type="study_session",
                description=f"Foundation study: {goal.title} - Session {i+1}",
                suggested_time=time.time() + (i * 86400),
                duration_minutes=45,
                confidence=0.8,
                expected_outcome="Build foundational understanding"
            )
            actions.append(action)
        
        # Phase 2: Deep learning (40% of time)
        deep_sessions = int(total_sessions_needed * 0.4)
        for i in range(deep_sessions):
            action_id = f"action_{self.action_id_counter}"
            self.action_id_counter += 1
            
            action = AutonomousAction(
                id=action_id,
                goal_id=goal.id,
                action_type="study_session",
                description=f"Deep learning: {goal.title} - Session {i+1}",
                suggested_time=time.time() + ((foundation_sessions + i) * 86400),
                duration_minutes=60,
                confidence=0.75,
                prerequisites=[f"action_{self.action_id_counter - foundation_sessions - i - 1}"],
                expected_outcome="Develop comprehensive understanding"
            )
            actions.append(action)
        
        # Phase 3: Practice & consolidation (20% of time)
        practice_sessions = total_sessions_needed - foundation_sessions - deep_sessions
        for i in range(practice_sessions):
            action_id = f"action_{self.action_id_counter}"
            self.action_id_counter += 1
            
            action = AutonomousAction(
                id=action_id,
                goal_id=goal.id,
                action_type="practice",
                description=f"Practice & consolidate: {goal.title} - Session {i+1}",
                suggested_time=time.time() + ((foundation_sessions + deep_sessions + i) * 86400),
                duration_minutes=40,
                confidence=0.7,
                prerequisites=[f"action_{self.action_id_counter - practice_sessions - i - 1}"],
                expected_outcome="Master and retain knowledge"
            )
            actions.append(action)
        
        self.planned_actions.update({a.id: a for a in actions})
        return actions
    
    def get_next_action(self, goal: Goal) -> Optional[AutonomousAction]:
        """Get next recommended action for a goal"""
        goal_actions = [
            a for a in self.planned_actions.values() 
            if a.goal_id == goal.id
        ]
        
        # Find first incomplete action with met prerequisites
        for action in sorted(goal_actions, key=lambda x: x.suggested_time):
            prerequisites_met = all(
                prereq in [a.id for a in self.executed_actions]
                for prereq in action.prerequisites
            )
            
            if prerequisites_met:
                return action
        
        return None
    
    def record_action_execution(self, action: AutonomousAction, 
                               success: bool = True):
        """Record that action was executed"""
        self.executed_actions.append(action.id)
        if success:
            action.confidence = min(1.0, action.confidence + 0.05)


class AutonomousLearner:
    """Learn from interactions to improve autonomy"""
    
    def __init__(self):
        self.suggestion_outcomes = defaultdict(list)
        self.action_success_rate = defaultdict(float)
        self.user_preferences = {}
        self.learning_rate = 0.1
        
    def record_outcome(self, action_type: str, outcome: bool, 
                      confidence: float):
        """Record action outcome"""
        self.suggestion_outcomes[action_type].append({
            "timestamp": time.time(),
            "outcome": outcome,
            "confidence": confidence
        })
        
        # Keep history manageable
        if len(self.suggestion_outcomes[action_type]) > 100:
            self.suggestion_outcomes[action_type].pop(0)
        
        # Update success rate
        outcomes = self.suggestion_outcomes[action_type]
        success_count = sum(1 for o in outcomes if o["outcome"])
        self.action_success_rate[action_type] = success_count / len(outcomes)
    
    def should_increase_autonomy(self) -> bool:
        """Check if system should become more autonomous"""
        if not self.action_success_rate:
            return False
        
        avg_success = sum(self.action_success_rate.values()) / len(self.action_success_rate)
        return avg_success > 0.7
    
    def adapt_strategy(self, action_type: str):
        """Adapt strategy based on success rates"""
        success_rate = self.action_success_rate.get(action_type, 0.5)
        
        if success_rate < 0.5:
            # Too many failures, reduce confidence
            return {"reduce_confidence": True, "factor": 0.9}
        elif success_rate > 0.8:
            # Very successful, increase autonomy
            return {"increase_autonomy": True, "factor": 1.1}
        else:
            # Moderate success, keep as is
            return {"maintain": True}


class AutonomousEngine:
    """Main orchestrator for Phase 5"""
    
    def __init__(self):
        self.goal_tracker = GoalTracker()
        self.action_planner = ActionPlanner()
        self.learner = AutonomousLearner()
        self.autonomous_mode = False  # User enables this
        self.user_approval_required = True  # Safety: always ask user first
        
    def suggest_goal(self, user_patterns: Dict) -> Optional[Tuple[str, float]]:
        """Suggest a goal based on patterns"""
        inferred = self.goal_tracker.infer_goals_from_patterns(user_patterns)
        
        if inferred:
            # Return most confident goal
            return max(inferred, key=lambda x: x[1])
        
        return None
    
    def create_and_plan_goal(self, title: str, description: str,
                            user_patterns: Dict,
                            target_days: int = 30) -> Dict:
        """Create goal and generate action plan"""
        goal_id = self.goal_tracker.create_goal(
            title, description, target_days
        )
        goal = self.goal_tracker.goals[goal_id]
        
        actions = self.action_planner.plan_actions_for_goal(goal, user_patterns)
        
        return {
            "goal_id": goal_id,
            "goal": {
                "title": goal.title,
                "description": goal.description,
                "target_days": target_days
            },
            "plan": {
                "total_actions": len(actions),
                "total_hours": sum(a.duration_minutes for a in actions) / 60,
                "phases": {
                    "foundation": sum(1 for a in actions if a.action_type == "study_session")[:1],
                    "deep_learning": sum(1 for a in actions if a.action_type == "study_session")[1:2],
                    "practice": sum(1 for a in actions if a.action_type == "practice")
                }
            }
        }
    
    def get_recommended_action(self, goal_id: str) -> Optional[Dict]:
        """Get recommended next action"""
        goal = self.goal_tracker.goals.get(goal_id)
        if not goal:
            return None
        
        action = self.action_planner.get_next_action(goal)
        if not action:
            return None
        
        return {
            "action_id": action.id,
            "type": action.action_type,
            "description": action.description,
            "duration_minutes": action.duration_minutes,
            "confidence": action.confidence,
            "expected_outcome": action.expected_outcome,
            "user_approval_required": True
        }
    
    def execute_recommended_action(self, action_id: str, 
                                  approved: bool = False) -> Dict:
        """Execute recommended action (with user approval)"""
        action = self.action_planner.planned_actions.get(action_id)
        if not action:
            return {"error": "Action not found"}
        
        if not approved and self.user_approval_required:
            return {
                "status": "awaiting_approval",
                "action_id": action_id,
                "message": f"Ready to {action.action_type}: {action.description}"
            }
        
        # Record execution
        self.action_planner.record_action_execution(action)
        
        return {
            "status": "executing",
            "action_id": action_id,
            "message": f"Starting: {action.description}",
            "duration_minutes": action.duration_minutes
        }
    
    def update_goal_progress(self, goal_id: str, 
                            completed_actions: int,
                            total_actions: int):
        """Update goal progress"""
        progress = min(1.0, completed_actions / max(1, total_actions))
        self.goal_tracker.update_goal_progress(goal_id, progress)
        
        if progress >= 1.0:
            self.goal_tracker.mark_goal_complete(goal_id)
    
    def enable_autonomous_mode(self, enabled: bool):
        """Enable/disable autonomous mode"""
        self.autonomous_mode = enabled
        # User can always require approval
    
    def get_autonomy_status(self) -> Dict:
        """Get current autonomy status"""
        active_goals = self.goal_tracker.get_active_goals()
        
        return {
            "autonomous_mode": self.autonomous_mode,
            "active_goals": len(active_goals),
            "learner_success_rate": {
                k: v for k, v in self.learner.action_success_rate.items()
            },
            "should_increase_autonomy": self.learner.should_increase_autonomy(),
            "user_approval_always_required": self.user_approval_required
        }


# Singleton
_autonomous_engine = None

def get_autonomous_engine() -> AutonomousEngine:
    """Get or create autonomous engine"""
    global _autonomous_engine
    if _autonomous_engine is None:
        _autonomous_engine = AutonomousEngine()
    return _autonomous_engine

