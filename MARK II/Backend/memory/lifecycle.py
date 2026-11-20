"""Deterministic Memory Lifecycle and Obsolescence Management (Level 6)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .api import MemoryAPI
from .models import AuthContext, MemoryDomain, MemoryNotFoundError, MemoryRecord, MemoryLifecycleState
from .security import MemoryAuthorizationError, authorize


class MemoryLifecycleManager:
    """Manages explicit lifecycle transitions and non-destructive obsolescence."""

    VALID_TRANSITIONS = {
        MemoryLifecycleState.NEW: {
            MemoryLifecycleState.ACTIVE,
            MemoryLifecycleState.INACTIVE,
        },
        MemoryLifecycleState.ACTIVE: {
            MemoryLifecycleState.REINFORCED,
            MemoryLifecycleState.SUPERSEDED,
            MemoryLifecycleState.OBSOLETE,
            MemoryLifecycleState.INACTIVE,
        },
        MemoryLifecycleState.REINFORCED: {
            MemoryLifecycleState.REINFORCED,
            MemoryLifecycleState.SUPERSEDED,
            MemoryLifecycleState.OBSOLETE,
            MemoryLifecycleState.INACTIVE,
        },
        MemoryLifecycleState.SUPERSEDED: {
            MemoryLifecycleState.ACTIVE,
            MemoryLifecycleState.INACTIVE,
        },
        MemoryLifecycleState.OBSOLETE: {
            MemoryLifecycleState.ACTIVE,
            MemoryLifecycleState.INACTIVE,
        },
        MemoryLifecycleState.INACTIVE: {
            MemoryLifecycleState.ACTIVE,
        },
    }

    def __init__(self, api: MemoryAPI):
        self.api = api

    @staticmethod
    def _normalize_state(value: Any) -> MemoryLifecycleState:
        if isinstance(value, MemoryLifecycleState):
            return value
        if isinstance(value, str):
            try:
                return MemoryLifecycleState(value.strip().upper())
            except ValueError:
                pass
        raise ValueError(f"invalid lifecycle state: {value}")

    def get_lifecycle_state(self, record: MemoryRecord) -> MemoryLifecycleState:
        if isinstance(record.content, dict) and "lifecycle_state" in record.content:
            try:
                return self._normalize_state(record.content["lifecycle_state"])
            except ValueError:
                pass
        return MemoryLifecycleState.ACTIVE if record.active else MemoryLifecycleState.INACTIVE

    def transition_state(
        self,
        context: AuthContext,
        memory_id: str,
        target_state: str | MemoryLifecycleState,
        reason: str = "",
    ) -> MemoryRecord:
        """Deterministically transition memory lifecycle state."""
        if not isinstance(memory_id, str) or not memory_id.strip():
            raise ValueError("memory_id is required")

        record = self.api.repository.get(memory_id.strip())
        if record is None:
            raise MemoryNotFoundError(f"memory not found: {memory_id}")

        authorize(context, record.domain, record.session_id, record)

        target = self._normalize_state(target_state)
        current = self.get_lifecycle_state(record)

        if target not in self.VALID_TRANSITIONS.get(current, set()):
            raise ValueError(
                f"invalid lifecycle transition from {current.value} to {target.value}"
            )

        now = datetime.now(timezone.utc)
        content = dict(record.content) if isinstance(record.content, dict) else {"text": str(record.content)}
        history = list(content.get("lifecycle_history", []))
        history.append({
            "from": current.value,
            "to": target.value,
            "timestamp": now.isoformat(),
            "reason": reason,
        })
        content["lifecycle_state"] = target.value
        content["lifecycle_history"] = history

        if target == MemoryLifecycleState.OBSOLETE:
            content["obsolete_reason"] = reason
            content["obsoleted_at"] = now.isoformat()
        elif target == MemoryLifecycleState.SUPERSEDED:
            content["superseded_at"] = now.isoformat()

        # Active flag sync: True for ACTIVE and REINFORCED; False for SUPERSEDED, OBSOLETE, INACTIVE
        new_active = target in (MemoryLifecycleState.ACTIVE, MemoryLifecycleState.REINFORCED)

        updated_record = MemoryRecord(
            memory_id=record.memory_id,
            owner_id=record.owner_id,
            domain=record.domain,
            category=record.category,
            content=content,
            session_id=record.session_id,
            created_at=record.created_at,
            updated_at=now,
            active=new_active,
        )
        return self.api.repository.update(updated_record)

    def mark_obsolete(
        self,
        context: AuthContext,
        memory_id: str,
        reason: str,
    ) -> MemoryRecord:
        """Soft-deactivate a memory and mark it obsolete with structured audit metadata."""
        if not reason:
            reason = "marked obsolete by lifecycle policy"

        return self.transition_state(
            context,
            memory_id,
            MemoryLifecycleState.OBSOLETE,
            reason=reason,
        )

    def detect_obsolete_memories(
        self,
        context: AuthContext,
        domain: str = MemoryDomain.BOSS_PERSONAL.value,
        session_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Identify candidate memories that have become obsolete based on structured signals."""
        domain_value = MemoryDomain(domain)
        records = self.api.retrieve(context, domain_value.value, session_id, limit=200)

        candidates: list[dict[str, Any]] = []
        for r in records:
            if not r.active:
                continue

            content = r.content if isinstance(r.content, dict) else {"text": str(r.content)}
            text = str(content.get("text", "")).lower()

            # Signal 1: Already has supersession tag but was left active
            if "superseded_by" in content:
                candidates.append({
                    "record": r,
                    "reason": f"superseded by {content['superseded_by']}",
                    "signal": "superseded",
                })
                continue

            # Signal 2: Time-sensitive task/event marked as finished/completed
            if any(term in text for term in ("task completed", "task finished", "meeting finished", "resolved")):
                candidates.append({
                    "record": r,
                    "reason": "event or task concluded",
                    "signal": "temporal_concluded",
                })
                continue

            # Signal 3: Explicit expiration date passed
            if "expires_at" in content:
                try:
                    exp = datetime.fromisoformat(content["expires_at"].replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) >= exp:
                        candidates.append({
                            "record": r,
                            "reason": f"expired at {content['expires_at']}",
                            "signal": "expired",
                        })
                except Exception:
                    pass

        return candidates
