"""Agent Gateway coordinating device router, execution dispatch, and verification."""

from __future__ import annotations

import time
import uuid
from typing import Any

from .agent import AgentPlatform, AgentStatus, BaseExecutionAgent, ExecutionResult
from .device_router import DeviceRouter, DeviceRoutingError
from .models import AgentAction
from .validators import ActionValidationError, validate_action
from .verifier import ExecutionVerifier, VerificationResult


class AgentGateway:
    """Central gateway for registering agents, routing actions, and dispatching execution."""

    def __init__(
        self,
        router: DeviceRouter | None = None,
        verifier: ExecutionVerifier | None = None,
    ) -> None:
        self.router = router or DeviceRouter()
        self.verifier = verifier or ExecutionVerifier()

    def register_agent(self, agent: BaseExecutionAgent) -> None:
        """Register an execution agent."""
        self.router.register(agent)

    def unregister_agent(self, agent_id: str) -> BaseExecutionAgent | None:
        """Unregister an execution agent."""
        return self.router.unregister(agent_id)

    def get_agent(self, agent_id: str) -> BaseExecutionAgent | None:
        """Retrieve a registered agent by ID."""
        return self.router.get_agent(agent_id)

    def list_agents(
        self,
        platform: AgentPlatform | None = None,
        status: AgentStatus | None = None,
    ) -> list[BaseExecutionAgent]:
        """List registered agents with optional filters."""
        return self.router.list_agents(platform=platform, status=status)

    def dispatch(
        self,
        action: AgentAction,
        *,
        preferred_platform: AgentPlatform | None = None,
        task_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> tuple[ExecutionResult, VerificationResult]:
        """Validate, route, dispatch action to agent, and verify execution result."""
        # 1. Validate action contract
        validated = validate_action(action)

        tid = task_id or f"task-{uuid.uuid4().hex[:8]}"

        # 2. Route to appropriate agent
        try:
            agent = self.router.route(validated, preferred_platform=preferred_platform)
        except DeviceRoutingError as exc:
            result = ExecutionResult(
                task_id=tid,
                success=False,
                error=f"Routing failed: {exc}",
            )
            verification = self.verifier.verify(validated, result)
            return result, verification

        # 3. Dispatch execution with timing
        start_time = time.perf_counter()
        try:
            raw_result = agent.execute(validated, tid, context=context)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            result = ExecutionResult(
                task_id=raw_result.task_id,
                success=raw_result.success,
                output=raw_result.output,
                error=raw_result.error,
                latency_ms=round(raw_result.latency_ms or elapsed_ms, 2),
                agent_id=agent.agent_id,
                device_id=agent.device_id,
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            result = ExecutionResult(
                task_id=tid,
                success=False,
                error=f"Agent execution error: {exc}",
                latency_ms=round(elapsed_ms, 2),
                agent_id=agent.agent_id,
                device_id=agent.device_id,
            )

        # 4. Verify result
        verification = self.verifier.verify(validated, result)
        return result, verification

    def cancel(self, agent_id: str, task_id: str) -> bool:
        """Cancel a running task on a specific agent."""
        agent = self.router.get_agent(agent_id)
        if agent is None:
            return False
        return agent.cancel(task_id)
