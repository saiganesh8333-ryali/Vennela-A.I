"""Natural-language automation detection and deterministic action generation."""

from __future__ import annotations

from dataclasses import dataclass

from .models import ActionType, AgentAction
from .registry import action_registry
from .validators import ActionValidationError, validate_action


@dataclass(frozen=True)
class AutomationResult:
    is_automation: bool
    action: AgentAction | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {"is_automation": self.is_automation}
        if self.action is not None:
            result.update(self.action.to_dict())
        if self.error is not None:
            result["error"] = self.error
        return result


class AutomationEngine:
    def __init__(self) -> None:
        self._actions = action_registry()

    def process(self, request: str | None) -> AutomationResult:
        original = " ".join((request or "").split())
        text = original.lower()
        if not original:
            return AutomationResult(False)
        if not self._looks_like_automation(text):
            return AutomationResult(False)
        for definition in self._actions.values():
            target = definition.matcher(text)
            matched = target is not None
            if definition.action_type is ActionType.OPEN_APP and target is not None:
                target = original[len(original) - len(target):]
            elif target == "":
                target = None
            if not matched:
                continue
            try:
                return AutomationResult(True, validate_action(AgentAction(definition.action_type, target)))
            except ActionValidationError as exc:
                return AutomationResult(True, error=str(exc))
        return AutomationResult(True, error="unsupported or ambiguous automation request")

    @staticmethod
    def _looks_like_automation(text: str) -> bool:
        return (
            text.startswith(("open ", "launch ", "start ", "turn ", "switch ", "enable ", "disable "))
            or any(
                word in text
                for word in (
                    "automation",
                    "automate",
                    "device operation",
                    "battery",
                    "charging",
                    "flashlight",
                    "torch",
                    "what time",
                    "current time",
                )
            )
        )
