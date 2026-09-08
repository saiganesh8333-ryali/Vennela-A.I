"""Compatibility bridge for legacy Smart Memory results into the canonical Memory Layer."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from .api import MemoryAPI
from .models import AuthContext, MemoryCategory, MemoryDomain, MemoryRecord, MemoryStatus


_CLASSIFICATION_MAP = {
    "profile": MemoryCategory.PROFILE,
    "preference": MemoryCategory.PREFERENCE,
    "interest": MemoryCategory.INTEREST,
    "goal": MemoryCategory.GOAL,
    "project": MemoryCategory.PROJECT,
    "skill": MemoryCategory.SKILL,
    "fact": MemoryCategory.FACT,
    "task": MemoryCategory.TASK,
    "event": MemoryCategory.EVENT,
    "relationship": MemoryCategory.RELATIONSHIP,
}


class MemoryCompatibilityAdapter:
    """Convert a Smart Memory result into a canonical MemoryRecord without rewriting legacy behavior."""

    def __init__(self, api: Optional[MemoryAPI] = None):
        self.api = api

    @staticmethod
    def _normalize_processed(processed: Optional[Mapping[str, Any]]) -> dict[str, Any]:
        if isinstance(processed, Mapping):
            return dict(processed)
        return {}

    @staticmethod
    def _as_datetime(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                return None
        return None

    @staticmethod
    def _resolve_domain(domain: Optional[str], session_id: Optional[str]) -> MemoryDomain:
        provided = (domain or MemoryDomain.BOSS_PERSONAL.value).strip()
        try:
            domain_value = MemoryDomain(provided)
        except ValueError as exc:
            raise ValueError("invalid memory domain") from exc
        if domain_value == MemoryDomain.SESSION and not session_id:
            raise ValueError("session_id is required for session memory")
        return domain_value

    @staticmethod
    def _resolve_category(category: Optional[str], processed: Mapping[str, Any]) -> MemoryCategory:
        preferred = category or processed.get("category") or processed.get("classification") or processed.get("type")
        if preferred is None:
            return MemoryCategory.FACT
        value = str(preferred).strip()
        mapped = _CLASSIFICATION_MAP.get(value.lower())
        if mapped is not None:
            return mapped
        try:
            return MemoryCategory(value)
        except ValueError:
            return MemoryCategory.FACT

    @staticmethod
    def _resolve_content(raw_message: Any, processed: Mapping[str, Any]) -> Any:
        if isinstance(processed, Mapping):
            for key in ("compressed", "text", "content", "message", "event"):
                candidate = processed.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
        if isinstance(raw_message, str) and raw_message.strip():
            return raw_message.strip()
        if raw_message is None:
            return ""
        return raw_message

    @staticmethod
    def _resolve_timestamps(processed: Mapping[str, Any]) -> tuple[datetime, datetime]:
        now = datetime.now(timezone.utc)
        created = processed.get("created_at") or processed.get("timestamp") or processed.get("created")
        updated = processed.get("updated_at") or processed.get("timestamp") or processed.get("updated")
        created_dt = MemoryCompatibilityAdapter._as_datetime(created) or now
        updated_dt = MemoryCompatibilityAdapter._as_datetime(updated) or created_dt
        return created_dt, updated_dt

    @staticmethod
    def _resolve_memory_id(processed: Mapping[str, Any], raw_message: Any) -> str:
        identifier = processed.get("memory_id")
        if isinstance(identifier, str) and identifier.strip():
            return identifier.strip()
        if isinstance(raw_message, str) and raw_message.strip():
            return f"compat-{abs(hash(raw_message))}"
        return "compat-memory"

    @staticmethod
    def should_store(processed: Optional[Mapping[str, Any]]) -> bool:
        if processed is None:
            return False
        if "should_store" in processed:
            value = processed.get("should_store")
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "stored"}
            return bool(value)
        if "stored" in processed:
            value = processed.get("stored")
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "stored"}
            return bool(value)
        if "result" in processed and isinstance(processed.get("result"), str):
            return processed.get("result", "").lower() == "stored"
        return False

    def to_record(
        self,
        context: AuthContext,
        raw_message: Any,
        processed: Optional[Mapping[str, Any]] = None,
        domain: Optional[str] = None,
        session_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Optional[MemoryRecord]:
        """Convert a validated Smart Memory candidate into a canonical MemoryRecord."""
        if not isinstance(context, AuthContext):
            raise ValueError("context must be an AuthContext instance")
        if not context.authenticated or not context.user_id:
            raise ValueError("authenticated user context required")

        normalized = self._normalize_processed(processed)
        if not self.should_store(normalized):
            return None

        resolved_domain = self._resolve_domain(
            domain or normalized.get("domain") or MemoryDomain.BOSS_PERSONAL.value,
            session_id,
        )
        resolved_category = self._resolve_category(category, normalized)
        content = self._resolve_content(raw_message, normalized)
        created_at, updated_at = self._resolve_timestamps(normalized)

        if resolved_domain == MemoryDomain.SESSION:
            effective_session_id = session_id
        else:
            effective_session_id = None

        return MemoryRecord(
            memory_id=self._resolve_memory_id(normalized, raw_message),
            owner_id=context.user_id,
            domain=resolved_domain,
            category=resolved_category,
            content=content,
            session_id=effective_session_id,
            created_at=created_at,
            updated_at=updated_at,
            status=MemoryStatus.ACTIVE,
        )

    def persist(
        self,
        context: AuthContext,
        raw_message: Any,
        processed: Optional[Mapping[str, Any]] = None,
        domain: Optional[str] = None,
        session_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Optional[MemoryRecord]:
        """Convert and persist when the Smart Memory result indicates it should be stored."""
        record = self.to_record(
            context=context,
            raw_message=raw_message,
            processed=processed,
            domain=domain,
            session_id=session_id,
            category=category,
        )
        if record is None:
            return None
        if self.api is None:
            return record
        return self.api.create(
            context,
            record.content,
            record.category.value,
            domain=record.domain.value,
            session_id=record.session_id,
        )
