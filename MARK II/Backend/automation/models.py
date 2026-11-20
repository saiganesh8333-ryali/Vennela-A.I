"""Typed, JSON-serializable automation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ActionType(str, Enum):
    OPEN_APP = "OPEN_APP"
    BATTERY_STATUS = "BATTERY_STATUS"
    CHARGING_STATUS = "CHARGING_STATUS"
    GET_DEVICE_TIME = "GET_DEVICE_TIME"
    FLASHLIGHT_ON = "FLASHLIGHT_ON"
    FLASHLIGHT_OFF = "FLASHLIGHT_OFF"


@dataclass(frozen=True)
class AgentAction:
    type: ActionType
    target: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"type": self.type.value}
        if self.target is not None:
            payload["target"] = self.target
        return {"agent_action": payload}
