"""Memory contracts and provider boundary for Vennela AI MARK-II.

Architecture & Isolation Rules:
1. Brain B remains the active reasoning engine.
2. Temporary MARK-I memory provides operational persistence and retrieval
   until MARK-II Cognitive Memory completes independent validation.
3. MARK-II Cognitive Memory (STM, MTM, LTM, Schema, Vault) remains independent
   and cannot be accidentally activated before completion.
4. Stateless isolation mode remains available as a zero-dependency fallback.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MemoryIsolationMode(str, Enum):
    """Runtime memory execution mode."""

    STATELESS_ISOLATED = "STATELESS_ISOLATED"
    MARK_I_TEMPORARY = "MARK_I_TEMPORARY"
    MARK_II_CONNECTED = "MARK_II_CONNECTED"


@dataclass(frozen=True)
class MemoryRetrievalRequest:
    """Request contract for memory retrieval across providers."""

    query: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    limit: int = 5
    enable_stm: bool = False
    enable_mtm: bool = False
    enable_ltm: bool = False
    enable_neural_schema: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryRetrievalResponse:
    """Normalized response contract from memory subsystem."""

    context_strings: List[str] = field(default_factory=list)
    memory_count: int = 0
    mode: MemoryIsolationMode = MemoryIsolationMode.STATELESS_ISOLATED
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class MemorySubsystemInterface(ABC):
    """Abstract interface that every memory provider must satisfy.

    The future MARK-II Memory Layer (with Supabase JSONB STM, temporal MTM,
    hybrid LTM, Neural Schema, and Secrets Vault) will implement this interface.
    """

    @abstractmethod
    def retrieve(self, request: MemoryRetrievalRequest) -> MemoryRetrievalResponse:
        """Retrieve relevant context strings without leaking cross-user state."""
        pass

    @abstractmethod
    def store(
        self,
        text: str,
        *,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Store conversation turn into durable memory (no-op in stateless mode)."""
        pass

    @property
    @abstractmethod
    def mode(self) -> MemoryIsolationMode:
        """Return the active isolation mode."""
        pass


class StatelessMemoryProvider(MemorySubsystemInterface):
    """Explicitly isolated stateless provider for Brain B.

    Guarantees:
    1. Zero integration with unfinished MARK-II code paths.
    2. Zero connection or fallback to legacy databases.
    3. No fake/synthetic memory generation.
    4. Deterministic no-op behavior with zero latency and zero external I/O.
    """

    def retrieve(self, request: MemoryRetrievalRequest) -> MemoryRetrievalResponse:
        return MemoryRetrievalResponse(
            context_strings=[],
            memory_count=0,
            mode=MemoryIsolationMode.STATELESS_ISOLATED,
            duration_ms=0.0,
            metadata={"status": "memory_disabled_stateless_mode"},
        )

    def store(
        self,
        text: str,
        *,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        return False

    @property
    def mode(self) -> MemoryIsolationMode:
        return MemoryIsolationMode.STATELESS_ISOLATED


class TemporaryMarkIMemoryProvider(MemorySubsystemInterface):
    """Temporary operational memory provider adapting MARK-I memory to Brain B.

    Features:
    - Bounded stable memory retrieval (Profile, Preference, Goal, Project).
    - Semantic memory retrieval via IntelligentMemory.
    - Conversation turn persistence via SmartMemory.
    - Strict AuthContext user-isolation enforcing ownership.
    - Graceful degradation if Supabase is unreachable or unconfigured.
    """

    def __init__(self, api_factory: Optional[Callable[[], Any]] = None):
        self._api_factory = api_factory

    @property
    def mode(self) -> MemoryIsolationMode:
        return MemoryIsolationMode.MARK_I_TEMPORARY

    def _get_api(self) -> Any:
        if self._api_factory is not None:
            return self._api_factory()
        url = os.getenv("SUPABASE_URL", "").strip()
        key = os.getenv("SUPABASE_KEY", "").strip()
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required for MARK-I memory")
        from supabase import create_client
        from memory.api import MemoryAPI
        from memory.repository import SupabaseMemoryRepository
        return MemoryAPI(SupabaseMemoryRepository(create_client(url, key)))

    def retrieve(self, request: MemoryRetrievalRequest) -> MemoryRetrievalResponse:
        started = time.perf_counter()
        user_id = (request.user_id or "").strip()
        if not user_id:
            user_id = os.getenv("VENNELA_BOSS_ID", "").strip() or "boss_user"

        from memory.models import AuthContext
        auth_context = AuthContext(
            user_id=user_id,
            authenticated=True,
            session_id=request.session_id,
        )

        try:
            api = self._get_api()
        except Exception as conn_err:
            logger.warning("MARK-I memory connection unavailable: %s", conn_err)
            return MemoryRetrievalResponse(
                context_strings=[],
                memory_count=0,
                mode=MemoryIsolationMode.MARK_I_TEMPORARY,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                metadata={"error": str(conn_err), "status": "connection_unavailable"},
            )

        try:
            from memory.intelligent import IntelligentMemory
            from memory.models import MemoryCategory, MemoryDomain

            # 1. Retrieve stable profile / preference records
            stable_categories = (
                MemoryCategory.PROFILE,
                MemoryCategory.PREFERENCE,
                MemoryCategory.INTEREST,
                MemoryCategory.GOAL,
                MemoryCategory.PROJECT,
            )
            raw_records = api.retrieve(
                auth_context,
                MemoryDomain.BOSS_PERSONAL.value,
                limit=100,
            )
            active_records = [
                r for r in raw_records
                if getattr(r, "active", False)
                and r.category in stable_categories
                and not (
                    isinstance(r.content, dict)
                    and r.content.get("lifecycle_state") in {"SUPERSEDED", "OBSOLETE", "INACTIVE"}
                )
            ]
            stable_selected = []
            for cat in stable_categories:
                cat_records = [r for r in active_records if r.category is cat]
                cat_records.sort(key=lambda r: -getattr(r.updated_at, "timestamp", lambda: 0)())
                stable_selected.extend(cat_records[:3])
                if len(stable_selected) >= 12:
                    break

            # 2. Semantic query-relevant retrieval
            semantic_records = []
            try:
                scored = IntelligentMemory(api).retrieve_semantic(
                    auth_context,
                    request.query,
                    session_id=request.session_id,
                    limit=request.limit or 5,
                    min_similarity=0.05,
                )
                semantic_records = [item.record for item in scored]
            except Exception as sem_err:
                logger.warning("MARK-I semantic retrieval warning: %s", sem_err)

            # 3. Format lines
            def _extract_text(rec):
                c = rec.content
                if isinstance(c, dict):
                    c = c.get("text", c.get("content", ""))
                return c.strip() if isinstance(c, str) else ""

            stable_ids = {r.memory_id for r in stable_selected}
            stable_texts = [_extract_text(r) for r in stable_selected if _extract_text(r)]
            relevant_texts = [
                _extract_text(r)
                for r in semantic_records
                if r.memory_id not in stable_ids and _extract_text(r)
            ]

            context_lines = []
            if stable_texts:
                context_lines.append("Stable user context:")
                for t in stable_texts:
                    context_lines.append(f"- {t}")
            if relevant_texts:
                context_lines.append("Query-relevant memories:")
                for t in relevant_texts:
                    context_lines.append(f"- {t}")

            return MemoryRetrievalResponse(
                context_strings=context_lines,
                memory_count=len(stable_texts) + len(relevant_texts),
                mode=MemoryIsolationMode.MARK_I_TEMPORARY,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                metadata={
                    "stable_count": len(stable_texts),
                    "relevant_count": len(relevant_texts),
                },
            )
        except Exception as ret_err:
            logger.warning("MARK-I memory retrieval failed: %s", ret_err)
            return MemoryRetrievalResponse(
                context_strings=[],
                memory_count=0,
                mode=MemoryIsolationMode.MARK_I_TEMPORARY,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                metadata={"error": str(ret_err), "status": "retrieval_failed"},
            )

    def store(
        self,
        text: str,
        *,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if not text or not text.strip():
            return False
        clean_user = (user_id or "").strip() or os.getenv("VENNELA_BOSS_ID", "").strip() or "boss_user"
        from memory.models import AuthContext
        auth_context = AuthContext(user_id=clean_user, authenticated=True, session_id=session_id)
        try:
            api = self._get_api()
            from memory.smart import SmartMemory
            from memory.models import MemoryDomain
            # BOSS_PERSONAL domain stores persistent user facts (session_id must be None per MemoryAPI contract)
            decision = SmartMemory(api).store(
                auth_context,
                text.strip(),
                domain=MemoryDomain.BOSS_PERSONAL.value,
                session_id=None,
            )
            return decision.action in {"create", "update"}
        except Exception as err:
            logger.warning("MARK-I temporary memory store warning: %s", err)
            return False


_memory_subsystem_instance: Optional[MemorySubsystemInterface] = None


def get_memory_subsystem() -> MemorySubsystemInterface:
    """Factory returning the active memory subsystem based on configuration.

    Selection precedence:
    1. VENNELA_MEMORY_PROVIDER:
       - 'stateless': StatelessMemoryProvider
       - 'mark_i': TemporaryMarkIMemoryProvider
       - 'mark_ii': BLOCKED (raises RuntimeError to protect unvalidated MARK-II components)
    2. VENNELA_MEMORY_ENABLED flag:
       - 'true': TemporaryMarkIMemoryProvider
       - 'false': StatelessMemoryProvider
    Default: StatelessMemoryProvider
    """
    global _memory_subsystem_instance
    if _memory_subsystem_instance is None:
        provider_type = os.getenv("VENNELA_MEMORY_PROVIDER", "").strip().lower()
        enabled = os.getenv("VENNELA_MEMORY_ENABLED", "false").strip().lower() == "true"

        if provider_type == "mark_ii":
            raise RuntimeError(
                "[DEVSECOPS BLOCK] MARK-II Cognitive Memory Architecture is currently under "
                "independent development and validation. Direct production activation is blocked "
                "until Phase 4 independent validation passes."
            )

        if provider_type == "mark_i" or (not provider_type and enabled):
            logger.info("Initializing Temporary MARK-I Memory Provider for Brain B")
            _memory_subsystem_instance = TemporaryMarkIMemoryProvider()
        else:
            logger.info("Initializing Stateless Memory Provider (isolated mode)")
            _memory_subsystem_instance = StatelessMemoryProvider()

    return _memory_subsystem_instance


def reset_memory_subsystem() -> None:
    """Reset singleton for dynamic configuration changes and testing."""
    global _memory_subsystem_instance
    _memory_subsystem_instance = None


__all__ = [
    "MemoryIsolationMode",
    "MemoryRetrievalRequest",
    "MemoryRetrievalResponse",
    "MemorySubsystemInterface",
    "StatelessMemoryProvider",
    "TemporaryMarkIMemoryProvider",
    "get_memory_subsystem",
    "reset_memory_subsystem",
]
