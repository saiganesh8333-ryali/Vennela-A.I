"""Provider-agnostic data structures and contracts for LLM Router."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
from typing import Any, Mapping, Sequence


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True)
class Message:
    role: Role | str
    content: str

    def to_dict(self) -> dict[str, str]:
        role_str = self.role.value if isinstance(self.role, Role) else str(self.role)
        return {"role": role_str, "content": self.content}


class TaskType(str, Enum):
    CONVERSATION = "CONVERSATION"
    TINY_TASK = "TINY_TASK"
    GENERAL_REASONING = "GENERAL_REASONING"
    DEEP_REASONING = "DEEP_REASONING"
    CODING = "CODING"
    LONG_CONTEXT = "LONG_CONTEXT"
    MULTIMODAL = "MULTIMODAL"
    EMERGENCY = "EMERGENCY"
    UNKNOWN = "UNKNOWN"


class FailureKind(str, Enum):
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    NETWORK = "network"
    INVALID_REQUEST = "invalid_request"
    CONTEXT_LIMIT = "context_limit"
    MODEL_UNAVAILABLE = "model_unavailable"
    SERVER = "server"
    NO_API_KEY = "no_api_key"
    CIRCUIT_OPEN = "circuit_open"
    MALFORMED_RESPONSE = "malformed_response"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Failure:
    kind: FailureKind
    message: str
    retryable: bool = False
    provider: str | None = None
    model_id: str | None = None
    status_code: int | None = None

    def safe_dict(self) -> dict[str, Any]:
        """Dictionary representation guaranteed to contain no credentials or raw request text."""
        return {
            "kind": self.kind.value,
            "message": self.message,
            "retryable": self.retryable,
            "provider": self.provider,
            "model_id": self.model_id,
            "status_code": self.status_code,
        }


class RoutingError(RuntimeError):
    """Exception raised for classified routing and provider failures."""

    def __init__(self, failure: Failure):
        super().__init__(failure.message)
        self.failure = failure


@dataclass(frozen=True)
class Attempt:
    model_id: str
    provider: str
    latency_ms: float = 0.0
    failure: Failure | None = None

    @property
    def succeeded(self) -> bool:
        return self.failure is None


@dataclass
class LLMRequest:
    prompt: str | None = None
    messages: Sequence[Message | Mapping[str, str]] | None = None
    task_type: TaskType | str | None = None
    requirements: frozenset[str] = field(default_factory=frozenset)
    latency_sensitive: bool = False
    streaming: bool = False
    structured_output: bool = False
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def normalized_messages(self) -> list[dict[str, str]]:
        if self.messages is not None:
            result = []
            for m in self.messages:
                if isinstance(m, Message):
                    result.append(m.to_dict())
                elif isinstance(m, Mapping):
                    result.append({"role": str(m.get("role", "user")), "content": str(m.get("content", ""))})
            return result
        if self.prompt is not None:
            return [{"role": "user", "content": self.prompt}]
        return []

    def get_prompt_text(self) -> str:
        if self.prompt is not None:
            return self.prompt
        if self.messages:
            return " ".join(
                str(m.content if isinstance(m, Message) else m.get("content", ""))
                for m in self.messages
            )
        return ""


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model_id: str
    provider: str
    latency_ms: float
    ttft_ms: float | None = None
    usage: Mapping[str, int] = field(default_factory=dict)
    attempts: tuple[Attempt, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    raw: Mapping[str, Any] | None = None

    @property
    def fallback_used(self) -> bool:
        return len(self.attempts) > 1

    def json(self) -> dict[str, Any]:
        """Parsed JSON helper if structured_output was requested."""
        return json.loads(self.text)


@dataclass(frozen=True)
class LLMStreamChunk:
    delta: str
    model_id: str
    provider: str
    index: int
    is_final: bool = False
    ttft_ms: float | None = None
    usage: Mapping[str, int] | None = None
