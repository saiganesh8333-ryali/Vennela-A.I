"""Deterministic Level 2 decisions backed by the canonical Memory API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional
from uuid import uuid4

from .api import MemoryAPI
from .models import AuthContext, MemoryCategory, MemoryDomain, MemoryRecord


@dataclass(frozen=True)
class SmartMemoryDecision:
    """The deterministic result of evaluating one possible memory."""

    action: str
    record: Optional[MemoryRecord]
    importance: float
    duplicate_of: Optional[str] = None
    reason: str = ""


class SmartMemory:
    """Classify, score, deduplicate, and persist canonical memory records."""

    _TRANSIENT_PREFIXES = (
        "hello", "hi", "hey", "thanks", "thank you", "can you", "could you",
        "how do i", "how can i", "what is", "who is", "please explain",
    )

    def __init__(self, api: MemoryAPI):
        self.api = api

    @staticmethod
    def _text(value: Any) -> str:
        if isinstance(value, dict):
            value = value.get("text", value.get("content", ""))
        return value.strip() if isinstance(value, str) else ""

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {token for token in text.lower().split() if token}

    def _category(self, text: str) -> MemoryCategory:
        lowered = text.lower()
        if "my name is" in lowered or "call me" in lowered:
            return MemoryCategory.PROFILE
        if any(marker in lowered for marker in ("i like", "i love", "favorite", "prefer", "i enjoy")):
            return MemoryCategory.PREFERENCE
        if any(marker in lowered for marker in ("my goal", "i want", "goal is", "dream", "aspiration")):
            return MemoryCategory.GOAL
        if any(marker in lowered for marker in ("project", "working on", "building")):
            return MemoryCategory.PROJECT
        if any(marker in lowered for marker in ("i can ", "i know ", "my skill", "experienced in")):
            return MemoryCategory.SKILL
        if any(marker in lowered for marker in ("error", "problem", "failed", "finished", "completed")):
            return MemoryCategory.EVENT
        return MemoryCategory.FACT

    def _is_transient(self, text: str) -> bool:
        lowered = text.lower().strip()
        return lowered.endswith("?") or any(
            lowered == marker or lowered.startswith(marker + " ")
            for marker in self._TRANSIENT_PREFIXES
        )

    @staticmethod
    def _importance(text: str, category: MemoryCategory, explicit: bool) -> float:
        if explicit:
            return 0.90
        if category is MemoryCategory.FACT:
            lowered = text.lower()
            return 0.50 if lowered.startswith(("my ", "i am ", "i live ", "i work ")) else 0.25
        return {
            MemoryCategory.PROFILE: 0.80,
            MemoryCategory.PREFERENCE: 0.70,
            MemoryCategory.GOAL: 0.70,
            MemoryCategory.PROJECT: 0.65,
            MemoryCategory.SKILL: 0.60,
            MemoryCategory.EVENT: 0.45,
        }[category]

    def decide(
        self,
        context: AuthContext,
        content: Any,
        domain: str = MemoryDomain.BOSS_PERSONAL.value,
        session_id: Optional[str] = None,
        existing: Iterable[MemoryRecord] = (),
    ) -> SmartMemoryDecision:
        """Return create, update, or ignore without changing persistence."""
        text = self._text(content)[:5000]
        domain_value = MemoryDomain(domain)
        if not text:
            return SmartMemoryDecision("ignore", None, 0.0, reason="empty")

        lowered = text.lower()
        explicit = "remember" in lowered or "don't forget" in lowered or "do not forget" in lowered
        if self._is_transient(text) and not explicit:
            return SmartMemoryDecision("ignore", None, 0.0, reason="transient")

        category = self._category(text)
        importance = self._importance(text, category, explicit)
        if importance < 0.40:
            return SmartMemoryDecision("ignore", None, importance, reason="low_value")

        candidate_tokens = self._tokens(text)
        for item in existing:
            if item.owner_id != context.user_id or item.domain != domain_value or not item.active:
                continue
            if domain_value is MemoryDomain.SESSION and item.session_id != session_id:
                continue
            existing_text = self._text(item.content)
            if not existing_text:
                continue
            existing_tokens = self._tokens(existing_text)
            similarity = (
                len(candidate_tokens & existing_tokens) / len(candidate_tokens | existing_tokens)
                if candidate_tokens | existing_tokens else 0.0
            )
            if existing_text.lower() == lowered or similarity >= 0.92:
                now = datetime.now(timezone.utc)
                payload = {"text": text, "importance": importance, "classification": category.value}
                return SmartMemoryDecision(
                    "update",
                    MemoryRecord(item.memory_id, item.owner_id, item.domain, category, payload,
                                 item.session_id, item.created_at, now, True),
                    importance,
                    duplicate_of=item.memory_id,
                    reason="duplicate",
                )

        payload = {"text": text, "importance": importance, "classification": category.value}
        record = MemoryRecord.now(str(uuid4()), context.user_id, domain_value, category, payload, session_id)
        return SmartMemoryDecision("create", record, importance)

    def store(
        self,
        context: AuthContext,
        content: Any,
        domain: str = MemoryDomain.BOSS_PERSONAL.value,
        session_id: Optional[str] = None,
        existing: Optional[Iterable[MemoryRecord]] = None,
    ) -> SmartMemoryDecision:
        """Apply a decision through MemoryAPI and no other persistence layer."""
        domain_value = MemoryDomain(domain)
        records = list(existing) if existing is not None else self.api.retrieve(context, domain_value.value, session_id)
        decision = self.decide(context, content, domain_value.value, session_id, records)
        if decision.action == "create" and decision.record is not None:
            record = decision.record
            stored = self.api.create(context, record.content, record.category.value, record.domain.value,
                                     record.session_id, record.memory_id)
            return SmartMemoryDecision("create", stored, decision.importance)
        if decision.action == "update" and decision.record is not None:
            record = decision.record
            stored = self.api.update(context, record.memory_id, record.content, record.category.value)
            return SmartMemoryDecision("update", stored, decision.importance,
                                       decision.duplicate_of, decision.reason)
        return decision
