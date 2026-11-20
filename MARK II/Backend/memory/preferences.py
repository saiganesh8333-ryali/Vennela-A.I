"""Deterministic Preference Evolution Engine (Level 6)."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .api import MemoryAPI
from .intelligent import IntelligentMemory
from .models import AuthContext, MemoryCategory, MemoryDomain, MemoryRecord, PreferenceEvolutionResult
from .security import MemoryAuthorizationError, authorize


class PreferenceEvolutionEngine:
    """Manages the lifecycle and historical evolution of user preferences without data loss."""

    def __init__(self, api: MemoryAPI, intelligent: Optional[IntelligentMemory] = None):
        self.api = api
        self.intelligent = intelligent

    @staticmethod
    def _text(record: MemoryRecord) -> str:
        if isinstance(record.content, dict):
            return str(record.content.get("text", record.content.get("content", ""))).strip()
        return str(record.content).strip()

    @staticmethod
    def _infer_topic(text: str) -> str:
        lowered = text.lower()
        match = re.search(r"(?:favorite|prefer|like|love|choice is)\s+([a-z0-9_\-]+)", lowered)
        if match:
            return match.group(1).strip()
        tokens = [t for t in re.findall(r"[a-z0-9]+", lowered) if t not in ("i", "my", "a", "the", "to", "is", "in", "it", "prefer", "like", "love", "favorite")]
        return tokens[0] if tokens else "general"

    def evolve_preference(
        self,
        context: AuthContext,
        new_preference_text: str,
        topic: Optional[str] = None,
        importance: float = 0.80,
    ) -> PreferenceEvolutionResult:
        """Evolve user preference, preserving historical preferences non-destructively."""
        clean_text = new_preference_text.strip()
        if not clean_text:
            raise ValueError("preference text is required")

        inferred_topic = topic.strip().lower() if topic and topic.strip() else self._infer_topic(clean_text)

        # Retrieve all preference records for this user (both active and inactive)
        all_records = self.api.repository.retrieve(context.user_id, MemoryDomain.BOSS_PERSONAL)
        all_prefs = [r for r in all_records if r.category is MemoryCategory.PREFERENCE]

        # Partition into active preferences matching topic and historical
        active_matches = []
        historical = []
        for r in all_prefs:
            r_topic = r.content.get("topic") if isinstance(r.content, dict) else None
            if not r_topic:
                r_topic = self._infer_topic(self._text(r))

            if r_topic == inferred_topic:
                if r.active:
                    active_matches.append(r)
                else:
                    historical.append(r)

        now = datetime.now(timezone.utc)

        # Check if identical preference already active
        for active in active_matches:
            if self._text(active).lower() == clean_text.lower():
                # Reinforce existing preference
                old_content = dict(active.content) if isinstance(active.content, dict) else {"text": self._text(active)}
                reinf = int(old_content.get("reinforcement_count", 1)) + 1
                old_content["reinforcement_count"] = reinf
                old_content["importance"] = max(float(old_content.get("importance", 0.5)), importance)
                old_content["last_reinforced_at"] = now.isoformat()
                updated = self.api.update(context, active.memory_id, old_content, category="Preference")
                return PreferenceEvolutionResult(
                    topic=inferred_topic,
                    current_preference=updated,
                    historical_preferences=historical,
                    conflicting_preferences=[],
                    action_taken="reinforced",
                )

        new_memory_id = str(uuid4())

        # If previous active preference exists, evolve it to historical
        if active_matches:
            superseded_records = []
            for old_rec in active_matches:
                # Collect any older superseded records from old_rec
                if isinstance(old_rec.content, dict):
                    for prev_id in old_rec.content.get("supersedes", []):
                        prev_rec = self.api.repository.get(prev_id)
                        if prev_rec is not None and prev_rec not in historical:
                            historical.append(prev_rec)

                # Soft-deactivate old preference
                self.api.forget(context, old_rec.memory_id)

                old_content = dict(old_rec.content) if isinstance(old_rec.content, dict) else {"text": self._text(old_rec)}
                old_content["evolution_state"] = "historical"
                old_content["superseded_by"] = new_memory_id
                old_content["superseded_at"] = now.isoformat()
                updated_old = self.api.update(context, old_rec.memory_id, old_content, category="Preference")
                historical.append(updated_old)
                superseded_records.append(updated_old)

            # Create new active preference record
            new_payload = {
                "text": clean_text,
                "topic": inferred_topic,
                "importance": importance,
                "classification": "Preference",
                "evolution_state": "current",
                "supersedes": [s.memory_id for s in superseded_records],
                "previous_preference": self._text(superseded_records[0]),
                "evolved_at": now.isoformat(),
            }
            new_record = self.api.create(
                context,
                content=new_payload,
                category="Preference",
                domain="boss_personal",
                memory_id=new_memory_id,
            )
            historical.sort(key=lambda item: item.updated_at.timestamp())
            return PreferenceEvolutionResult(
                topic=inferred_topic,
                current_preference=new_record,
                historical_preferences=historical,
                conflicting_preferences=[],
                action_taken="evolved",
            )

        # First time preference for this topic
        new_payload = {
            "text": clean_text,
            "topic": inferred_topic,
            "importance": importance,
            "classification": "Preference",
            "evolution_state": "current",
            "created_at": now.isoformat(),
        }
        new_record = self.api.create(
            context,
            content=new_payload,
            category="Preference",
            domain="boss_personal",
            memory_id=new_memory_id,
        )
        return PreferenceEvolutionResult(
            topic=inferred_topic,
            current_preference=new_record,
            historical_preferences=historical,
            conflicting_preferences=[],
            action_taken="created",
        )

    def get_preference_history(
        self,
        context: AuthContext,
        topic: str,
    ) -> PreferenceEvolutionResult:
        """Retrieve the chronological evolution history of a preference topic."""
        clean_topic = topic.strip().lower()
        all_records = self.api.repository.retrieve(context.user_id, MemoryDomain.BOSS_PERSONAL)
        prefs = [r for r in all_records if r.category is MemoryCategory.PREFERENCE]

        current = None
        historical = []
        conflicting = []

        for r in prefs:
            authorize(context, r.domain, r.session_id, r)
            r_topic = r.content.get("topic") if isinstance(r.content, dict) else None
            if not r_topic:
                r_topic = self._infer_topic(self._text(r))

            if r_topic == clean_topic:
                if r.active:
                    if isinstance(r.content, dict) and r.content.get("conflict_status") == "ambiguous":
                        conflicting.append(r)
                    elif current is None:
                        current = r
                    else:
                        conflicting.append(r)
                else:
                    historical.append(r)

        # Traverse supersedes chain on current and conflicting preferences
        visited_ids = {r.memory_id for r in historical}
        if current is not None:
            visited_ids.add(current.memory_id)

        to_fetch = []
        if current and isinstance(current.content, dict):
            to_fetch.extend(current.content.get("supersedes", []))
        for c_rec in conflicting:
            if isinstance(c_rec.content, dict):
                to_fetch.extend(c_rec.content.get("supersedes", []))

        while to_fetch:
            sid = to_fetch.pop(0)
            if sid in visited_ids:
                continue
            visited_ids.add(sid)
            s_rec = self.api.repository.get(sid)
            if s_rec is not None:
                authorize(context, s_rec.domain, s_rec.session_id, s_rec)
                historical.append(s_rec)
                if isinstance(s_rec.content, dict) and "supersedes" in s_rec.content:
                    for next_sid in s_rec.content["supersedes"]:
                        if next_sid not in visited_ids:
                            to_fetch.append(next_sid)

        # Sort historical chronologically
        historical.sort(key=lambda item: item.updated_at.timestamp())

        return PreferenceEvolutionResult(
            topic=clean_topic,
            current_preference=current,
            historical_preferences=historical,
            conflicting_preferences=conflicting,
            action_taken="retrieved",
        )
