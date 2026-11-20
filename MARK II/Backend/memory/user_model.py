"""Deterministic Derived User Model Projection (Level 6)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .api import MemoryAPI
from .models import (
    AuthContext,
    MemoryCategory,
    MemoryDomain,
    MemoryRecord,
    MemoryRelationship,
    UserModel,
)
from .relational import RelationalMemory
from .security import MemoryAuthorizationError, authorize


class UserModelEngine:
    """Projects a coherent, derived user model from canonical memories and relationships."""

    def __init__(self, api: MemoryAPI, relational: Optional[RelationalMemory] = None):
        self.api = api
        self.relational = relational

    @staticmethod
    def _text(record: MemoryRecord) -> str:
        if isinstance(record.content, dict):
            return str(record.content.get("text", record.content.get("content", ""))).strip()
        return str(record.content).strip()

    @staticmethod
    def _importance(record: MemoryRecord) -> float:
        if isinstance(record.content, dict):
            try:
                return float(record.content.get("importance", 0.5))
            except (TypeError, ValueError):
                return 0.5
        return 0.5

    def build_user_model(
        self,
        context: AuthContext,
        domain: str = MemoryDomain.BOSS_PERSONAL.value,
        include_core: bool = False,
        session_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> UserModel:
        """Construct the derived user model deterministically from authorized active memories."""
        timestamp = now or datetime.now(timezone.utc)
        effective_session = session_id or context.session_id

        # Query active records for this owner
        domain_val = MemoryDomain(domain)
        candidates = self.api.retrieve(context, domain_val.value, effective_session, limit=200)

        if include_core and "memory:core" in context.scopes:
            candidates.extend(self.api.retrieve(context, MemoryDomain.VENNELA_CORE.value, limit=100))

        # Filter strictly active records and ensure authorization
        active_records: list[MemoryRecord] = []
        for r in candidates:
            if not r.active:
                continue
            # Exclude records tagged as superseded or obsolete
            if isinstance(r.content, dict):
                if r.content.get("lifecycle_state") in ("SUPERSEDED", "OBSOLETE", "INACTIVE"):
                    continue
                if r.content.get("evolution_state") == "historical":
                    continue
            authorize(context, r.domain, r.session_id, r)
            active_records.append(r)

        # Categorize
        preferences = sorted(
            [r for r in active_records if r.category is MemoryCategory.PREFERENCE],
            key=lambda item: (-self._importance(item), -item.updated_at.timestamp(), item.memory_id),
        )
        goals = sorted(
            [r for r in active_records if r.category is MemoryCategory.GOAL],
            key=lambda item: (-self._importance(item), -item.updated_at.timestamp(), item.memory_id),
        )
        projects = sorted(
            [r for r in active_records if r.category is MemoryCategory.PROJECT],
            key=lambda item: (-self._importance(item), -item.updated_at.timestamp(), item.memory_id),
        )
        skills = sorted(
            [r for r in active_records if r.category is MemoryCategory.SKILL],
            key=lambda item: (-self._importance(item), -item.updated_at.timestamp(), item.memory_id),
        )
        interests = sorted(
            [r for r in active_records if r.category is MemoryCategory.INTEREST],
            key=lambda item: (-self._importance(item), -item.updated_at.timestamp(), item.memory_id),
        )
        key_facts = sorted(
            [r for r in active_records if r.category is MemoryCategory.FACT and self._importance(r) >= 0.40],
            key=lambda item: (-self._importance(item), -item.updated_at.timestamp(), item.memory_id),
        )
        recent_events = sorted(
            [r for r in active_records if r.category is MemoryCategory.EVENT],
            key=lambda item: (-item.updated_at.timestamp(), item.memory_id),
        )

        # Active relationships connecting user model records
        active_ids = {r.memory_id for r in active_records}
        relationships: list[MemoryRelationship] = []
        if self.relational is not None:
            raw_rels = self.relational.get_relationships(context, active_only=True)
            for rel in raw_rels:
                if rel.source_memory_id in active_ids and rel.target_memory_id in active_ids:
                    relationships.append(rel)

        # Build explainable summary prompt
        sections = [f"[Coherent User Model: {context.user_id}]"]
        if preferences:
            sections.append("Preferences:\n" + "\n".join(f"  - {self._text(r)}" for r in preferences[:5]))
        if goals:
            sections.append("Goals:\n" + "\n".join(f"  - {self._text(r)}" for r in goals[:5]))
        if projects:
            sections.append("Projects:\n" + "\n".join(f"  - {self._text(r)}" for r in projects[:5]))
        if skills:
            sections.append("Skills:\n" + "\n".join(f"  - {self._text(r)}" for r in skills[:5]))
        if key_facts:
            sections.append("Key Facts:\n" + "\n".join(f"  - {self._text(r)}" for r in key_facts[:5]))
        if recent_events:
            sections.append("Recent Events:\n" + "\n".join(f"  - {self._text(r)}" for r in recent_events[:3]))

        summary_prompt = "\n\n".join(sections)

        return UserModel(
            user_id=context.user_id,
            preferences=preferences,
            goals=goals,
            projects=projects,
            skills=skills,
            interests=interests,
            key_facts=key_facts,
            recent_events=recent_events,
            relationships=relationships,
            generated_at=timestamp,
            summary_prompt=summary_prompt,
        )
