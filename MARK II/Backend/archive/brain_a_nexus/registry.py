"""Discovery registry for orchestrator-facing specialized agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class RegisteredAgent(Protocol):
    agent_id: str
    name: str
    version: str
    description: str
    capabilities: tuple[str, ...] | frozenset[str] | list[str]

    def health_check(self) -> Any:
        ...


class AgentRegistryError(Exception):
    """Base error for invalid registry operations."""


class DuplicateAgentError(AgentRegistryError):
    """Raised when an agent ID is already registered."""


class InvalidAgentError(AgentRegistryError):
    """Raised when an object does not satisfy the registration contract."""


@dataclass(frozen=True)
class AgentDescriptor:
    """Snapshot of agent metadata exposed to discovery clients."""

    agent_id: str
    name: str
    version: str
    description: str
    capabilities: tuple[str, ...]
    health: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "capabilities": list(self.capabilities),
            "health": self.health,
        }


class AgentRegistry:
    """Deterministic agent discovery; it never executes agents."""

    def __init__(self) -> None:
        self._agents: dict[str, RegisteredAgent] = {}
        self._order: list[str] = []

    def register(self, agent: RegisteredAgent) -> None:
        self._validate(agent)
        if agent.agent_id in self._agents:
            raise DuplicateAgentError(f"Agent '{agent.agent_id}' is already registered")
        self._agents[agent.agent_id] = agent
        self._order.append(agent.agent_id)

    def unregister(self, agent_id: str) -> RegisteredAgent | None:
        agent = self._agents.pop(agent_id, None)
        if agent is not None:
            self._order.remove(agent_id)
        return agent

    def get(self, agent_id: str) -> RegisteredAgent | None:
        return self._agents.get(agent_id)

    def require(self, agent_id: str) -> RegisteredAgent:
        agent = self.get(agent_id)
        if agent is None:
            raise AgentRegistryError(f"Unknown agent '{agent_id}'")
        return agent

    def exists(self, agent_id: str) -> bool:
        return agent_id in self._agents

    def list_agents(self) -> list[RegisteredAgent]:
        return [self._agents[agent_id] for agent_id in self._order]

    def find_by_capability(self, capability: str) -> list[RegisteredAgent]:
        if not isinstance(capability, str) or not capability.strip():
            raise ValueError("capability must be a non-empty string")
        requested = capability.strip()
        return [
            agent
            for agent in self.list_agents()
            if requested in {str(item) for item in agent.capabilities}
        ]

    def describe(self, agent_id: str) -> AgentDescriptor:
        agent = self.require(agent_id)
        health = agent.health_check() if callable(getattr(agent, "health_check", None)) else None
        return AgentDescriptor(
            agent_id=agent.agent_id,
            name=agent.name,
            version=agent.version,
            description=agent.description,
            capabilities=tuple(str(item) for item in agent.capabilities),
            health=health,
        )

    def metadata(self) -> list[AgentDescriptor]:
        return [self.describe(agent_id) for agent_id in self._order]

    @staticmethod
    def _validate(agent: RegisteredAgent) -> None:
        required = ("agent_id", "name", "version", "description", "capabilities")
        if any(not hasattr(agent, field) for field in required):
            raise InvalidAgentError(
                "Agent must expose agent_id, name, version, description, and capabilities"
            )
        if not isinstance(agent.agent_id, str) or not agent.agent_id.strip():
            raise InvalidAgentError("agent_id must be a non-empty string")
        if not isinstance(agent.capabilities, (tuple, frozenset, list)):
            raise InvalidAgentError("capabilities must be a sequence")
