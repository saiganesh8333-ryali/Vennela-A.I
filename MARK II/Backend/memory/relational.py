"""Deterministic Level 4 Relational Memory backed by the canonical Memory API."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Optional, Sequence
from uuid import uuid4

from .api import MemoryAPI
from .models import (
    AuthContext,
    MemoryDomain,
    MemoryNotFoundError,
    MemoryRecord,
    MemoryRelationship,
    RelationshipType,
)
from .security import MemoryAuthorizationError, authorize


@dataclass(frozen=True)
class TraversalStep:
    """A single hop reached during relational graph traversal."""

    memory_id: str
    depth: int
    relationship: MemoryRelationship
    memory: MemoryRecord

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "depth": self.depth,
            "relationship": self.relationship.to_dict(),
            "memory": self.memory.to_dict(),
        }


@dataclass(frozen=True)
class TraversalResult:
    """Deterministic result of a bounded, cycle-safe graph traversal."""

    start_memory_id: str
    start_memory: MemoryRecord
    steps: list[TraversalStep] = field(default_factory=list)

    @property
    def visited_memory_ids(self) -> list[str]:
        return [step.memory_id for step in self.steps]

    @property
    def memories(self) -> list[MemoryRecord]:
        return [step.memory for step in self.steps]

    @property
    def relationships(self) -> list[MemoryRelationship]:
        return [step.relationship for step in self.steps]

    @property
    def depths(self) -> dict[str, int]:
        return {step.memory_id: step.depth for step in self.steps}

    def __iter__(self):
        return iter(self.steps)

    def __len__(self) -> int:
        return len(self.steps)

    def __getitem__(self, index: int) -> TraversalStep:
        return self.steps[index]

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_memory_id": self.start_memory_id,
            "start_memory": self.start_memory.to_dict(),
            "visited_memory_ids": self.visited_memory_ids,
            "steps": [step.to_dict() for step in self.steps],
            "total_nodes": len(self.steps),
        }


class RelationalMemory:
    """Manage explicit, authorized relationships between canonical memory records."""

    def __init__(self, api: MemoryAPI):
        self.api = api

    @staticmethod
    def _normalize_type(value: Any) -> RelationshipType:
        if isinstance(value, RelationshipType):
            return value
        if isinstance(value, str):
            normalized = value.strip().upper()
            try:
                return RelationshipType(normalized)
            except ValueError:
                pass
        raise ValueError(f"invalid relationship type: {value}")

    @staticmethod
    def _normalize_strength(value: Any) -> float:
        try:
            val = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid strength/confidence: {value}") from exc
        if not (0.0 <= val <= 1.0):
            raise ValueError(f"strength must be between 0.0 and 1.0, got {val}")
        return val

    def _get_and_authorize_memory(
        self,
        context: AuthContext,
        memory_id: str,
        label: str = "memory",
    ) -> MemoryRecord:
        if not isinstance(memory_id, str) or not memory_id.strip():
            raise ValueError(f"{label}_memory_id is required")
        clean_id = memory_id.strip()
        record = self.api.repository.get(clean_id)
        if record is None or not record.active:
            raise MemoryNotFoundError(f"{label} memory not found: {clean_id}")
        authorize(context, record.domain, record.session_id, record)
        return record

    def create_relationship(
        self,
        context: AuthContext,
        source_memory_id: str,
        target_memory_id: str,
        relationship_type: str | RelationshipType,
        strength: float = 1.0,
        metadata: Optional[dict[str, Any]] = None,
        relationship_id: Optional[str] = None,
    ) -> MemoryRelationship:
        """Create an explicit, authorized relationship between two canonical memories."""
        if not isinstance(source_memory_id, str) or not source_memory_id.strip():
            raise ValueError("source_memory_id is required")
        if not isinstance(target_memory_id, str) or not target_memory_id.strip():
            raise ValueError("target_memory_id is required")

        source_clean = source_memory_id.strip()
        target_clean = target_memory_id.strip()

        if source_clean == target_clean:
            raise ValueError("cannot link memory to itself: source and target must be distinct")

        rel_type = self._normalize_type(relationship_type)
        rel_strength = self._normalize_strength(strength)

        source_record = self._get_and_authorize_memory(context, source_clean, "source")
        target_record = self._get_and_authorize_memory(context, target_clean, "target")

        # Block unauthorized cross-owner relationships
        if source_record.owner_id != target_record.owner_id:
            raise MemoryAuthorizationError("cross-owner relationship not allowed")

        # Enforce uniqueness for active relationship of the same type between source and target
        existing_active = self.api.repository.get_relationships(
            source_id=source_clean,
            target_id=target_clean,
            relationship_type=rel_type,
            active_only=True,
        )
        if existing_active:
            raise ValueError("relationship already exists")

        rel_id = relationship_id.strip() if isinstance(relationship_id, str) and relationship_id.strip() else str(uuid4())
        relationship = MemoryRelationship.now(
            relationship_id=rel_id,
            source_memory_id=source_clean,
            target_memory_id=target_clean,
            relationship_type=rel_type,
            strength=rel_strength,
            metadata=metadata or {},
            active=True,
        )
        return self.api.repository.create_relationship(relationship)

    def get_relationship(
        self,
        context: AuthContext,
        relationship_id: str,
    ) -> Optional[MemoryRelationship]:
        """Retrieve a specific relationship by ID after validating authorization."""
        if not isinstance(relationship_id, str) or not relationship_id.strip():
            raise ValueError("relationship_id is required")
        rel = self.api.repository.get_relationship(relationship_id.strip())
        if rel is None or not rel.active:
            return None

        # Authorize context on both source and target records
        self._get_and_authorize_memory(context, rel.source_memory_id, "source")
        self._get_and_authorize_memory(context, rel.target_memory_id, "target")
        return rel

    def get_relationships(
        self,
        context: AuthContext,
        memory_id: Optional[str] = None,
        source_memory_id: Optional[str] = None,
        target_memory_id: Optional[str] = None,
        relationship_type: Optional[str | RelationshipType] = None,
        active_only: bool = True,
        direction: str = "both",
    ) -> list[MemoryRelationship]:
        """Retrieve relationships for a given memory or filter with deterministic ordering."""
        rel_type = self._normalize_type(relationship_type) if relationship_type is not None else None

        source_clean = source_memory_id.strip() if isinstance(source_memory_id, str) and source_memory_id.strip() else None
        target_clean = target_memory_id.strip() if isinstance(target_memory_id, str) and target_memory_id.strip() else None
        memory_clean = memory_id.strip() if isinstance(memory_id, str) and memory_id.strip() else None

        if memory_clean:
            self._get_and_authorize_memory(context, memory_clean, "queried")
            if direction == "outgoing":
                source_clean = memory_clean
                memory_clean = None
            elif direction == "incoming":
                target_clean = memory_clean
                memory_clean = None
            elif direction != "both":
                raise ValueError(f"invalid direction: {direction}. Must be 'outgoing', 'incoming', or 'both'")

        if source_clean:
            self._get_and_authorize_memory(context, source_clean, "source")
        if target_clean:
            self._get_and_authorize_memory(context, target_clean, "target")

        raw_relationships = self.api.repository.get_relationships(
            memory_id=memory_clean,
            source_id=source_clean,
            target_id=target_clean,
            relationship_type=rel_type,
            active_only=active_only,
        )

        # Filter relationships to ensure caller has access to the other endpoint
        authorized_relationships: list[MemoryRelationship] = []
        for rel in raw_relationships:
            try:
                self._get_and_authorize_memory(context, rel.source_memory_id, "source")
                self._get_and_authorize_memory(context, rel.target_memory_id, "target")
                authorized_relationships.append(rel)
            except (MemoryAuthorizationError, MemoryNotFoundError):
                continue

        return sorted(
            authorized_relationships,
            key=lambda item: (-item.strength, -item.updated_at.timestamp(), item.relationship_id),
        )

    def update_relationship(
        self,
        context: AuthContext,
        relationship_id: str,
        strength: Optional[float] = None,
        metadata: Optional[dict[str, Any]] = None,
        active: Optional[bool] = None,
    ) -> MemoryRelationship:
        """Update relationship strength, metadata, or active status."""
        if not isinstance(relationship_id, str) or not relationship_id.strip():
            raise ValueError("relationship_id is required")
        clean_id = relationship_id.strip()

        existing = self.api.repository.get_relationship(clean_id)
        if existing is None:
            raise KeyError(f"relationship not found: {clean_id}")

        self._get_and_authorize_memory(context, existing.source_memory_id, "source")
        self._get_and_authorize_memory(context, existing.target_memory_id, "target")

        new_strength = self._normalize_strength(strength) if strength is not None else existing.strength
        new_active = bool(active) if active is not None else existing.active
        new_metadata = dict(existing.metadata or {})
        if metadata is not None:
            new_metadata.update(metadata)

        updated = MemoryRelationship(
            relationship_id=existing.relationship_id,
            source_memory_id=existing.source_memory_id,
            target_memory_id=existing.target_memory_id,
            relationship_type=existing.relationship_type,
            strength=new_strength,
            created_at=existing.created_at,
            updated_at=datetime.now(timezone.utc),
            active=new_active,
            metadata=new_metadata,
        )
        return self.api.repository.update_relationship(updated)

    def remove_relationship(
        self,
        context: AuthContext,
        relationship_id: str,
    ) -> bool:
        """Soft-remove a relationship by deactivating it."""
        if not isinstance(relationship_id, str) or not relationship_id.strip():
            raise ValueError("relationship_id is required")
        clean_id = relationship_id.strip()

        existing = self.api.repository.get_relationship(clean_id)
        if existing is None:
            raise KeyError(f"relationship not found: {clean_id}")

        self._get_and_authorize_memory(context, existing.source_memory_id, "source")
        self._get_and_authorize_memory(context, existing.target_memory_id, "target")

        return self.api.repository.remove_relationship(clean_id)

    delete_relationship = remove_relationship

    def traverse(
        self,
        context: AuthContext,
        start_memory_id: str,
        max_depth: int = 2,
        relationship_types: Optional[Sequence[str | RelationshipType]] = None,
        direction: str = "outgoing",
        limit: int = 20,
    ) -> TraversalResult:
        """Deterministic, cycle-safe, bounded breadth-first traversal over memory relationships."""
        if not isinstance(start_memory_id, str) or not start_memory_id.strip():
            raise ValueError("start_memory_id is required")
        clean_start_id = start_memory_id.strip()

        if max_depth < 1:
            raise ValueError(f"max_depth must be at least 1, got {max_depth}")
        effective_max_depth = min(max_depth, 10)

        if direction not in ("outgoing", "incoming", "both"):
            raise ValueError(f"invalid direction: {direction}. Must be 'outgoing', 'incoming', or 'both'")

        type_filter: Optional[set[RelationshipType]] = None
        if relationship_types:
            type_filter = {self._normalize_type(item) for item in relationship_types}

        start_record = self._get_and_authorize_memory(context, clean_start_id, "start")

        visited_memories: set[str] = {clean_start_id}
        visited_relationships: set[str] = set()
        steps: list[TraversalStep] = []

        # Queue contains: (current_memory_id, current_depth)
        queue: deque[tuple[str, int]] = deque([(clean_start_id, 0)])

        while queue and len(visited_memories) < max(1, limit):
            curr_id, curr_depth = queue.popleft()
            if curr_depth >= effective_max_depth:
                continue

            # Fetch candidate relationships connected to curr_id
            if direction == "outgoing":
                candidates = self.api.repository.get_relationships(
                    source_id=curr_id,
                    active_only=True,
                )
            elif direction == "incoming":
                candidates = self.api.repository.get_relationships(
                    target_id=curr_id,
                    active_only=True,
                )
            else:
                candidates = self.api.repository.get_relationships(
                    memory_id=curr_id,
                    active_only=True,
                )

            if type_filter is not None:
                candidates = [rel for rel in candidates if rel.relationship_type in type_filter]

            # Deterministic edge sorting: strength descending, type ascending, target ascending, ID ascending
            candidates.sort(
                key=lambda rel: (
                    -rel.strength,
                    rel.relationship_type.value,
                    rel.target_memory_id,
                    rel.relationship_id,
                )
            )

            for rel in candidates:
                if rel.relationship_id in visited_relationships:
                    continue

                neighbor_id = (
                    rel.target_memory_id if rel.source_memory_id == curr_id else rel.source_memory_id
                )

                # Cycle-safe: skip already visited memories
                if neighbor_id in visited_memories:
                    continue

                # Validate neighbor existence and authorization
                neighbor_record = self.api.repository.get(neighbor_id)
                if neighbor_record is None or not neighbor_record.active:
                    continue
                try:
                    authorize(
                        context,
                        neighbor_record.domain,
                        neighbor_record.session_id,
                        neighbor_record,
                    )
                except MemoryAuthorizationError:
                    # Caller cannot access neighbor, do not traverse into it
                    continue

                visited_memories.add(neighbor_id)
                visited_relationships.add(rel.relationship_id)

                step = TraversalStep(
                    memory_id=neighbor_id,
                    depth=curr_depth + 1,
                    relationship=rel,
                    memory=neighbor_record,
                )
                steps.append(step)

                if len(visited_memories) >= limit:
                    break

                if curr_depth + 1 < effective_max_depth:
                    queue.append((neighbor_id, curr_depth + 1))

        return TraversalResult(
            start_memory_id=clean_start_id,
            start_memory=start_record,
            steps=steps,
        )
