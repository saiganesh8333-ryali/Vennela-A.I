import json
from vennela_langgraph.core.errors import BrainFailure, FailureCategory
from vennela_langgraph.core.intent import CanonicalIntent
from .contracts import LLMRequest


class LLMIntentResolver:
    def __init__(self, router, max_retries: int = 1):
        self.router, self.max_retries = router, max_retries

    def resolve(self, user_message: str, request_id: str,
                conversation_context=None, memory_context=None) -> CanonicalIntent:
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.router.generate(LLMRequest(
                    task="intent", request_id=request_id, retry_count=attempt,
                    payload={
                        "user_message": user_message,
                        "conversation_context": conversation_context or [],
                        "memory_context": memory_context or [],
                    },
                ))
                raw = response.content.strip()
                if raw.startswith("```"):
                    raw = raw.strip("`")
                    raw = raw[raw.find("{"):]
                intent = CanonicalIntent.model_validate(json.loads(raw))
                return intent
            except Exception as exc:
                last_error = exc
                if not getattr(exc, "retryable", True):
                    break
        raise ValueError(f"intent schema validation failed after {self.max_retries + 1} attempts: {last_error}")
