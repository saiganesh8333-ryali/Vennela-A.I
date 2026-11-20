from enum import Enum
from typing import List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field
from .intent import CanonicalIntent


class PlanStep(BaseModel):
    step_id: str
    capability: str
    depends_on: List[str] = Field(default_factory=list)
    parallel_group: Optional[str] = None
    supports_parallel: bool = True
    requires_verification: bool = False


class ExecutionPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: f"plan-{uuid4().hex[:10]}")
    steps: List[PlanStep] = Field(default_factory=list)
    join_required: bool = False

    @property
    def plan_steps(self) -> List[str]:
        return [step.capability for step in self.steps]

    @property
    def dependencies(self) -> dict[str, List[str]]:
        return {step.step_id: step.depends_on for step in self.steps}

    @property
    def parallel_groups(self) -> dict[str, List[str]]:
        groups: dict[str, List[str]] = {}
        for step in self.steps:
            if step.parallel_group:
                groups.setdefault(step.parallel_group, []).append(step.step_id)
        return groups


def create_execution_plan(intent: CanonicalIntent) -> ExecutionPlan:
    steps: List[PlanStep] = []
    for index, capability in enumerate(intent.requested_capabilities):
        step_id = f"capability-{index + 1}"
        depends_on: List[str] = []
        parallel_group = "independent" if intent.is_parallelizable else None
        if capability == "pc.open_app" and "web.research" in intent.requested_capabilities:
            depends_on = ["web-research"] if "search" in intent.user_goal.lower() else []
        if capability == "web.research":
            step_id = "web-research"
        steps.append(PlanStep(
            step_id=step_id, capability=capability, depends_on=depends_on,
            parallel_group=parallel_group,
            requires_verification=capability.startswith(("pc.", "android.")),
        ))
    if intent.requires_reasoning:
        steps.append(PlanStep(step_id="reasoning", capability="reasoning.answer",
                              depends_on=[step.step_id for step in steps]))
    steps.append(PlanStep(step_id="response", capability="response.compose",
                          depends_on=[steps[-1].step_id] if steps else []))
    return ExecutionPlan(steps=steps, join_required=len(intent.requested_capabilities) > 1)
