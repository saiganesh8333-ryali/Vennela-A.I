from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Protocol
from pydantic import BaseModel, Field
from .errors import BrainFailure


class Provenance(BaseModel):
    source: str
    method: str
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WebEvidence(BaseModel):
    source_url: str
    title: str
    extracted_facts: List[str]
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: Provenance
    uncertainties: List[str] = Field(default_factory=list)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


VerificationStatus = Literal["success", "failed", "partial", "unknown"]


class VerificationResult(BaseModel):
    status: VerificationStatus
    action: Optional[str] = None
    message: str
    evidence: List[str] = Field(default_factory=list)


class StateUpdate(BaseModel):
    values: Dict[str, Any] = Field(default_factory=dict)
    failures: List[BrainFailure] = Field(default_factory=list)
    events: List[Dict[str, Any]] = Field(default_factory=list)


class Node(Protocol):
    name: str
    def run(self, state: "VennelaState") -> StateUpdate: ...
