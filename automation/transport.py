"""Real-time authenticated agent transport layer (WebSocket connection, protocol, and lifecycle)."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from typing import Any

from .agent import (
    AgentMetadata,
    AgentPlatform,
    AgentStatus,
    BaseExecutionAgent,
    ExecutionResult,
)
from .gateway import AgentGateway
from .models import ActionType, AgentAction

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = "1.0"
DEFAULT_DEV_TOKEN = "vennela-agent-secret-dev"


class TransportError(Exception):
    """Base exception for agent transport errors."""


class AuthenticationError(TransportError):
    """Raised when an agent fails authentication."""


class RegistrationError(TransportError):
    """Raised when an agent registration payload is invalid."""


class AgentConnection:
    """Manages an active WebSocket connection and correlates execution request/response pairs."""

    def __init__(
        self,
        websocket: Any,
        agent_id: str,
        device_id: str,
        platform: AgentPlatform,
        capabilities: frozenset[ActionType],
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self.websocket = websocket
        self.agent_id = agent_id
        self.device_id = device_id
        self.platform = platform
        self.capabilities = capabilities
        self.loop = loop or asyncio.get_event_loop()
        self.is_active = True
        self.last_seen = time.time()
        self._pending_requests: dict[str, asyncio.Future[ExecutionResult]] = {}
        self._lock = threading.Lock()

    def update_last_seen(self) -> None:
        self.last_seen = time.time()

    async def send_execute(
        self,
        task_id: str,
        action: AgentAction,
        timeout_seconds: float = 30.0,
    ) -> ExecutionResult:
        """Send an execution request envelope to the connected agent and await the correlated result."""
        if not self.is_active:
            return ExecutionResult(
                task_id=task_id,
                success=False,
                error=f"Agent '{self.agent_id}' is disconnected",
                agent_id=self.agent_id,
                device_id=self.device_id,
            )

        fut: asyncio.Future[ExecutionResult] = self.loop.create_future()
        with self._lock:
            self._pending_requests[task_id] = fut

        envelope = {
            "type": "execute",
            "version": PROTOCOL_VERSION,
            "request_id": task_id,
            "action": action.to_dict()["agent_action"],
        }

        try:
            await self.websocket.send_json(envelope)
            result = await asyncio.wait_for(fut, timeout=timeout_seconds)
            return result
        except asyncio.TimeoutError:
            with self._lock:
                self._pending_requests.pop(task_id, None)
            return ExecutionResult(
                task_id=task_id,
                success=False,
                error=f"Execution timed out after {timeout_seconds}s waiting for agent '{self.agent_id}'",
                agent_id=self.agent_id,
                device_id=self.device_id,
            )
        except Exception as exc:
            with self._lock:
                self._pending_requests.pop(task_id, None)
            return ExecutionResult(
                task_id=task_id,
                success=False,
                error=f"Transport send error: {exc}",
                agent_id=self.agent_id,
                device_id=self.device_id,
            )

    async def send_cancel(self, task_id: str) -> bool:
        """Send a cancellation notice to the connected agent."""
        if not self.is_active:
            return False

        envelope = {
            "type": "cancel",
            "version": PROTOCOL_VERSION,
            "request_id": task_id,
        }

        try:
            await self.websocket.send_json(envelope)
            return True
        except Exception as exc:
            logger.warning(f"Failed to send cancellation to agent '{self.agent_id}': {exc}")
            return False

    def handle_result(self, payload: dict[str, Any]) -> bool:
        """Correlate an incoming result envelope with its pending execution future."""
        self.update_last_seen()
        request_id = payload.get("request_id")
        if not request_id:
            logger.warning(f"Received result payload without request_id from '{self.agent_id}'")
            return False

        with self._lock:
            fut = self._pending_requests.pop(request_id, None)

        if fut is None or fut.done():
            logger.warning(f"Received result for unknown or already completed request_id '{request_id}'")
            return False

        status = payload.get("status", "failed")
        raw_result = payload.get("result")
        output = raw_result if isinstance(raw_result, dict) else {}
        error = payload.get("error")
        if isinstance(error, dict):
            error = str(error.get("message") or error)

        success = status == "success"
        res = ExecutionResult(
            task_id=request_id,
            success=success,
            output=output,
            error=error if not success else None,
            agent_id=self.agent_id,
            device_id=self.device_id,
        )
        fut.set_result(res)
        return True

    def close(self, reason: str = "Connection closed") -> None:
        """Mark connection inactive and fail any outstanding pending requests."""
        self.is_active = False
        with self._lock:
            pending = list(self._pending_requests.items())
            self._pending_requests.clear()

        for tid, fut in pending:
            if not fut.done():
                fut.set_result(
                    ExecutionResult(
                        task_id=tid,
                        success=False,
                        error=f"Agent disconnected: {reason}",
                        agent_id=self.agent_id,
                        device_id=self.device_id,
                    )
                )


class WebSocketExecutionAgent(BaseExecutionAgent):
    """Adapter exposing an active WebSocket agent as a BaseExecutionAgent for DeviceRouter."""

    def __init__(self, metadata: AgentMetadata, connection: AgentConnection) -> None:
        super().__init__(metadata)
        self.connection = connection

    def execute(self, action: AgentAction, task_id: str, context: dict[str, Any] | None = None) -> ExecutionResult:
        if not self.connection.is_active:
            return ExecutionResult(
                task_id=task_id,
                success=False,
                error=f"Agent '{self.agent_id}' is offline",
                agent_id=self.agent_id,
                device_id=self.device_id,
            )

        loop = self.connection.loop
        try:
            # If called within the same thread where loop is already running, run directly or via task
            running_loop = None
            try:
                running_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

            if running_loop is loop:
                # We are in the event loop thread: create task and run via nested helper if possible
                coro = self.connection.send_execute(task_id, action)
                # If we're inside a coroutine, we can't synchronously block the loop;
                # Run with run_coroutine_threadsafe from a worker thread
                res: list[ExecutionResult] = []
                exc_holder: list[Exception] = []

                def worker():
                    try:
                        fut = asyncio.run_coroutine_threadsafe(coro, loop)
                        res.append(fut.result(timeout=35.0))
                    except Exception as e:
                        exc_holder.append(e)

                t = threading.Thread(target=worker)
                t.start()
                t.join(timeout=35.0)
                if exc_holder:
                    raise exc_holder[0]
                if res:
                    return res[0]
                return ExecutionResult(task_id=task_id, success=False, error="Execution timed out")
            else:
                fut = asyncio.run_coroutine_threadsafe(
                    self.connection.send_execute(task_id, action), loop
                )
                return fut.result(timeout=35.0)
        except Exception as exc:
            return ExecutionResult(
                task_id=task_id,
                success=False,
                error=f"Dispatch to WebSocket agent failed: {exc}",
                agent_id=self.agent_id,
                device_id=self.device_id,
            )

    def cancel(self, task_id: str) -> bool:
        if not self.connection.is_active:
            return False
        fut = asyncio.run_coroutine_threadsafe(
            self.connection.send_cancel(task_id), self.connection.loop
        )
        try:
            return fut.result(timeout=5.0)
        except Exception:
            return False


class AgentTransportManager:
    """Manages agent WebSocket connections, authentication, and registration with AgentGateway."""

    def __init__(
        self,
        gateway: AgentGateway,
        auth_token: str | None = None,
        heartbeat_timeout_seconds: float = 60.0,
    ) -> None:
        self.gateway = gateway
        self.auth_token = auth_token or os.getenv("VENNELA_AGENT_TOKEN", DEFAULT_DEV_TOKEN).strip()
        self.heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self._connections: dict[str, AgentConnection] = {}
        self._agents: dict[str, WebSocketExecutionAgent] = {}
        self._lock = threading.Lock()

    def validate_token(self, token: str | None) -> bool:
        """Validate agent authentication token."""
        if not self.auth_token:
            return True  # If auth explicitly disabled in config
        if not token or not isinstance(token, str):
            return False
        return token.strip() == self.auth_token

    def register_connection(
        self,
        websocket: Any,
        registration_payload: dict[str, Any],
        loop: asyncio.AbstractEventLoop,
    ) -> tuple[AgentConnection, WebSocketExecutionAgent]:
        """Validate registration handshake and register agent with Gateway and Device Router."""
        agent_id = registration_payload.get("agent_id")
        if not agent_id or not isinstance(agent_id, str) or not agent_id.strip():
            raise RegistrationError("Missing or invalid 'agent_id'")

        agent_id = agent_id.strip()

        # Check authentication token in handshake if provided
        token = registration_payload.get("token")
        if not self.validate_token(token):
            raise AuthenticationError("Invalid or missing authentication token in registration payload")

        device_id = registration_payload.get("device_id") or f"dev-{agent_id}"
        if not isinstance(device_id, str) or not device_id.strip():
            raise RegistrationError("Missing or invalid 'device_id'")

        raw_platform = registration_payload.get("platform", "").lower().strip()
        try:
            platform = AgentPlatform(raw_platform)
        except ValueError:
            raise RegistrationError(f"Invalid platform '{raw_platform}'. Expected 'android' or 'pc'")

        raw_caps = registration_payload.get("capabilities", [])
        if not isinstance(raw_caps, list):
            raise RegistrationError("'capabilities' must be a list of action type strings")

        parsed_caps: set[ActionType] = set()
        for cap in raw_caps:
            try:
                parsed_caps.add(ActionType(cap))
            except ValueError:
                raise RegistrationError(f"Unsupported action capability: '{cap}'")

        capabilities = frozenset(parsed_caps)

        with self._lock:
            # Handle duplicate connection: close existing active connection
            existing_conn = self._connections.get(agent_id)
            if existing_conn is not None:
                logger.info(f"Duplicate agent connection for '{agent_id}': replacing older connection")
                existing_conn.close(reason="Replaced by new connection")

            connection = AgentConnection(
                websocket=websocket,
                agent_id=agent_id,
                device_id=device_id.strip(),
                platform=platform,
                capabilities=capabilities,
                loop=loop,
            )

            metadata = AgentMetadata(
                agent_id=agent_id,
                device_id=device_id.strip(),
                platform=platform,
                status=AgentStatus.ONLINE,
                capabilities=capabilities,
                last_heartbeat=time.time(),
            )

            agent = WebSocketExecutionAgent(metadata, connection)
            self._connections[agent_id] = connection
            self._agents[agent_id] = agent
            self.gateway.register_agent(agent)

        return connection, agent

    def unregister_connection(self, agent_id: str, reason: str = "Disconnected") -> None:
        """Unregister an agent on disconnect, mark OFFLINE, and clean up active routing."""
        with self._lock:
            conn = self._connections.pop(agent_id, None)
            agent = self._agents.get(agent_id)
            if conn is not None:
                conn.close(reason)
            if agent is not None:
                agent.set_status(AgentStatus.OFFLINE)
                # Unregister from active router to prevent routing to offline agent
                self.gateway.unregister_agent(agent_id)

    def get_connection(self, agent_id: str) -> AgentConnection | None:
        with self._lock:
            return self._connections.get(agent_id)

    def get_agent(self, agent_id: str) -> WebSocketExecutionAgent | None:
        with self._lock:
            return self._agents.get(agent_id)

    def is_agent_online(self, agent_id: str) -> bool:
        agent = self.get_agent(agent_id)
        return agent is not None and agent.get_status() == AgentStatus.ONLINE
