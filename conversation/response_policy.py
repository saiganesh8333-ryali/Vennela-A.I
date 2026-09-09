"""Deterministic Conversation Adjuster and Response Policy layer for Vennela AI.

Enforces concise, direct conversational responses by default (JARVIS/FRIDAY style),
expanding to detailed explanations only when requested or technically necessary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, Mapping


class DetailLevel(str, Enum):
    CONCISE = "CONCISE"
    DETAILED = "DETAILED"
    ACTION_CONFIRMATION = "ACTION_CONFIRMATION"


CONCISE_SYSTEM_PROMPT = (
    "You are Vennela, a sharp, ultra-capable AI assistant (JARVIS/FRIDAY style). "
    "Respond concisely by default: be direct, clear, and natural. "
    "Avoid conversational filler, introductory fluff, repeating the user's question, "
    "or unprompted summaries. Answer in 1-3 short sentences unless detail is essential."
)

DETAILED_SYSTEM_PROMPT = (
    "You are Vennela, a sharp, ultra-capable AI assistant. "
    "Provide a comprehensive, detailed, step-by-step response with full technical depth "
    "and clear explanations as requested."
)

ACTION_SYSTEM_PROMPT = (
    "You are Vennela, a sharp, ultra-capable AI assistant. "
    "Confirm the action or report the status directly in a single brief, natural phrase "
    "(e.g., 'YouTube is open.', 'Yes, backend is online.')."
)


# Keywords that explicitly request deep/expanded details
EXPAND_KEYWORDS = (
    "explain in detail",
    "in detail",
    "detailed explanation",
    "deep dive",
    "step by step",
    "step-by-step",
    "tutorial",
    "teach me",
    "walk me through",
    "complete explanation",
    "full architecture",
    "comprehensive",
    "thorough",
    "in-depth",
)

# Keywords that explicitly request concise / brief answers
CONCISE_KEYWORDS = (
    "short answer",
    "briefly",
    "quick answer",
    "just tell me",
    "in one sentence",
    "in one word",
    "tldr",
    "tl;dr",
    "concise",
    "summary only",
)

# Action / status triggers
ACTION_STATUS_PATTERNS = (
    r"^(is|are|was|were)\s+.*\s+(online|running|active|healthy|up|down|dead|offline)\??$",
    r"^(open|launch|start|close|turn on|turn off|switch to)\s+.*",
    r"^status\s+of\s+.*",
    r"^check\s+(battery|status|backend|server|network|connection|internet).*",
)


@dataclass(frozen=True)
class PolicyAdjustment:
    detail_level: DetailLevel
    system_instruction: str
    max_tokens: int | None = None
    latency_sensitive: bool = False
    task_hint: str | None = None


class ConversationAdjuster:
    """Lightweight, deterministic policy adjuster governing response style."""

    def __init__(
        self,
        default_max_tokens_concise: int = 150,
        default_max_tokens_detailed: int = 2048,
    ) -> None:
        self.default_max_tokens_concise = default_max_tokens_concise
        self.default_max_tokens_detailed = default_max_tokens_detailed

    def should_expand_detail(self, text: str) -> bool:
        lower = text.lower()
        if any(k in lower for k in EXPAND_KEYWORDS):
            return True
        # Technical complexity check: code review with multiple requirements or multi-step design
        if "design pattern" in lower or "trade-off" in lower or "architecture diagram" in lower:
            return True
        return False

    def should_be_concise(self, text: str) -> bool:
        lower = text.lower()
        return any(k in lower for k in CONCISE_KEYWORDS)

    def is_action_or_status(self, text: str) -> bool:
        lower = text.strip().lower()
        return any(bool(re.match(p, lower)) for p in ACTION_STATUS_PATTERNS)

    def adjust(
        self,
        prompt: str,
        user_system_instruction: str | None = None,
        latency_sensitive: bool = False,
        **kwargs: Any,
    ) -> PolicyAdjustment:
        """Determines the response style policy and returns adjusted request parameters."""
        prompt_clean = prompt.strip()

        # 1. Explicit user detail override
        if self.should_expand_detail(prompt_clean) and not self.should_be_concise(prompt_clean):
            base_instruction = DETAILED_SYSTEM_PROMPT
            if user_system_instruction:
                base_instruction = f"{user_system_instruction}\n{base_instruction}"
            return PolicyAdjustment(
                detail_level=DetailLevel.DETAILED,
                system_instruction=base_instruction,
                max_tokens=kwargs.get("max_tokens", self.default_max_tokens_detailed),
                latency_sensitive=latency_sensitive,
                task_hint="DEEP_REASONING",
            )

        # 2. Action confirmation or status check
        if self.is_action_or_status(prompt_clean):
            base_instruction = ACTION_SYSTEM_PROMPT
            if user_system_instruction:
                base_instruction = f"{user_system_instruction}\n{base_instruction}"
            return PolicyAdjustment(
                detail_level=DetailLevel.ACTION_CONFIRMATION,
                system_instruction=base_instruction,
                max_tokens=kwargs.get("max_tokens", 80),
                latency_sensitive=True,
                task_hint="TINY_TASK",
            )

        # 3. Default behavior: Concise, direct, conversational
        base_instruction = CONCISE_SYSTEM_PROMPT
        if user_system_instruction:
            base_instruction = f"{user_system_instruction}\n{base_instruction}"

        return PolicyAdjustment(
            detail_level=DetailLevel.CONCISE,
            system_instruction=base_instruction,
            max_tokens=kwargs.get("max_tokens", self.default_max_tokens_concise),
            latency_sensitive=latency_sensitive,
            task_hint="CONVERSATION",
        )
