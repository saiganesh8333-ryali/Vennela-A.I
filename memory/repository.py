"""Repository implementations for the Basic Memory Layer."""

from copy import deepcopy
from datetime import datetime
from .models import MemoryCategory, MemoryDomain, MemoryRecord


class MemoryRepository:
    def create(self, record: MemoryRecord) -> MemoryRecord:
        raise NotImplementedError

    def retrieve(self, owner_id: str, domain: MemoryDomain,
                 session_id: str | None = None) -> list[MemoryRecord]:
        raise NotImplementedError

    def update(self, record: MemoryRecord) -> MemoryRecord:
        raise NotImplementedError

    def forget(self, memory_id: str) -> bool:
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
        records = [
            deepcopy(record) for record in self._records.values()
            if record.owner_id == owner_id and record.domain == domain
            and record.active and (domain != MemoryDomain.SESSION or record.session_id == session_id)
        ]
        return sorted(records, key=lambda item: item.updated_at, reverse=True)

    def update(self, record):
        if record.memory_id not in self._records:
            raise KeyError("memory not found")
        self._records[record.memory_id] = deepcopy(record)
        return deepcopy(record)

    def get(self, memory_id):
        record = self._records.get(memory_id)
        return deepcopy(record) if record is not None else None

    def forget(self, memory_id):
        record = self._records.get(memory_id)
        if record is None:
            return False
        self._records[memory_id] = MemoryRecord(
            record.memory_id, record.owner_id, record.domain, record.category,
            record.content, record.session_id, record.created_at,
            datetime.now(record.updated_at.tzinfo), False)
        return True


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
        return MemoryRecord(
            row["memory_id"], row["owner_id"], MemoryDomain(row["domain"]),
            MemoryCategory(row["category"]), row["content"], row.get("session_id"),
            datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
            datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")),
            bool(row.get("active", True)))

    def create(self, record):
        return self._record(self._check(
            self.client.table(self.table_name).insert(record.to_dict()).execute())[0])

    def retrieve(self, owner_id, domain, session_id=None):
        query = self.client.table(self.table_name).select("*").eq("owner_id", owner_id).eq("domain", domain.value).eq("active", True)
        if session_id is not None:
            query = query.eq("session_id", session_id)
        rows = self._check(query.order("updated_at", desc=True).execute())
        return [self._record(row) for row in rows]

    def update(self, record):
        rows = self._check(self.client.table(self.table_name).update(record.to_dict()).eq("memory_id", record.memory_id).execute())
        if not rows:
            raise KeyError("memory not found")
        return self._record(rows[0])

    def get(self, memory_id):
        rows = self._check(self.client.table(self.table_name).select("*").eq("memory_id", memory_id).limit(1).execute())
        return self._record(rows[0]) if rows else None

    def forget(self, memory_id):
        rows = self._check(self.client.table(self.table_name).update({"active": False}).eq("memory_id", memory_id).execute())
        return bool(rows)
