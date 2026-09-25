"""Allowlisted action metadata."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

from .models import ActionType


@dataclass(frozen=True)
class ActionDefinition:
    action_type: ActionType
    requires_target: bool
    matcher: Callable[[str], str | None]


def action_registry() -> dict[ActionType, ActionDefinition]:
    return {
        ActionType.OPEN_APP: ActionDefinition(ActionType.OPEN_APP, True, _open_app),
        ActionType.BATTERY_STATUS: ActionDefinition(ActionType.BATTERY_STATUS, False, _battery),
        ActionType.CHARGING_STATUS: ActionDefinition(ActionType.CHARGING_STATUS, False, _charging),
        ActionType.GET_DEVICE_TIME: ActionDefinition(ActionType.GET_DEVICE_TIME, False, _device_time),
        ActionType.FLASHLIGHT_ON: ActionDefinition(ActionType.FLASHLIGHT_ON, False, _flashlight_on),
        ActionType.FLASHLIGHT_OFF: ActionDefinition(ActionType.FLASHLIGHT_OFF, False, _flashlight_off),
    }


def _open_app(text: str) -> str | None:
    for prefix in ("open ", "launch ", "start "):
        if text.startswith(prefix):
            target = text[len(prefix):].strip()
            return target or None
    return None


def _battery(text: str) -> str | None:
    return "" if any(phrase in text for phrase in ("battery", "charge level")) else None


def _charging(text: str) -> str | None:
    return "" if "charg" in text and any(word in text for word in ("am i", "phone", "device", "status", "charging")) else None


def _device_time(text: str) -> str | None:
    return "" if "time" in text and any(word in text for word in ("what", "current", "tell")) else None


def _flashlight_on(text: str) -> str | None:
    return "" if any(word in text for word in ("flashlight", "torch")) and any(word in text for word in ("turn on", "switch on", "enable")) else None


def _flashlight_off(text: str) -> str | None:
    return "" if any(word in text for word in ("flashlight", "torch")) and any(word in text for word in ("turn off", "switch off", "disable")) else None
