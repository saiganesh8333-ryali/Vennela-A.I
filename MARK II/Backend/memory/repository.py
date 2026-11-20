"""Repository implementations for the Basic Memory Layer."""

from copy import deepcopy
from datetime import datetime
from .models import MemoryCategory, MemoryDomain, MemoryRecord, MemoryRelationship, RelationshipType


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

    def create_relationship(self, relationship: MemoryRelationship) -> MemoryRelationship:
        raise NotImplementedError

    def get_relationship(self, relationship_id: str) -> MemoryRelationship | None:
        raise NotImplementedError

    def get_relationships(
        self,
        memory_id: str | None = None,
        source_id: str | None = None,
        target_id: str | None = None,
        relationship_type: RelationshipType | None = None,
        active_only: bool = True,
    ) -> list[MemoryRelationship]:
        raise NotImplementedError

    def update_relationship(self, relationship: MemoryRelationship) -> MemoryRelationship:
        raise NotImplementedError

    def remove_relationship(self, relationship_id: str) -> bool:
        raise NotImplementedError


class InMemoryMemoryRepository(MemoryRepository):
    """Deterministic repository for tests and local callers; production uses Supabase."""

    def __init__(self):
        self._records: dict[str, MemoryRecord] = {}
        self._relationships: dict[str, MemoryRelationship] = {}

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

    def create_relationship(self, relationship):
        if relationship.relationship_id in self._relationships:
            raise ValueError("relationship_id already exists")
        self._relationships[relationship.relationship_id] = deepcopy(relationship)
        return deepcopy(relationship)

    def get_relationship(self, relationship_id):
        rel = self._relationships.get(relationship_id)
        return deepcopy(rel) if rel is not None else None

    def get_relationships(
        self,
        memory_id=None,
        source_id=None,
        target_id=None,
        relationship_type=None,
        active_only=True,
    ):
        results = []
        for rel in self._relationships.values():
            if active_only and not rel.active:
                continue
            if relationship_type is not None and rel.relationship_type != relationship_type:
                continue
            if source_id is not None and rel.source_memory_id != source_id:
                continue
            if target_id is not None and rel.target_memory_id != target_id:
                continue
            if memory_id is not None and rel.source_memory_id != memory_id and rel.target_memory_id != memory_id:
                continue
            results.append(deepcopy(rel))
        return sorted(
            results,
            key=lambda item: (-item.strength, -item.updated_at.timestamp(), item.relationship_id)
        )

    def update_relationship(self, relationship):
        if relationship.relationship_id not in self._relationships:
            raise KeyError("relationship not found")
        self._relationships[relationship.relationship_id] = deepcopy(relationship)
        return deepcopy(relationship)

    def remove_relationship(self, relationship_id):
        rel = self._relationships.get(relationship_id)
        if rel is None:
            return False
        self._relationships[relationship_id] = MemoryRelationship(
            rel.relationship_id, rel.source_memory_id, rel.target_memory_id,
            rel.relationship_type, rel.strength, rel.created_at,
            datetime.now(rel.updated_at.tzinfo), False, rel.metadata
        )
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

    relationships_table = "memory_relationships"

    @staticmethod
    def _relationship(row):
        return MemoryRelationship(
            relationship_id=row["relationship_id"],
            source_memory_id=row["source_memory_id"],
            target_memory_id=row["target_memory_id"],
            relationship_type=RelationshipType(row["relationship_type"]),
            strength=float(row.get("strength", 1.0)),
            created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")),
            active=bool(row.get("active", True)),
            metadata=row.get("metadata") or {},
        )

    def create_relationship(self, relationship):
        rows = self._check(
            self.client.table(self.relationships_table).insert(relationship.to_dict()).execute()
        )
        return self._relationship(rows[0])

    def get_relationship(self, relationship_id):
        rows = self._check(
            self.client.table(self.relationships_table).select("*").eq("relationship_id", relationship_id).limit(1).execute()
        )
        return self._relationship(rows[0]) if rows else None

    def get_relationships(
        self,
        memory_id=None,
        source_id=None,
        target_id=None,
        relationship_type=None,
        active_only=True,
    ):
        query = self.client.table(self.relationships_table).select("*")
        if active_only:
            query = query.eq("active", True)
        if relationship_type is not None:
            rel_type_val = relationship_type.value if isinstance(relationship_type, RelationshipType) else str(relationship_type)
            query = query.eq("relationship_type", rel_type_val)
        if source_id is not None:
            query = query.eq("source_memory_id", source_id)
        if target_id is not None:
            query = query.eq("target_memory_id", target_id)
        if memory_id is not None and source_id is None and target_id is None:
            query = query.or_(f"source_memory_id.eq.{memory_id},target_memory_id.eq.{memory_id}")
        rows = self._check(query.order("updated_at", desc=True).execute())
        results = [self._relationship(row) for row in rows]
        return sorted(
            results,
            key=lambda item: (-item.strength, -item.updated_at.timestamp(), item.relationship_id)
        )

    def update_relationship(self, relationship):
        rows = self._check(
            self.client.table(self.relationships_table).update(relationship.to_dict()).eq("relationship_id", relationship.relationship_id).execute()
        )
        if not rows:
            raise KeyError("relationship not found")
        return self._relationship(rows[0])

    def remove_relationship(self, relationship_id):
        rows = self._check(
            self.client.table(self.relationships_table).update({"active": False}).eq("relationship_id", relationship_id).execute()
        )
        return bool(rows)

