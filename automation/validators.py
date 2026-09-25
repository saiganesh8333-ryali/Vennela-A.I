"""Validation for the backend-to-agent action contract."""

from __future__ import annotations

from collections.abc import Mapping

from .models import ActionType, AgentAction


class ActionValidationError(ValueError):
    """Raised when an action cannot be safely sent to the agent."""


def validate_action(action: AgentAction) -> AgentAction:
    if not isinstance(action.type, ActionType):
        raise ActionValidationError("unsupported action type")
    if action.type is ActionType.OPEN_APP:
        if not isinstance(action.target, str) or not action.target.strip():
            raise ActionValidationError("OPEN_APP requires a target")
        return AgentAction(action.type, action.target.strip())
    if action.target is not None:
        raise ActionValidationError(f"{action.type.value} does not accept a target")
    return action


def parse_action(payload: Mapping[str, object]) -> AgentAction:
    raw = payload.get("agent_action", payload)
    if not isinstance(raw, Mapping):
        raise ActionValidationError("agent_action must be an object")
    raw_type = raw.get("type")
    try:
        action_type = ActionType(raw_type)
    except (TypeError, ValueError):
        raise ActionValidationError("unsupported action type") from None
    target = raw.get("target")
    if target is not None and not isinstance(target, str):
        raise ActionValidationError("target must be a string")
    return validate_action(AgentAction(action_type, target))
