from typing import List
from .intent import CanonicalIntent
from .plan import create_execution_plan


def build_plan(intent: CanonicalIntent) -> List[str]:
    structured = create_execution_plan(intent)
    return ["intent"] + [step.capability.split(".", 1)[0] for step in structured.steps
                         if step.capability not in {"reasoning.answer", "response.compose"}] + (
                             ["verification"] if intent.requires_verification else []
                         ) + ["reasoning", "response"]
