"""Capability-based Device Router for selecting execution agents."""

from __future__ import annotations

from typing import Sequence

from .agent import AgentPlatform, AgentStatus, BaseExecutionAgent
from .models import ActionType, AgentAction


class DeviceRoutingError(Exception):
    """Raised when an action cannot be routed to any available agent."""


class DeviceRouter:
    """Routes automation actions to appropriate execution agents based on capabilities."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseExecutionAgent] = {}

    def register(self, agent: BaseExecutionAgent) -> None:
        """Register an execution agent."""
        self._agents[agent.agent_id] = agent

    def unregister(self, agent_id: str) -> BaseExecutionAgent | None:
        """Unregister an execution agent by ID."""
        return self._agents.pop(agent_id, None)

    def get_agent(self, agent_id: str) -> BaseExecutionAgent | None:
        """Lookup an agent by ID."""
        return self._agents.get(agent_id)

    def list_agents(
        self,
        platform: AgentPlatform | None = None,
        status: AgentStatus | None = None,
    ) -> list[BaseExecutionAgent]:
        """List registered agents with optional platform and status filters."""
        agents = list(self._agents.values())
        if platform is not None:
            agents = [a for a in agents if a.platform == platform]
        if status is not None:
            agents = [a for a in agents if a.get_status() == status]
        return agents

    def route(
        self,
        action: AgentAction,
        preferred_platform: AgentPlatform | None = None,
    ) -> BaseExecutionAgent:
        """Route an action to the best available agent supporting the required capability.

        Priority order:
        1. Online agent matching preferred_platform AND action capability.
        2. Online agent on any platform matching action capability (if preferred_platform not strictly found).
        """
        if not self._agents:
            raise DeviceRoutingError("No execution agents registered with Device Router")

        # 1. Filter by capability
        capable_agents = [
            a for a in self._agents.values()
            if a.metadata.supports(action.type) and a.metadata.is_available()
        ]

        if not capable_agents:
            # Distinguish between missing capability vs agent offline
            all_capable = [
                a for a in self._agents.values()
                if a.metadata.supports(action.type)
            ]
            if not all_capable:
                raise DeviceRoutingError(
                    f"No registered agent supports capability '{action.type.value}'"
                )
            raise DeviceRoutingError(
                f"All agents capable of '{action.type.value}' are currently unavailable/offline"
            )

        # 2. Filter by preferred platform if requested
        if preferred_platform is not None:
            platform_matches = [
                a for a in capable_agents if a.platform == preferred_platform
            ]
            if platform_matches:
                return platform_matches[0]
            # If preferred platform was specified but not found among capable agents:
            # We fail gracefully with a descriptive error rather than silently routing to the wrong platform
            raise DeviceRoutingError(
                f"No available agent on preferred platform '{preferred_platform.value}' supports '{action.type.value}'"
            )

        # 3. Default selection: return first available capable agent
        return capable_agents[0]
