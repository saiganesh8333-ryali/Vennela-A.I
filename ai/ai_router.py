"""AI routing with standalone frozen LLM Router V1 and Conversation Adjuster."""

import logging
from typing import Dict, List, Optional

from llm_router.adapter import VennelaLLMAdapter
from conversation.response_policy import ConversationAdjuster

logger = logging.getLogger(__name__)

_adapter: Optional[VennelaLLMAdapter] = None
_adjuster: Optional[ConversationAdjuster] = None


def get_adapter() -> VennelaLLMAdapter:
    global _adapter
    if _adapter is None:
        _adapter = VennelaLLMAdapter()
    return _adapter


def get_adjuster() -> ConversationAdjuster:
    global _adjuster
    if _adjuster is None:
        _adjuster = ConversationAdjuster()
    return _adjuster


def get_ai_response(messages: List[Dict[str, str]]) -> Dict[str, str]:
    """Route conversation messages through ConversationAdjuster and VennelaLLMAdapter."""
    if not messages:
        return {
            "provider": "error",
            "response": "No messages provided.",
            "error": "empty_messages",
        }

    system_instruction = None
    user_prompt = ""

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "system":
            system_instruction = content
        elif role == "user":
            user_prompt = content

    if not user_prompt and messages:
        user_prompt = messages[-1].get("content", "")

    adjuster = get_adjuster()
    policy = adjuster.adjust(user_prompt, user_system_instruction=system_instruction)

    adapter = get_adapter()
    try:
        result = adapter.route_text(
            user_prompt,
            system_instruction=policy.system_instruction,
            latency_sensitive=policy.latency_sensitive,
            max_tokens=policy.max_tokens,
            task_hint=policy.task_hint,
        )
        return {
            "provider": result.get("provider", "LLMRouter"),
            "model": result.get("model_id", "default"),
            "response": result.get("text", ""),
            "latency_ms": str(int(result.get("latency_ms", 0))),
        }
    except Exception as exc:
        logger.error(f"Router call failed in ai_router: {exc}")
        return {
            "provider": "error",
            "response": "AI temporarily unavailable. Please try again.",
            "error": str(exc),
        }