"""Controlled Basic Memory API."""

from typing import Any, Optional
from uuid import uuid4

from .models import AuthContext, MemoryCategory, MemoryDomain, MemoryRecord, MemoryStatus
from .repository import MemoryRepository
from .security import authorize


class MemoryAPI:
    def __init__(self, repository: MemoryRepository):
        self.repository = repository

    @staticmethod
    def _domain(value):
        try:
            return value if isinstance(value, MemoryDomain) else MemoryDomain(value)
        except ValueError as exc:
            raise ValueError("invalid memory domain") from exc

    @staticmethod
    def _category(value):
        try:
            return value if isinstance(value, MemoryCategory) else MemoryCategory(value)
        except ValueError as exc:
            raise ValueError("invalid memory category") from exc

    def create(self, context: AuthContext, content: Any, category: str,
               domain: str = MemoryDomain.BOSS_PERSONAL.value,
               session_id: Optional[str] = None, memory_id: Optional[str] = None):
        domain_value = self._domain(domain)
        category_value = self._category(category)
        authorize(context, domain_value, session_id)
        if domain_value == MemoryDomain.SESSION and not session_id:
            raise ValueError("session_id is required for session memory")
        if domain_value != MemoryDomain.SESSION and session_id is not None:
            raise ValueError("session_id is only valid for session memory")
        record = MemoryRecord.now(memory_id or str(uuid4()), context.user_id,
                                  domain_value, category_value, content, session_id)
        # API writes are validated, user-authorized records and become retrievable.
        record = record.transition(MemoryStatus.ACTIVE)
        return self.repository.create(record)

    store = create

    def retrieve(self, context: AuthContext, domain: str = MemoryDomain.BOSS_PERSONAL.value,
                 session_id: Optional[str] = None, query: Optional[str] = None,
                 limit: int = 20):
        domain_value = self._domain(domain)
        authorize(context, domain_value, session_id)
        records = self.repository.retrieve(context.user_id, domain_value, session_id)
        if query and query.strip():
            terms = set(query.lower().split())
            records.sort(key=lambda item: (len(terms & set(str(item.content).lower().split())), item.updated_at), reverse=True)
        return records[:max(0, limit)]

    def update(self, context: AuthContext, memory_id: str, content: Any,
               category: Optional[str] = None):
        if not memory_id:
            raise ValueError("memory_id is required")
        existing = self.repository.get(memory_id)
        if existing is None:
            raise KeyError("memory not found")
        authorize(context, existing.domain, existing.session_id, existing)
        if existing.status is MemoryStatus.DELETED:
            raise ValueError("deleted memory cannot be updated")
        updated = existing.with_updates(
            content=content,
            category=self._category(category) if category is not None else existing.category,
        )
        return self.repository.update(updated)

    def forget(self, context: AuthContext, memory_id: str):
        if not memory_id:
            raise ValueError("memory_id is required")
        existing = self.repository.get(memory_id)
        if existing is None:
            raise KeyError("memory not found")
        authorize(context, existing.domain, existing.session_id, existing)
        self.repository.transition_status(memory_id, MemoryStatus.DELETED)
        return True

    delete = forget
