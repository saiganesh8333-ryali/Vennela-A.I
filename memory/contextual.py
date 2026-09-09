"""Deterministic contextual selection over canonical memory records."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Optional

from .api import MemoryAPI
from .models import AuthContext, MemoryDomain, MemoryRecord


class ContextualMemory:
    """Select a bounded, domain-safe set of records for response context."""

    def __init__(self, api: MemoryAPI):
        self.api = api

    @staticmethod
    def _text(content: Any) -> str:
        if isinstance(content, dict):
            content = content.get("text", content.get("content", ""))
        return content.strip() if isinstance(content, str) else ""

    @staticmethod
    def _tokens(value: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", value.lower()))

    @staticmethod
    def _importance(record: MemoryRecord) -> float:
        if isinstance(record.content, dict):
            try:
                return max(0.0, min(1.0, float(record.content.get("importance", 0.0))))
            except (TypeError, ValueError):
                return 0.0
        return 0.0

    @staticmethod
    def _recency(record: MemoryRecord, now: datetime) -> float:
        updated = record.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (now - updated).total_seconds() / 86400)
        return 1.0 / (1.0 + age_days / 30.0)

    def select(
        self,
        context: AuthContext,
        query: str,
        session_id: Optional[str] = None,
        limit: int = 5,
        include_core: bool = False,
        now: Optional[datetime] = None,
    ) -> list[MemoryRecord]:
        """Return relevant records, ordered deterministically and bounded by ``limit``."""
        if limit <= 0:
            return []
        effective_session = session_id or context.session_id
        effective_context = context
        if effective_session != context.session_id:
            effective_context = AuthContext(context.user_id, context.authenticated, context.scopes, effective_session)

        candidates: list[MemoryRecord] = self.api.retrieve(
            effective_context, MemoryDomain.BOSS_PERSONAL.value, limit=100
        )
        if effective_session:
            candidates.extend(self.api.retrieve(
                effective_context, MemoryDomain.SESSION.value, effective_session, limit=100
            ))
        if include_core and "memory:core" in effective_context.scopes:
            candidates.extend(self.api.retrieve(
                effective_context, MemoryDomain.VENNELA_CORE.value, limit=100
            ))

        query_tokens = self._tokens(query)
        timestamp = now or datetime.now(timezone.utc)
        scored = []
        for record in candidates:
            text_tokens = self._tokens(self._text(record.content))
            relevance = (
                len(query_tokens & text_tokens) / len(query_tokens | text_tokens)
                if query_tokens and text_tokens else 0.0
            )
            if query_tokens and relevance == 0.0:
                continue
            score = (
                relevance * 0.50
                + self._importance(record) * 0.25
                + self._recency(record, timestamp) * 0.15
                + (0.10 if record.domain is MemoryDomain.SESSION else 0.0)
            )
            scored.append((score, record))

        scored.sort(key=lambda entry: (
            -entry[0],
            -entry[1].updated_at.timestamp(),
            entry[1].memory_id,
        ))
        return [record for _, record in scored[:limit]]
