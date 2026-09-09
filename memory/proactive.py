"""Deterministic Proactive Recall Engine with Anti-Spam Policy (Level 6)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Dict, List, Optional, Tuple

from .api import MemoryAPI
from .intelligent import IntelligentMemory
from .models import AuthContext, MemoryDomain, ProactiveMemory, ProactiveRecallResult, ScoredMemory
from .security import MemoryAuthorizationError, authorize


@dataclass(frozen=True)
class ProactiveRecallPolicy:
    """Configurable thresholds for proactive recall anti-spam control."""

    min_score: float = 0.50
    min_semantic_similarity: float = 0.20
    max_recall: int = 2
    cooldown_seconds: float = 300.0


class ProactiveRecallEngine:
    """Evaluates context and determines whether proactive memory surfacing is justified."""

    def __init__(
        self,
        api: MemoryAPI,
        intelligent: IntelligentMemory,
        policy: Optional[ProactiveRecallPolicy] = None,
    ):
        self.api = api
        self.intelligent = intelligent
        self.policy = policy or ProactiveRecallPolicy()
        # Cooldown cache: (user_id, memory_id) -> timestamp
        self._surfaced_history: dict[tuple[str, str], datetime] = {}

    def _is_in_cooldown(self, user_id: str, memory_id: str, now: datetime) -> bool:
        key = (user_id, memory_id)
        if key not in self._surfaced_history:
            return False
        last_surfaced = self._surfaced_history[key]
        delta = (now - last_surfaced).total_seconds()
        return delta < self.policy.cooldown_seconds

    def _mark_surfaced(self, user_id: str, memory_id: str, now: datetime) -> None:
        self._surfaced_history[(user_id, memory_id)] = now

    def clear_cooldown(self, user_id: Optional[str] = None) -> None:
        if user_id:
            keys_to_del = [k for k in self._surfaced_history if k[0] == user_id]
            for k in keys_to_del:
                del self._surfaced_history[k]
        else:
            self._surfaced_history.clear()

    @staticmethod
    def _text(record) -> str:
        if isinstance(record.content, dict):
            return str(record.content.get("text", record.content.get("content", ""))).strip()
        return str(record.content).strip()

    def _is_already_in_context(self, memory_text: str, context_text: str) -> bool:
        if not memory_text or not context_text:
            return False
        clean_mem = memory_text.strip().lower()
        clean_ctx = context_text.strip().lower()

        # If substantial memory text is an exact substring of context
        if len(clean_mem) >= 25 and clean_mem in clean_ctx:
            return True

        mem_tokens = set(re.findall(r"[a-z0-9]+", clean_mem))
        ctx_tokens = set(re.findall(r"[a-z0-9]+", clean_ctx))
        if len(mem_tokens) >= 5:
            overlap = len(mem_tokens & ctx_tokens) / len(mem_tokens)
            if overlap >= 0.80:
                return True
        return False

    def _generate_reason(self, scored: ScoredMemory) -> str:
        record = scored.record
        cat = record.category.value
        if scored.relational_boost > 0.0:
            return f"Connected {cat.lower()} with high relevance to active discussion (score: {scored.score:.2f})"
        if scored.importance >= 0.70:
            return f"High-importance {cat.lower()} directly applicable to current topic (score: {scored.score:.2f})"
        if scored.session_boost > 0.0:
            return f"Active session {cat.lower()} relevant to context (score: {scored.score:.2f})"
        return f"Proactively relevant {cat.lower()} matching context semantics (score: {scored.score:.2f})"

    def recall(
        self,
        context: AuthContext,
        current_context: str,
        domain: str = MemoryDomain.BOSS_PERSONAL.value,
        session_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> ProactiveRecallResult:
        """Deterministically decide which memories to surface proactively."""
        timestamp = now or datetime.now(timezone.utc)
        if not current_context or not isinstance(current_context, str) or not current_context.strip():
            return ProactiveRecallResult([], 0, "", timestamp)

        clean_context = current_context.strip()

        # Step 1: Query L5 Intelligent retrieval with generous candidate pool
        candidates = self.intelligent.retrieve_semantic(
            context,
            query=clean_context,
            domain=domain,
            session_id=session_id,
            limit=20,
            now=timestamp,
        )

        recalled: list[ProactiveMemory] = []
        suppressed_count = 0

        for scored in candidates:
            # Policy 1: Score threshold
            if scored.score < self.policy.min_score or scored.semantic_similarity < self.policy.min_semantic_similarity:
                suppressed_count += 1
                continue

            memory_id = scored.record.memory_id
            mem_text = self._text(scored.record)

            # Policy 2: Anti-spam cooldown
            if self._is_in_cooldown(context.user_id, memory_id, timestamp):
                suppressed_count += 1
                continue

            # Policy 3: In-context duplication suppression
            if self._is_already_in_context(mem_text, clean_context):
                suppressed_count += 1
                continue

            # Surfacing approved!
            reason = self._generate_reason(scored)
            proactive_mem = ProactiveMemory(
                record=scored.record,
                score=scored.score,
                reason=reason,
                confidence=scored.semantic_similarity,
                surfaced_at=timestamp,
            )
            recalled.append(proactive_mem)
            self._mark_surfaced(context.user_id, memory_id, timestamp)

            if len(recalled) >= self.policy.max_recall:
                break

        return ProactiveRecallResult(
            recalled_memories=recalled,
            suppressed_count=suppressed_count,
            context_evaluated=clean_context,
            timestamp=timestamp,
        )
