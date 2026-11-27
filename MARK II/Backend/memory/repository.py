"""Repository implementations for the Basic Memory Layer."""

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
import logging
import threading
from typing import Any
from .models import MemoryCategory, MemoryDomain, MemoryRecord, MemoryRelationship, RelationshipType

logger = logging.getLogger(__name__)

_VALID_DOMAINS: dict[str, MemoryDomain] = {d.value: d for d in MemoryDomain}
_VALID_CATEGORIES: dict[str, MemoryCategory] = {c.value: c for c in MemoryCategory}


def validate_memory_domain(raw_domain: Any) -> MemoryDomain:
    """Validate raw domain strictly against the supported MARK-I/II MemoryDomain contract."""
    if isinstance(raw_domain, MemoryDomain):
        return raw_domain
    if not isinstance(raw_domain, str):
        raise ValueError(f"Invalid memory domain type: {type(raw_domain).__name__}")
    normalized = raw_domain.strip().lower()
    if normalized not in _VALID_DOMAINS:
        raise ValueError(f"Unsupported memory domain: {normalized!r}")
    return _VALID_DOMAINS[normalized]


def normalize_memory_category(raw_category: Any, *, memory_id: str | None = None) -> MemoryCategory:
    """Normalize legitimate category capitalization/whitespace; safely fallback empty/null to Fact."""
    if isinstance(raw_category, MemoryCategory):
        return raw_category
    if raw_category is None:
        logger.warning(
            "mark_i_category_fallback memory_id=%s reason=null_category fallback=Fact",
            memory_id or "<unknown>",
        )
        return MemoryCategory.FACT
    if not isinstance(raw_category, str):
        raise ValueError(f"Invalid memory category type: {type(raw_category).__name__}")
    stripped = raw_category.strip()
    if not stripped:
        logger.warning(
            "mark_i_category_fallback memory_id=%s reason=empty_category fallback=Fact",
            memory_id or "<unknown>",
        )
        return MemoryCategory.FACT
    normalized = stripped.title()
    if normalized in _VALID_CATEGORIES:
        return _VALID_CATEGORIES[normalized]
    raise ValueError(f"Unsupported memory category: {stripped!r}")


def parse_iso_timestamp(value: Any, *, field_name: str = "timestamp") -> datetime:
    """Parse ISO-8601 strings (Z, offsets, naive) or datetimes into timezone-aware UTC datetimes."""
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError(f"Empty {field_name}")
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    raise ValueError(f"Malformed {field_name} ({type(value).__name__})")


def parse_memory_row(row: Any) -> MemoryRecord:
    """Parse and normalize a database row into a MemoryRecord without leaking payload content."""
    if not isinstance(row, Mapping):
        raise ValueError(f"Invalid row type: {type(row).__name__}")

    raw_id = row.get("memory_id")
    memory_id = raw_id.strip() if isinstance(raw_id, str) else ""
    if not memory_id:
        raise ValueError("Missing required field: memory_id")

    raw_owner = row.get("owner_id")
    owner_id = raw_owner.strip() if isinstance(raw_owner, str) else ""
    if not owner_id:
        raise ValueError("Missing required field: owner_id")

    domain = validate_memory_domain(row.get("domain"))
    category = normalize_memory_category(row.get("category"), memory_id=memory_id)

    if "content" not in row or row.get("content") is None:
        raise ValueError("Missing required field: content")
    content = row["content"]

    raw_sid = row.get("session_id")
    if raw_sid is None:
        session_id = None
    elif isinstance(raw_sid, str):
        session_id = raw_sid.strip() or None
    else:
        raise ValueError(f"Invalid session_id type: {type(raw_sid).__name__}")

    has_created = "created_at" in row and row.get("created_at") is not None
    has_updated = "updated_at" in row and row.get("updated_at") is not None
    if not has_created and not has_updated:
        raise ValueError("Missing required timestamps: created_at and updated_at")

    if has_created and has_updated:
        created_at = parse_iso_timestamp(row.get("created_at"), field_name="created_at")
        updated_at = parse_iso_timestamp(row.get("updated_at"), field_name="updated_at")
    elif has_created:
        created_at = parse_iso_timestamp(row.get("created_at"), field_name="created_at")
        updated_at = created_at
    else:
        updated_at = parse_iso_timestamp(row.get("updated_at"), field_name="updated_at")
        created_at = updated_at

    raw_active = row.get("active", True)
    if raw_active is None:
        active = True
    elif isinstance(raw_active, str):
        active = raw_active.strip().lower() not in {"false", "0", "no", "f"}
    else:
        active = bool(raw_active)

    return MemoryRecord(
        memory_id=memory_id,
        owner_id=owner_id,
        domain=domain,
        category=category,
        content=content,
        session_id=session_id,
        created_at=created_at,
        updated_at=updated_at,
        active=active,
    )


class MemoryRepository:
    requires_owner_scoped_get: bool = False

    def create(self, record: MemoryRecord) -> MemoryRecord:
        raise NotImplementedError

    def retrieve(self, owner_id: str, domain: MemoryDomain,
                 session_id: str | None = None) -> list[MemoryRecord]:
        raise NotImplementedError

    def update(self, record: MemoryRecord, owner_id: str | None = None) -> MemoryRecord:
        raise NotImplementedError

    def forget(self, memory_id: str, owner_id: str | None = None) -> bool:
        raise NotImplementedError

    def get(self, memory_id: str, owner_id: str | None = None) -> MemoryRecord | None:
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


def _require_owner_id(owner_id: str | None, operation: str) -> str:
    """Fail closed when owner_id is missing or blank."""
    clean = owner_id.strip() if isinstance(owner_id, str) else ""
    if not clean:
        raise ValueError(f"[SEC-ID-01] owner_id is required for {operation}")
    return clean


class InMemoryMemoryRepository(MemoryRepository):
    """Deterministic repository for tests and local callers; production uses Supabase."""

    def __init__(self):
        self._records: dict[str, MemoryRecord] = {}
        self._relationships: dict[str, MemoryRelationship] = {}

    def create(self, record):
        _require_owner_id(record.owner_id, "InMemoryMemoryRepository.create")
        if record.memory_id in self._records:
            raise ValueError("memory_id already exists")
        self._records[record.memory_id] = deepcopy(record)
        return deepcopy(record)

    def retrieve(self, owner_id, domain, session_id=None):
        clean_owner = _require_owner_id(owner_id, "InMemoryMemoryRepository.retrieve")
        records = [
            deepcopy(record) for record in self._records.values()
            if record.owner_id == clean_owner and record.domain == domain
            and record.active and (domain != MemoryDomain.SESSION or record.session_id == session_id)
        ]
        return sorted(records, key=lambda item: item.updated_at, reverse=True)

    def update(self, record, owner_id: str | None = None):
        existing = self._records.get(record.memory_id)
        if existing is None:
            raise KeyError("memory not found")
        effective_owner = _require_owner_id(
            owner_id if owner_id is not None else record.owner_id,
            "InMemoryMemoryRepository.update",
        )
        if existing.owner_id != effective_owner or record.owner_id != effective_owner:
            raise KeyError("memory not found")
        self._records[record.memory_id] = deepcopy(record)
        return deepcopy(record)

    def get(self, memory_id, owner_id: str | None = None):
        record = self._records.get(memory_id)
        if record is None:
            return None
        if owner_id is not None:
            clean_owner = _require_owner_id(owner_id, "InMemoryMemoryRepository.get")
            if record.owner_id != clean_owner:
                return None
        return deepcopy(record)

    def forget(self, memory_id, owner_id: str | None = None):
        record = self._records.get(memory_id)
        if record is None:
            return False
        if owner_id is not None:
            clean_owner = _require_owner_id(owner_id, "InMemoryMemoryRepository.forget")
            if record.owner_id != clean_owner:
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
    requires_owner_scoped_get: bool = True

    def __init__(self, client):
        self.client = client
        self._retrieval_tls = threading.local()

    @staticmethod
    def _check(response):
        error = getattr(response, "error", None)
        if error:
            raise RuntimeError(f"Supabase memory operation failed: {error}")
        return getattr(response, "data", []) or []

    @staticmethod
    def _record(row):
        return parse_memory_row(row)

    def get_last_retrieval_diagnostics(self) -> dict[str, Any] | None:
        """Return thread-scoped diagnostics from the most recent retrieve() call."""
        stats = getattr(self._retrieval_tls, "last_stats", None)
        return dict(stats) if isinstance(stats, dict) else None

    def create(self, record):
        _require_owner_id(record.owner_id, "SupabaseMemoryRepository.create")
        rows = self._check(
            self.client.table(self.table_name).insert(record.to_dict()).execute()
        )
        if not rows:
            raise RuntimeError("Supabase memory create returned no row")
        return self._record(rows[0])

    def retrieve(self, owner_id, domain, session_id=None):
        clean_owner = _require_owner_id(owner_id, "SupabaseMemoryRepository.retrieve")
        query = (
            self.client.table(self.table_name)
            .select("*")
            .eq("owner_id", clean_owner)
            .eq("domain", domain.value)
            .eq("active", True)
        )
        if session_id is not None:
            query = query.eq("session_id", session_id)
        rows = self._check(query.order("updated_at", desc=True).execute())

        valid_records: list[MemoryRecord] = []
        skipped_count = 0
        for row in rows:
            try:
                record = self._record(row)
                if record is not None:
                    valid_records.append(record)
            except (ValueError, TypeError, KeyError, AttributeError) as exc:
                skipped_count += 1
                row_id = "<unknown>"
                if isinstance(row, Mapping) and row.get("memory_id") is not None:
                    row_id = str(row.get("memory_id")).strip()[:64] or "<unknown>"
                logger.warning(
                    "mark_i_row_skipped provider=SupabaseMemoryRepository memory_id=%s domain=%s error_type=%s",
                    row_id,
                    domain.value,
                    type(exc).__name__,
                )

        self._retrieval_tls.last_stats = {
            "owner_id_queried": clean_owner,
            "domain": domain.value,
            "raw_rows_fetched": len(rows),
            "valid_rows_parsed": len(valid_records),
            "skipped_rows_count": skipped_count,
        }
        return valid_records

    def update(self, record, owner_id: str | None = None):
        effective_owner = _require_owner_id(
            owner_id if owner_id is not None else record.owner_id,
            "SupabaseMemoryRepository.update",
        )
        if record.owner_id != effective_owner:
            raise PermissionError("memory ownership mismatch")
        payload = record.to_dict()
        # Never permit ownership reassignment during record updates.
        payload.pop("owner_id", None)
        rows = self._check(
            self.client.table(self.table_name)
            .update(payload)
            .eq("memory_id", record.memory_id)
            .eq("owner_id", effective_owner)
            .execute()
        )
        if not rows:
            raise KeyError("memory not found")
        return self._record(rows[0])

    def get(self, memory_id, owner_id: str):
        clean_owner = _require_owner_id(owner_id, "SupabaseMemoryRepository.get")
        rows = self._check(
            self.client.table(self.table_name)
            .select("*")
            .eq("memory_id", memory_id)
            .eq("owner_id", clean_owner)
            .limit(1)
            .execute()
        )
        return self._record(rows[0]) if rows else None

    def forget(self, memory_id, owner_id: str):
        clean_owner = _require_owner_id(owner_id, "SupabaseMemoryRepository.forget")
        rows = self._check(
            self.client.table(self.table_name)
            .update({"active": False})
            .eq("memory_id", memory_id)
            .eq("owner_id", clean_owner)
            .execute()
        )
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

