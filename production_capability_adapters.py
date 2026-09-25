"""Compatibility adapters from LangGraph capability contracts to NEXUS."""

from __future__ import annotations

import asyncio
import inspect
import threading
from typing import Any


class ProductionPCAgent:
    """Execute supported LangGraph PC actions through the shared NEXUS gateway."""

    _ACTION_TYPES = {
        "OPEN_APP": "OPEN_APP",
        "BATTERY_STATUS": "BATTERY_STATUS",
        "GET_DEVICE_TIME": "GET_DEVICE_TIME",
    }

    def __init__(self, gateway: Any):
        self.gateway = gateway

    def execute(self, action: str) -> dict[str, Any]:
        return self._execute(action, None)

    def execute_with_context(self, action: str, request: str) -> dict[str, Any]:
        return self._execute(action, request)

    def _execute(self, action: str, request: str | None) -> dict[str, Any]:
        try:
            from automation import ActionType, AgentAction
        except ImportError as exc:
            raise RuntimeError("Production automation layer is unavailable") from exc

        action_type_name = self._ACTION_TYPES.get(action.split(":", 1)[0])
        if action_type_name is None:
            raise ValueError(f"Unsupported production PC action: {action}")

        target = None
        if action_type_name == "OPEN_APP":
            target = self._open_app_target(action, request)

        production_action = AgentAction(
            type=ActionType(action_type_name),
            target=target,
        )
        execution, verification = self.gateway.dispatch(
            production_action,
            context={"source": "langgraph"},
        )
        return {
            "action": action,
            "executed": execution.success,
            "result": execution.to_dict(),
            "error": execution.error,
            "verified": verification.verified,
            "verification_status": verification.status.value,
            "verification_message": verification.message,
            "verification_details": verification.details,
        }

    @staticmethod
    def _open_app_target(action: str, request: str | None) -> str:
        """Resolve the target from the canonical action string when present."""
        parts = action.split(":", 1)
        if len(parts) != 2 or not parts[1].strip():
            if request:
                request_parts = request.strip().split(maxsplit=1)
                if len(request_parts) == 2 and request_parts[0].lower() in {
                    "open", "launch", "start",
                }:
                    return request_parts[1].strip()
            raise ValueError("OPEN_APP requires an application target")
        return parts[1].strip()


class ProductionAndroidAgent:
    """Execute supported LangGraph Android actions through the shared gateway."""

    _ACTION_TYPES = {
        "FLASHLIGHT_ON": "FLASHLIGHT_ON",
        "FLASHLIGHT_OFF": "FLASHLIGHT_OFF",
        "BATTERY_STATUS": "BATTERY_STATUS",
        "CHARGING_STATUS": "CHARGING_STATUS",
        "GET_DEVICE_TIME": "GET_DEVICE_TIME",
    }

    def __init__(self, gateway: Any):
        self.gateway = gateway

    def execute(self, action: str) -> dict[str, Any]:
        return self._execute(action, None)

    def execute_with_context(self, action: str, request: str) -> dict[str, Any]:
        return self._execute(action, request)

    def _execute(self, action: str, request: str | None) -> dict[str, Any]:
        try:
            from automation import ActionType, AgentAction, AgentPlatform
        except ImportError as exc:
            raise RuntimeError("Production automation layer is unavailable") from exc

        action_type_name = self._resolve_action(action, request)
        production_action = AgentAction(type=ActionType(action_type_name))
        execution, verification = self.gateway.dispatch(
            production_action,
            preferred_platform=AgentPlatform.ANDROID,
            context={"source": "langgraph"},
        )
        return {
            "action": action,
            "executed": execution.success,
            "verified": verification.verified,
            "status": verification.status.value,
            "error": execution.error,
            "metadata": {
                "execution": execution.to_dict(),
                "verification": {
                    "message": verification.message,
                    "details": verification.details,
                },
            },
        }

    @classmethod
    def _resolve_action(cls, action: str, request: str | None) -> str:
        if action in cls._ACTION_TYPES:
            return cls._ACTION_TYPES[action]
        if action == "FLASHLIGHT" and request:
            normalized = request.lower()
            if any(phrase in normalized for phrase in ("turn off", "switch off", "disable")):
                return "FLASHLIGHT_OFF"
            if any(phrase in normalized for phrase in ("turn on", "switch on", "enable")):
                return "FLASHLIGHT_ON"
        raise ValueError(f"Unsupported production Android action: {action}")


class ProductionWebAgent:
    """Synchronous LangGraph boundary over the existing async WebHuntAgent."""

    def __init__(self, web_hunt_agent: Any):
        if web_hunt_agent is None or not callable(getattr(web_hunt_agent, "run", None)):
            raise ValueError("A configured WebHuntAgent is required")
        self.web_hunt_agent = web_hunt_agent

    def search(self, request: str) -> dict[str, Any]:
        return self._normalize(self._run_web_agent(request), request, None)

    def search_with_context(self, request: str, request_id: str) -> dict[str, Any]:
        return self._normalize(
            self._run_web_agent(request, request_id=request_id),
            request,
            request_id,
        )

    def _normalize(self, result: Any, request: str, request_id: str | None) -> dict[str, Any]:
        payload = result.to_dict()
        status = str(result.metadata.get("status", "")) or (
            "failed" if result.errors_and_warnings else "completed"
        )
        metadata = dict(result.metadata)
        if request_id is not None:
            metadata["langgraph_request_id"] = request_id
        payload.update({
            "executed": status != "failed",
            "verified": bool(result.sources or result.key_findings) and not bool(
                result.errors_and_warnings
            ),
            "status": status,
            "error": result.errors_and_warnings[-1] if result.errors_and_warnings else None,
            "errors": list(result.errors_and_warnings),
            "metadata": metadata,
            "sources": [source.to_dict() for source in result.sources],
            "findings": list(result.key_findings),
            "uncertainties": list(result.uncertainties),
            "evidence": self._evidence_payload(result),
        })
        return payload

    def _run_web_agent(self, request: str, request_id: str | None = None) -> Any:
        outcome: list[Any] = []
        failures: list[Exception] = []

        def run() -> None:
            try:
                if request_id:
                    parameters = inspect.signature(self.web_hunt_agent.run).parameters
                    if "context" in parameters or any(
                        parameter.kind is inspect.Parameter.VAR_KEYWORD
                        for parameter in parameters.values()
                    ):
                        outcome.append(asyncio.run(
                            self.web_hunt_agent.run(
                                request,
                                context={"request_id": request_id},
                            )
                        ))
                    else:
                        outcome.append(asyncio.run(self.web_hunt_agent.run(request)))
                else:
                    outcome.append(asyncio.run(self.web_hunt_agent.run(request)))
            except Exception as exc:
                failures.append(exc)

        worker = threading.Thread(target=run, name="langgraph-web-adapter")
        worker.start()
        worker.join()
        if failures:
            raise RuntimeError("Production WebHuntAgent execution failed") from failures[0]
        if not outcome:
            raise RuntimeError("Production WebHuntAgent returned no result")
        return outcome[0]

    @staticmethod
    def _evidence_payload(result: Any) -> list[dict[str, Any]]:
        facts_by_url: dict[str, list[str]] = {}
        for fact in result.extracted_information:
            facts_by_url.setdefault(fact.source_url, []).append(fact.fact)
        evidence = []
        for source in result.sources:
            evidence.append({
                "source_url": source.url,
                "title": source.title,
                "extracted_facts": facts_by_url.get(source.url, [source.snippet] if source.snippet else []),
                "confidence": 1.0,
                "provenance": {
                    "source": source.domain,
                    "method": "production-web-intelligence",
                },
                "uncertainties": list(result.uncertainties),
            })
        return evidence
