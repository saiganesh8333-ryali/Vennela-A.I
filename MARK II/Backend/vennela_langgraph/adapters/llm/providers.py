import json
from typing import Protocol
from vennela_langgraph.core.intent import resolve_intent
from vennela_langgraph.core.plan import create_execution_plan
from .contracts import LLMRequest, LLMResponse, LLMMetadata


class LLMProvider(Protocol):
    provider: str
    model: str
    def generate(self, request: LLMRequest) -> LLMResponse: ...


class DeterministicMockProvider:
    provider = "lab-mock"
    model = "deterministic-llm-v1"

    def __init__(self, overrides: dict[str, str] | None = None):
        self.overrides = overrides or {}

    def generate(self, request: LLMRequest) -> LLMResponse:
        if request.task in self.overrides:
            content = self.overrides[request.task]
        elif request.task == "intent":
            intent = resolve_intent(
                request.payload["user_message"],
                request.payload.get("conversation_context", []),
                request.payload.get("memory_context", []),
            )
            content = intent.model_dump_json()
        elif request.task == "planner":
            intent = request.payload["canonical_intent"]
            from vennela_langgraph.core.intent import CanonicalIntent
            content = create_execution_plan(CanonicalIntent.model_validate(intent)).model_dump_json()
        elif request.task == "reasoning":
            content = json.dumps({
                "response_text": request.payload.get("fallback_response", "No response available."),
                "confidence": 0.85,
                "evidence_refs": request.payload.get("evidence_refs", []),
                "unresolved_items": request.payload.get("unresolved_items", []),
                "follow_up_required": bool(request.payload.get("unresolved_items")),
            })
        else:
            content = "{}"
        return LLMResponse(content=content, metadata=LLMMetadata(
            provider=self.provider, model=self.model, request_id=request.request_id,
            latency_ms=0.0, success=True, retry_count=request.retry_count,
        ))
