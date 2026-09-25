from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field
from .contracts import StateUpdate, WebEvidence, VerificationResult
from .errors import BrainFailure
from .intent import CanonicalIntent
from .plan import ExecutionPlan


class Message(BaseModel):
    role: str
    content: str


class VennelaState(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str = "lab-session"
    user_id: Optional[str] = None
    messages: List[Message] = Field(default_factory=list)
    original_request: str
    canonical_intent: Optional[CanonicalIntent] = None
    plan_id: Optional[str] = None
    plan_details: Optional[ExecutionPlan] = None
    plan_steps: List[dict] = Field(default_factory=list)
    dependencies: Dict[str, List[str]] = Field(default_factory=dict)
    parallel_groups: Dict[str, List[str]] = Field(default_factory=dict)
    memory_context: List[str] = Field(default_factory=list)
    selected_agents: List[str] = Field(default_factory=list)
    execution_plan: List[str] = Field(default_factory=list)
    tool_results: Dict[str, Any] = Field(default_factory=dict)
    web_evidence: List[WebEvidence] = Field(default_factory=list)
    reasoning_context: List[str] = Field(default_factory=list)
    verification_results: List[VerificationResult] = Field(default_factory=list)
    errors: List[BrainFailure] = Field(default_factory=list)
    attempts: Dict[str, int] = Field(default_factory=dict)
    status: str = "created"
    response: Optional[str] = None
    response_metadata: Dict[str, Any] = Field(default_factory=dict)
    fusion_context: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def apply(self, update: "StateUpdate") -> "VennelaState":
        data = self.model_dump()
        for key, value in update.values.items():
            if key not in data:
                raise ValueError(f"Unknown state field: {key}")
            if key in {"errors", "messages", "web_evidence", "verification_results", "reasoning_context"}:
                data[key] = data[key] + value
            else:
                data[key] = value
        data["errors"] = data["errors"] + update.failures
        return VennelaState.model_validate(data)
