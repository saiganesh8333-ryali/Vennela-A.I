"""Vennela AI Automation Layer: Engine, Process Management, Device Routing, Agent Gateway, and Transport."""

from .agent import (
    AgentMetadata,
    AgentPlatform,
    AgentStatus,
    BaseExecutionAgent,
    ExecutionResult,
    MockExecutionAgent,
)
from .api import create_agent_app, create_agent_transport_api
from .device_router import DeviceRouter, DeviceRoutingError
from .engine import AutomationEngine, AutomationResult
from .gateway import AgentGateway
from .models import ActionType, AgentAction
from .pcb import (
    AutomationThread,
    ProcessControlBlock,
    ProcessState,
    TaskStatus,
)
from .process import ProcessManager
from .scheduler import AutomationScheduler
from .transport import (
    AgentConnection,
    AgentTransportManager,
    AuthenticationError,
    RegistrationError,
    TransportError,
    WebSocketExecutionAgent,
)
from .validators import ActionValidationError, parse_action, validate_action
from .verifier import ExecutionVerifier, VerificationResult, VerificationStatus

__all__ = [
    # Core Actions & Engine
    "ActionType",
    "AgentAction",
    "AutomationEngine",
    "AutomationResult",
    "ActionValidationError",
    "validate_action",
    "parse_action",
    # Agent Contracts
    "AgentPlatform",
    "AgentStatus",
    "AgentMetadata",
    "ExecutionResult",
    "BaseExecutionAgent",
    "MockExecutionAgent",
    # Device Routing
    "DeviceRouter",
    "DeviceRoutingError",
    # Gateway
    "AgentGateway",
    # Process & Thread Management (PCB)
    "ProcessState",
    "TaskStatus",
    "AutomationThread",
    "ProcessControlBlock",
    "ProcessManager",
    # Scheduling & Verification
    "AutomationScheduler",
    "ExecutionVerifier",
    "VerificationResult",
    "VerificationStatus",
    # Real-Time Agent Transport (WebSocket)
    "AgentConnection",
    "WebSocketExecutionAgent",
    "AgentTransportManager",
    "TransportError",
    "AuthenticationError",
    "RegistrationError",
    "create_agent_transport_api",
    "create_agent_app",
]
