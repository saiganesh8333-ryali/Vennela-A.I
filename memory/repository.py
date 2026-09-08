"""Repository implementations for the Basic Memory Layer."""

from copy import deepcopy
from datetime import datetime
from .models import MemoryCategory, MemoryDomain, MemoryRecord, MemoryStatus


class MemoryRepository:
    def create(self, record: MemoryRecord) -> MemoryRecord:
        raise NotImplementedError

    def retrieve(self, owner_id: str, domain: MemoryDomain,
                 session_id: str | None = None) -> list[MemoryRecord]:
        raise NotImplementedError

    def list(self, owner_id: str, domain: MemoryDomain,
             session_id: str | None = None) -> list[MemoryRecord]:
        return self.retrieve(owner_id, domain, session_id)

    def update(self, record: MemoryRecord) -> MemoryRecord:
        raise NotImplementedError

    def forget(self, memory_id: str) -> bool:
        raise NotImplementedError

    def transition_status(self, memory_id: str, status: MemoryStatus) -> MemoryRecord:
        raise NotImplementedError

    def get(self, memory_id: str) -> MemoryRecord | None:
        raise NotImplementedError


class InMemoryMemoryRepository(MemoryRepository):
    """Deterministic repository for tests and local callers; production uses Supabase."""

    def __init__(self):
        self._records: dict[str, MemoryRecord] = {}

    def create(self, record):
        if record.memory_id in self._records:
            raise ValueError("memory_id already exists")
        self._records[record.memory_id] = deepcopy(record)
        return deepcopy(record)

    def retrieve(self, owner_id, domain, session_id=None):
        domain = domain if isinstance(domain, MemoryDomain) else MemoryDomain(domain)
        if domain is MemoryDomain.SESSION and not session_id:
            raise ValueError("session_id is required for session memory")
        if domain is not MemoryDomain.SESSION and session_id is not None:
            raise ValueError("session_id is only valid for session memory")
        records = [
            deepcopy(record) for record in self._records.values()
            if record.owner_id == owner_id and record.domain == domain
            and record.status is MemoryStatus.ACTIVE
            and (domain != MemoryDomain.SESSION or record.session_id == session_id)
        ]
        return sorted(records, key=lambda item: item.updated_at, reverse=True)

    def update(self, record):
        if record.memory_id not in self._records:
            raise KeyError("memory not found")
        existing = self._records[record.memory_id]
        if (record.owner_id, record.domain, record.session_id) != (
            existing.owner_id, existing.domain, existing.session_id
        ):
            raise ValueError("memory ownership, domain, and session are immutable")
        if record.created_at != existing.created_at:
            raise ValueError("created_at is immutable")
        self._records[record.memory_id] = deepcopy(record)
        return deepcopy(record)

    def get(self, memory_id):
        record = self._records.get(memory_id)
        return deepcopy(record) if record is not None else None

    def forget(self, memory_id):
        if memory_id not in self._records:
            return False
        self.transition_status(memory_id, MemoryStatus.DELETED)
        return True

    def transition_status(self, memory_id, status):
        record = self._records.get(memory_id)
        if record is None:
            raise KeyError("memory not found")
        updated = record.transition(status)
        self._records[memory_id] = deepcopy(updated)
        return deepcopy(updated)


class SupabaseMemoryRepository(MemoryRepository):
    """Supabase-only production repository using the canonical memories contract."""

    table_name = "memories"

    def __init__(self, client):
        self.client = client

    @staticmethod
    def _check(response):
        error = getattr(response, "error", None)
        if error:
            raise RuntimeError(f"Supabase memory operation failed: {error}")
        return getattr(response, "data", []) or []

    @staticmethod
    def _record(row):
        status = row.get("status")
        if status is None:
            status = MemoryStatus.ACTIVE if row.get("active", True) else MemoryStatus.DELETED
        return MemoryRecord(
            memory_id=row["memory_id"],
            owner_id=row["owner_id"],
            domain=MemoryDomain(row["domain"]),
            category=MemoryCategory(row["category"]),
            content=row["content"],
            source=row.get("source", "conversation"),
            confidence=row.get("confidence", 0.5),
            importance=row.get("importance", 0.0),
            status=status,
            created_at=row["created_at"],
            updated_at=row.get("updated_at"),
            last_accessed_at=row.get("last_accessed_at"),
            expires_at=row.get("expires_at"),
            session_id=row.get("session_id"),
            embedding=row.get("embedding"),
            metadata=row.get("metadata") or {},
        )

    def create(self, record):
        return self._record(self._check(
            self.client.table(self.table_name).insert(record.to_dict()).execute())[0])

    def retrieve(self, owner_id, domain, session_id=None):
        domain = domain if isinstance(domain, MemoryDomain) else MemoryDomain(domain)
        if domain is MemoryDomain.SESSION and not session_id:
            raise ValueError("session_id is required for session memory")
        if domain is not MemoryDomain.SESSION and session_id is not None:
            raise ValueError("session_id is only valid for session memory")
        query = (
            self.client.table(self.table_name).select("*")
            .eq("owner_id", owner_id)
            .eq("domain", domain.value)
            .eq("status", MemoryStatus.ACTIVE.value)
        )
        if session_id is not None:
            query = query.eq("session_id", session_id)
        rows = self._check(query.order("updated_at", desc=True).execute())
        return [self._record(row) for row in rows]

    def list(self, owner_id, domain, session_id=None):
        return self.retrieve(owner_id, domain, session_id)

    def update(self, record):
        existing = self.get(record.memory_id)
        if existing is None:
            raise KeyError("memory not found")
        if (record.owner_id, record.domain, record.session_id, record.created_at) != (
            existing.owner_id, existing.domain, existing.session_id, existing.created_at
        ):
            raise ValueError("memory ownership, domain, session, and created_at are immutable")
        payload = record.to_dict()
        payload.pop("active", None)
        rows = self._check(
            self.client.table(self.table_name)
            .update(payload)
            .eq("memory_id", record.memory_id)
            .execute()
        )
        return self._record(rows[0])

    def get(self, memory_id):
        rows = self._check(self.client.table(self.table_name).select("*").eq("memory_id", memory_id).limit(1).execute())
        return self._record(rows[0]) if rows else None

    def forget(self, memory_id):
        return bool(self.transition_status(memory_id, MemoryStatus.DELETED))

    def transition_status(self, memory_id, status):
        target = status if isinstance(status, MemoryStatus) else MemoryStatus(status)
        current = self.get(memory_id)
        if current is None:
            raise KeyError("memory not found")
        updated = current.transition(target)
        rows = self._check(
            self.client.table(self.table_name)
            .update({
                "status": updated.status.value,
                "active": updated.active,
                "updated_at": updated.updated_at.isoformat(),
            })
            .eq("memory_id", memory_id)
            .execute()
        )
        if not rows:
            raise KeyError("memory not found")
        return self._record(rows[0])
