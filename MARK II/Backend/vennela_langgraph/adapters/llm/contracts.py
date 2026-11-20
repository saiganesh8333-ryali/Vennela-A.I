from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LLMRequest(BaseModel):
    task: str
    payload: Dict[str, Any]
    request_id: str
    retry_count: int = 0


class LLMUsage(BaseModel):
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None

    @property
    def total_tokens(self) -> Optional[int]:
        if self.input_tokens is None or self.output_tokens is None:
            return None
        return self.input_tokens + self.output_tokens


class LLMMetadata(BaseModel):
    provider: str
    model: str
    request_id: str
    latency_ms: float
    success: bool
    failure_category: Optional[str] = None
    retry_count: int = 0


class LLMResponse(BaseModel):
    content: str
    metadata: LLMMetadata
    usage: Optional[LLMUsage] = None


class ResponseProposal(BaseModel):
    response_text: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_refs: List[str] = Field(default_factory=list)
    unresolved_items: List[str] = Field(default_factory=list)
    follow_up_required: bool = False
