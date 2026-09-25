import json
from vennela_langgraph.core.capabilities import CAPABILITY_REGISTRY
from vennela_langgraph.core.plan import ExecutionPlan
from .contracts import LLMRequest


def validate_execution_plan(plan: ExecutionPlan, intent) -> ExecutionPlan:
    step_ids = {step.step_id for step in plan.steps}
    for step in plan.steps:
        if step.capability not in CAPABILITY_REGISTRY:
            raise ValueError(f"CAPABILITY_NOT_SUPPORTED: {step.capability}")
        missing = set(step.depends_on) - step_ids
        if missing:
            raise ValueError(f"DEPENDENCY: missing step(s) {sorted(missing)}")
    visiting, visited = set(), set()

    def visit(step_id):
        if step_id in visiting:
            raise ValueError("DEPENDENCY: cycle detected")
        if step_id in visited:
            return
        visiting.add(step_id)
        step = next(item for item in plan.steps if item.step_id == step_id)
        for dependency in step.depends_on:
            visit(dependency)
        visiting.remove(step_id)
        visited.add(step_id)

    for step_id in step_ids:
        visit(step_id)
    planned = {step.capability for step in plan.steps}
    missing_capabilities = set(intent.requested_capabilities) - planned
    if missing_capabilities:
        raise ValueError(f"SCHEMA: missing required capabilities {sorted(missing_capabilities)}")
    return plan


class LLMPlannerAdapter:
    def __init__(self, router, max_retries: int = 1):
        self.router, self.max_retries = router, max_retries

    def plan(self, intent, request_id: str) -> ExecutionPlan:
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.router.generate(LLMRequest(
                    task="planner", request_id=request_id, retry_count=attempt,
                    payload={"canonical_intent": intent.model_dump()},
                ))
                return validate_execution_plan(ExecutionPlan.model_validate(json.loads(response.content)), intent)
            except Exception as exc:
                last_error = exc
                if not getattr(exc, "retryable", True):
                    break
        raise ValueError(f"planner validation failed after {self.max_retries + 1} attempts: {last_error}")
