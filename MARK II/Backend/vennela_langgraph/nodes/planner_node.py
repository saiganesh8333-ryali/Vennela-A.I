from vennela_langgraph.core.contracts import StateUpdate
from vennela_langgraph.core.plan import create_execution_plan
from vennela_langgraph.core.planner import build_plan
from ._base import BaseNode


class PlannerNode(BaseNode):
    name = "planner"

    def __init__(self, telemetry, planner=None):
        super().__init__(telemetry)
        self.planner = planner

    def execute(self, state):
        structured = self.planner.plan(state.canonical_intent, state.request_id) if self.planner else create_execution_plan(state.canonical_intent)
        plan = build_plan(state.canonical_intent)
        return StateUpdate(values={
            "execution_plan": plan,
            "selected_agents": [step for step in plan if step in {"memory", "web", "pc", "android"}],
            "plan_id": structured.plan_id,
            "plan_details": structured,
            "plan_steps": [step.model_dump() for step in structured.steps],
            "dependencies": structured.dependencies,
            "parallel_groups": structured.parallel_groups,
            "status": "planned",
        })
