"""Deterministic Level 5 Intelligent Memory layer backed by the canonical Memory API."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Callable, Dict, List, Optional, Sequence
from uuid import uuid4

from .api import MemoryAPI
from .embedding_engine import get_embedding
from .models import (
    AuthContext,
    ConflictResult,
    ConsolidationResult,
    MemoryCategory,
    MemoryDomain,
    MemoryRecord,
    ScoredMemory,
)
from .relational import RelationalMemory
from .security import MemoryAuthorizationError, authorize


class IntelligentMemory:
    """Intelligent semantic retrieval, relevance ranking, consolidation, and conflict resolution."""

    _POSITIVE_MARKERS = ("love", "like", "prefer", "enjoy", "favorite", "want", "advocate", "recommend")
    _NEGATIVE_MARKERS = ("hate", "dislike", "detest", "avoid", "don't like", "do not like", "against", "oppose")

    def __init__(
        self,
        api: MemoryAPI,
        relational: Optional[RelationalMemory] = None,
        embedder: Optional[Callable[[str], List[float]]] = None,
    ):
        self.api = api
        self.relational = relational
        self._embedder = embedder or get_embedding

    @staticmethod
    def _text(content: Any) -> str:
        if isinstance(content, dict):
            content = content.get("text", content.get("content", ""))
        return content.strip() if isinstance(content, str) else ""

    @staticmethod
    def _tokens(value: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", value.lower()))

    def _embed(self, text: str) -> list[float]:
        if not text or not isinstance(text, str):
            return [0.0] * 128
        return self._embedder(text)

    @staticmethod
    def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(float(x) * float(y) for x, y in zip(a, b))
        norm_a = sum(float(x) * float(x) for x in a) ** 0.5
        norm_b = sum(float(y) * float(y) for y in b) ** 0.5
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        sim = dot / (norm_a * norm_b + 1e-9)
        return max(0.0, min(1.0, float(sim)))

    @staticmethod
    def _importance(record: MemoryRecord) -> float:
        if isinstance(record.content, dict):
            try:
                val = float(record.content.get("importance", 0.5))
                return max(0.0, min(1.0, val))
            except (TypeError, ValueError):
                return 0.5
        return 0.5

    @staticmethod
    def _recency(record: MemoryRecord, now: datetime) -> float:
        updated = record.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (now - updated).total_seconds() / 86400)
        return 1.0 / (1.0 + age_days / 30.0)

    def rank(
        self,
        context: AuthContext,
        query: str,
        candidates: Sequence[MemoryRecord],
        session_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> list[ScoredMemory]:
        """Rank candidates using semantic similarity, importance, recency, session, and relational links."""
        if not candidates:
            return []

        query_vec = self._embed(query)
        timestamp = now or datetime.now(timezone.utc)
        candidate_ids = {c.memory_id for c in candidates}

        scored: list[ScoredMemory] = []
        for candidate in candidates:
            authorize(context, candidate.domain, candidate.session_id, candidate)
            text = self._text(candidate.content)

            # Get or calculate embedding
            if isinstance(candidate.content, dict) and "embedding" in candidate.content and isinstance(candidate.content["embedding"], list):
                mem_vec = candidate.content["embedding"]
            else:
                mem_vec = self._embed(text)

            sim = self._cosine_similarity(query_vec, mem_vec)
            imp = self._importance(candidate)
            rec = self._recency(candidate, timestamp)

            sess_boost = 0.10 if candidate.domain is MemoryDomain.SESSION or (session_id and candidate.session_id == session_id) else 0.0

            rel_boost = 0.0
            if self.relational is not None:
                try:
                    rels = self.relational.get_relationships(context, memory_id=candidate.memory_id, active_only=True)
                    # Boost if candidate connects to other candidates in the pool
                    connected = [
                        r for r in rels
                        if (r.target_memory_id in candidate_ids and r.target_memory_id != candidate.memory_id)
                        or (r.source_memory_id in candidate_ids and r.source_memory_id != candidate.memory_id)
                    ]
                    rel_boost = min(0.15, len(connected) * 0.05)
                except Exception:
                    rel_boost = 0.0

            # Composite explainable score
            total_score = (sim * 0.45) + (imp * 0.25) + (rec * 0.15) + sess_boost + rel_boost

            scored.append(
                ScoredMemory(
                    record=candidate,
                    score=round(total_score, 6),
                    semantic_similarity=round(sim, 6),
                    importance=round(imp, 4),
                    recency=round(rec, 4),
                    session_boost=round(sess_boost, 4),
                    relational_boost=round(rel_boost, 4),
                )
            )

        return sorted(
            scored,
            key=lambda item: (
                -item.score,
                -item.record.updated_at.timestamp(),
                item.record.memory_id,
            ),
        )

    def retrieve_semantic(
        self,
        context: AuthContext,
        query: str,
        domain: str = MemoryDomain.BOSS_PERSONAL.value,
        session_id: Optional[str] = None,
        limit: int = 5,
        min_similarity: float = 0.0,
        include_core: bool = False,
        now: Optional[datetime] = None,
    ) -> list[ScoredMemory]:
        """Perform authorized semantic retrieval bounded by limit."""
        if limit <= 0:
            return []

        effective_session = session_id or context.session_id
        effective_context = context
        if effective_session != context.session_id:
            effective_context = AuthContext(
                context.user_id, context.authenticated, context.scopes, effective_session
            )

        domain_value = MemoryDomain(domain)
        candidates: list[MemoryRecord] = self.api.retrieve(
            effective_context, domain_value.value, effective_session, limit=100
        )

        if domain_value is not MemoryDomain.SESSION and effective_session:
            candidates.extend(
                self.api.retrieve(
                    effective_context, MemoryDomain.SESSION.value, effective_session, limit=100
                )
            )

        if include_core and "memory:core" in effective_context.scopes:
            candidates.extend(
                self.api.retrieve(effective_context, MemoryDomain.VENNELA_CORE.value, limit=100)
            )

        # Deduplicate candidates while preserving order
        seen_ids = set()
        unique_candidates = []
        for c in candidates:
            if c.memory_id not in seen_ids and c.active:
                seen_ids.add(c.memory_id)
                unique_candidates.append(c)

        ranked = self.rank(effective_context, query, unique_candidates, effective_session, now)

        if min_similarity > 0.0:
            ranked = [s for s in ranked if s.semantic_similarity >= min_similarity]

        return ranked[:limit]

    def consolidate(
        self,
        context: AuthContext,
        domain: str = MemoryDomain.BOSS_PERSONAL.value,
        session_id: Optional[str] = None,
        similarity_threshold: float = 0.88,
        category: Optional[str | MemoryCategory] = None,
    ) -> list[ConsolidationResult]:
        """Detect and safely consolidate redundant memories without data destruction."""
        domain_value = MemoryDomain(domain)
        records = self.api.retrieve(context, domain_value.value, session_id, limit=200)
        if category is not None:
            target_cat = category if isinstance(category, MemoryCategory) else MemoryCategory(category)
            records = [r for r in records if r.category == target_cat]

        # Group by category for domain/type consistency
        by_category: dict[MemoryCategory, list[MemoryRecord]] = {}
        for r in records:
            by_category.setdefault(r.category, []).append(r)

        results: list[ConsolidationResult] = []
        deactivated_ids: set[str] = set()

        for cat, cat_records in by_category.items():
            n = len(cat_records)
            for i in range(n):
                primary = cat_records[i]
                if primary.memory_id in deactivated_ids:
                    continue
                primary_text = self._text(primary.content)
                if not primary_text:
                    continue
                primary_vec = self._embed(primary_text)
                merged_records: list[MemoryRecord] = []

                for j in range(i + 1, n):
                    secondary = cat_records[j]
                    if secondary.memory_id in deactivated_ids:
                        continue
                    secondary_text = self._text(secondary.content)
                    if not secondary_text:
                        continue
                    secondary_vec = self._embed(secondary_text)
                    sim = self._cosine_similarity(primary_vec, secondary_vec)

                    if sim >= similarity_threshold:
                        # Non-destructive consolidation: deactivate secondary
                        self.api.forget(context, secondary.memory_id)
                        deactivated_ids.add(secondary.memory_id)
                        merged_records.append(secondary)

                if merged_records:
                    # Update primary record with reinforcement count and highest importance
                    old_content = primary.content if isinstance(primary.content, dict) else {"text": primary.content}
                    primary_imp = self._importance(primary)
                    max_imp = max([primary_imp] + [self._importance(m) for m in merged_records])
                    current_reinf = int(old_content.get("reinforcement_count", 1))
                    updated_content = dict(old_content)
                    updated_content["importance"] = max_imp
                    updated_content["reinforcement_count"] = current_reinf + len(merged_records)
                    existing_consolidations = list(updated_content.get("consolidated_from", []))
                    existing_consolidations.extend([m.memory_id for m in merged_records])
                    updated_content["consolidated_from"] = existing_consolidations
                    updated_content["consolidated_at"] = datetime.now(timezone.utc).isoformat()

                    updated_primary = self.api.update(
                        context,
                        primary.memory_id,
                        updated_content,
                        category=primary.category.value,
                    )
                    results.append(
                        ConsolidationResult(
                            primary_record=updated_primary,
                            consolidated_records=merged_records,
                            reason=f"Consolidated {len(merged_records)} redundant record(s) with similarity >= {similarity_threshold}",
                            action="merge_and_deactivate_redundant",
                        )
                    )

        return results

    def _extract_polarity(self, text: str) -> Optional[str]:
        lowered = text.lower()
        has_pos = any(m in lowered for m in self._POSITIVE_MARKERS)
        has_neg = any(m in lowered for m in self._NEGATIVE_MARKERS)
        if has_pos and not has_neg:
            return "positive"
        if has_neg and not has_pos:
            return "negative"
        return None

    def resolve_conflicts(
        self,
        context: AuthContext,
        domain: str = MemoryDomain.BOSS_PERSONAL.value,
        session_id: Optional[str] = None,
        category: Optional[str | MemoryCategory] = None,
    ) -> list[ConflictResult]:
        """Detect contradictory memories and apply deterministic conflict resolution policy."""
        domain_value = MemoryDomain(domain)
        records = self.api.retrieve(context, domain_value.value, session_id, limit=200)
        if category is not None:
            target_cat = category if isinstance(category, MemoryCategory) else MemoryCategory(category)
            records = [r for r in records if r.category == target_cat]

        by_category: dict[MemoryCategory, list[MemoryRecord]] = {}
        for r in records:
            by_category.setdefault(r.category, []).append(r)

        results: list[ConflictResult] = []
        resolved_ids: set[str] = set()

        for cat, cat_records in by_category.items():
            n = len(cat_records)
            for i in range(n):
                r1 = cat_records[i]
                if r1.memory_id in resolved_ids:
                    continue
                t1 = self._text(r1.content)
                tokens1 = self._tokens(t1)
                polarity1 = self._extract_polarity(t1)

                for j in range(i + 1, n):
                    r2 = cat_records[j]
                    if r2.memory_id in resolved_ids:
                        continue
                    t2 = self._text(r2.content)
                    tokens2 = self._tokens(t2)
                    polarity2 = self._extract_polarity(t2)

                    # Check for subject overlap (e.g. sharing topic words like 'python', 'coffee')
                    shared_tokens = (tokens1 & tokens2) - {"i", "my", "a", "the", "to", "is", "in", "it", "for", "of"}

                    is_conflict = False
                    reason = ""

                    # Polarity reversal on shared subject
                    if shared_tokens and polarity1 and polarity2 and polarity1 != polarity2:
                        is_conflict = True
                        reason = f"Opposing polarities ({polarity1} vs {polarity2}) on shared topic: {shared_tokens}"

                    # Mutually exclusive attribute claims (e.g. 'favorite language is python' vs 'favorite language is rust')
                    if not is_conflict:
                        attr_match1 = re.search(r"(favorite \w+|prefer \w+|choice is \w+)", t1.lower())
                        attr_match2 = re.search(r"(favorite \w+|prefer \w+|choice is \w+)", t2.lower())
                        if attr_match1 and attr_match2 and attr_match1.group(1) == attr_match2.group(1) and t1.lower() != t2.lower():
                            is_conflict = True
                            reason = f"Mutually exclusive attribute values for: {attr_match1.group(1)}"

                    if is_conflict:
                        # Resolution policy:
                        # If one is significantly newer and equal or higher importance: SUPERSEDE
                        time1 = r1.updated_at.timestamp()
                        time2 = r2.updated_at.timestamp()
                        imp1 = self._importance(r1)
                        imp2 = self._importance(r2)

                        # Check if one clearly supersedes the other
                        if abs(time1 - time2) >= 1.0 or imp1 != imp2:
                            newer, older = (r2, r1) if time2 >= time1 else (r1, r2)
                            newer_imp, older_imp = (imp2, imp1) if time2 >= time1 else (imp1, imp2)

                            if newer_imp >= older_imp - 0.10:
                                # Supersede older record
                                self.api.forget(context, older.memory_id)
                                resolved_ids.add(older.memory_id)

                                old_newer_content = newer.content if isinstance(newer.content, dict) else {"text": newer.content}
                                updated_newer_content = dict(old_newer_content)
                                updated_newer_content["supersedes"] = older.memory_id
                                updated_newer_content["superseded_at"] = datetime.now(timezone.utc).isoformat()
                                updated_newer = self.api.update(
                                    context,
                                    newer.memory_id,
                                    updated_newer_content,
                                    category=newer.category.value,
                                )

                                results.append(
                                    ConflictResult(
                                        status="superseded",
                                        winning_record=updated_newer,
                                        conflicting_records=[older],
                                        reason=f"Newer record supersedes older conflicting record ({reason})",
                                    )
                                )
                                continue

                        # Ambiguous: preserve both, tag both with conflict metadata
                        r1_content = dict(r1.content) if isinstance(r1.content, dict) else {"text": r1.content}
                        r2_content = dict(r2.content) if isinstance(r2.content, dict) else {"text": r2.content}
                        r1_content["conflict_status"] = "ambiguous"
                        r1_content["conflict_with"] = r2.memory_id
                        r2_content["conflict_status"] = "ambiguous"
                        r2_content["conflict_with"] = r1.memory_id

                        up1 = self.api.update(context, r1.memory_id, r1_content, r1.category.value)
                        up2 = self.api.update(context, r2.memory_id, r2_content, r2.category.value)
                        resolved_ids.add(r1.memory_id)
                        resolved_ids.add(r2.memory_id)

                        results.append(
                            ConflictResult(
                                status="ambiguous",
                                winning_record=None,
                                conflicting_records=[up1, up2],
                                reason=f"Ambiguous contradiction: preserved both records active ({reason})",
                            )
                        )

        return results
