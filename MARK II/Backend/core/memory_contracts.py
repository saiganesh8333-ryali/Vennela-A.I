"""Memory contracts and provider boundary for Vennela AI MARK-II.

Architecture & Isolation Rules:
1. Brain B (ProductionLangGraphBrain) is the sole active reasoning engine.
2. Temporary MARK-I memory (TemporaryMarkIMemoryProvider) provides operational
   persistence and retrieval until MARK-II Cognitive Memory completes validation.
3. MARK-II Cognitive Memory (STM, MTM, LTM, Neural Schema, Secrets Vault)
   remains paused and protected from premature production activation.
4. Stateless isolation mode (StatelessMemoryProvider) remains available as a
   zero-dependency fallback.
5. Every memory operation fails closed if authenticated user_id is missing.
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
    user_id: str
    session_id: Optional[str] = None
    limit: int = 5
    enable_stm: bool = False
    enable_mtm: bool = False
    enable_ltm: bool = False
    enable_neural_schema: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.user_id or not self.user_id.strip():
            raise ValueError(
                "[SEC-ID-01] Missing authenticated user_id in MemoryRetrievalRequest. "
                "Memory requests must fail closed."
            )


@dataclass(frozen=True)
class MemoryRetrievalResponse:
    """Normalized response contract from memory subsystem."""

    context_strings: List[str] = field(default_factory=list)
    memory_count: int = 0
    mode: MemoryIsolationMode = MemoryIsolationMode.STATELESS_ISOLATED
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class MemorySubsystemInterface(ABC):
    """Abstract interface that every memory provider must satisfy."""

    @abstractmethod
    def retrieve(self, request: MemoryRetrievalRequest) -> MemoryRetrievalResponse:
        """Retrieve relevant context strings without leaking cross-user state."""
        pass

    @abstractmethod
    def store(
        self,
        text: str,
        *,
        user_id: str,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Store conversation turn into durable memory (no-op in stateless mode)."""
        pass

    def update(
        self,
        memory_id: str,
        content: Any,
        *,
        user_id: str,
        session_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> bool:
        """Update an existing memory record (no-op in stateless mode)."""
        if not user_id or not user_id.strip():
            raise ValueError(
                "[SEC-ID-01] Missing authenticated user_id in MemorySubsystemInterface.update."
            )
        return False

    def delete(
        self,
        memory_id: str,
        *,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> bool:
        """Delete/forget an existing memory record (no-op in stateless mode)."""
        if not user_id or not user_id.strip():
            raise ValueError(
                "[SEC-ID-01] Missing authenticated user_id in MemorySubsystemInterface.delete."
            )
        return False

    @property
    @abstractmethod
    def mode(self) -> MemoryIsolationMode:
        """Return the active isolation mode."""
        pass


class StatelessMemoryProvider(MemorySubsystemInterface):
    """Explicitly isolated stateless provider for Brain B.

    Guarantees:
    1. Zero integration with unfinished MARK-II code paths.
    2. Zero connection or fallback to MARK-I databases.
    3. No fake/synthetic memory generation.
    4. Deterministic no-op behavior with zero latency and zero external I/O.
    5. Fails closed if user_id is missing or empty.
    """

    def retrieve(self, request: MemoryRetrievalRequest) -> MemoryRetrievalResponse:
        if not request.user_id or not request.user_id.strip():
            raise ValueError(
                "[SEC-ID-01] Missing authenticated user_id in MemoryRetrievalRequest."
            )
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
        user_id: str,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if not user_id or not user_id.strip():
            raise ValueError(
                "[SEC-ID-01] Missing authenticated user_id in MemorySubsystemInterface.store."
            )
        return False

    @property
    def mode(self) -> MemoryIsolationMode:
        return MemoryIsolationMode.STATELESS_ISOLATED


def _extract_record_text(record: Any) -> str:
    content = getattr(record, "content", None)
    if isinstance(content, dict):
        return str(content.get("text", content.get("content", ""))).strip()
    if isinstance(content, str):
        return content.strip()
    return ""


def _require_user_id(user_id: Optional[str], operation: str) -> str:
    clean = (user_id or "").strip()
    if not clean:
        raise ValueError(
            f"[SEC-ID-01] Missing authenticated user_id in {operation}. "
            "Memory operations must fail closed."
        )
    return clean


class TemporaryMarkIMemoryProvider(MemorySubsystemInterface):
    """Temporary operational memory provider adapting MARK-I memory to Brain B.

    Features:
    - Bounded stable memory retrieval (Profile, Preference, Goal, Project).
    - Semantic memory retrieval via IntelligentMemory.
    - Session-scoped short-term memory retrieval/storage when session_id is supplied.
    - Conversation turn persistence & deduplication via SmartMemory.
    - Strict AuthContext user and session isolation enforcing ownership on all operations.
    - Graceful degradation if Supabase is unreachable or unconfigured.
    """

    def __init__(self, api_factory: Optional[Callable[[], Any]] = None):
        self._api_factory = api_factory
        self._api_instance: Optional[Any] = None

    @property
    def mode(self) -> MemoryIsolationMode:
        return MemoryIsolationMode.MARK_I_TEMPORARY

    def _get_api(self) -> Any:
        if self._api_instance is None:
            if self._api_factory is not None:
                self._api_instance = self._api_factory()
            else:
                self._api_instance = self._default_api_factory()
        return self._api_instance

    @staticmethod
    def _default_api_factory() -> Any:
        from memory.api import MemoryAPI
        from memory.repository import InMemoryMemoryRepository, SupabaseMemoryRepository

        url = os.getenv("SUPABASE_URL", "").strip()
        key = os.getenv("SUPABASE_KEY", "").strip()
        if url and key:
            from supabase import create_client

            return MemoryAPI(SupabaseMemoryRepository(create_client(url, key)))
        logger.warning(
            "SUPABASE_URL/SUPABASE_KEY not configured; TemporaryMarkIMemoryProvider using InMemoryMemoryRepository"
        )
        return MemoryAPI(InMemoryMemoryRepository())

    def retrieve(self, request: MemoryRetrievalRequest) -> MemoryRetrievalResponse:
        clean_user = _require_user_id(request.user_id, "TemporaryMarkIMemoryProvider.retrieve")
        started = time.perf_counter()

        try:
            from memory.intelligent import IntelligentMemory
            from memory.models import AuthContext, MemoryCategory, MemoryDomain

            api = self._get_api()
            auth_context = AuthContext(
                user_id=clean_user,
                authenticated=True,
                session_id=request.session_id,
            )

            all_personal = api.retrieve(
                auth_context,
                domain=MemoryDomain.BOSS_PERSONAL.value,
                session_id=None,
                limit=50,
            )

            stable_categories = {
                MemoryCategory.PROFILE,
                MemoryCategory.PREFERENCE,
                MemoryCategory.GOAL,
                MemoryCategory.PROJECT,
            }
            stable_records = []
            seen_stable_texts: set[str] = set()
            for rec in all_personal:
                if rec.category in stable_categories:
                    txt = _extract_record_text(rec)
                    norm = txt.lower()
                    if txt and norm not in seen_stable_texts:
                        seen_stable_texts.add(norm)
                        stable_records.append(rec)
                if len(stable_records) >= 5:
                    break

            stable_ids = {r.memory_id for r in stable_records}
            stable_texts = [_extract_record_text(r) for r in stable_records if _extract_record_text(r)]

            semantic_limit = max(1, min(request.limit, 10))
            scored = IntelligentMemory(api).rank(
                auth_context,
                request.query,
                all_personal,
                session_id=request.session_id,
            )
            relevant_texts: List[str] = []
            for item in scored:
                rec = item.record
                if rec.memory_id in stable_ids:
                    continue
                txt = _extract_record_text(rec)
                if txt and txt.lower() not in seen_stable_texts:
                    seen_stable_texts.add(txt.lower())
                    relevant_texts.append(txt)
                if len(relevant_texts) >= semantic_limit:
                    break

            session_texts: List[str] = []
            if request.session_id and request.session_id.strip():
                session_records = api.retrieve(
                    auth_context,
                    domain=MemoryDomain.SESSION.value,
                    session_id=request.session_id.strip(),
                    query=request.query,
                    limit=max(1, min(request.limit, 5)),
                )
                for rec in session_records:
                    txt = _extract_record_text(rec)
                    if txt and txt.lower() not in seen_stable_texts:
                        seen_stable_texts.add(txt.lower())
                        session_texts.append(txt)

            context_lines: List[str] = []
            if stable_texts:
                context_lines.append("Stable user context:")
                for t in stable_texts:
                    context_lines.append(f"- {t}")
            if relevant_texts:
                context_lines.append("Query-relevant memories:")
                for t in relevant_texts:
                    context_lines.append(f"- {t}")
            if session_texts:
                context_lines.append("Session context:")
                for t in session_texts:
                    context_lines.append(f"- {t}")

            return MemoryRetrievalResponse(
                context_strings=context_lines,
                memory_count=len(stable_texts) + len(relevant_texts) + len(session_texts),
                mode=MemoryIsolationMode.MARK_I_TEMPORARY,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                metadata={
                    "stable_count": len(stable_texts),
                    "relevant_count": len(relevant_texts),
                    "session_count": len(session_texts),
                },
            )
        except Exception as ret_err:
            logger.warning("MARK-I memory retrieval failed (%s): %s", type(ret_err).__name__, ret_err)
            return MemoryRetrievalResponse(
                context_strings=[],
                memory_count=0,
                mode=MemoryIsolationMode.MARK_I_TEMPORARY,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                metadata={"error": type(ret_err).__name__, "status": "retrieval_failed"},
            )

    def store(
        self,
        text: str,
        *,
        user_id: str,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        clean_user = _require_user_id(user_id, "TemporaryMarkIMemoryProvider.store")
        if not text or not text.strip():
            return False

        clean_text = text.strip()
        clean_session = session_id.strip() if isinstance(session_id, str) and session_id.strip() else None

        try:
            from memory.models import AuthContext, MemoryCategory, MemoryDomain
            from memory.smart import SmartMemory

            api = self._get_api()
            auth_context = AuthContext(
                user_id=clean_user,
                authenticated=True,
                session_id=clean_session,
            )

            decision = SmartMemory(api).store(
                auth_context,
                clean_text,
                domain=MemoryDomain.BOSS_PERSONAL.value,
                session_id=None,
            )
            stored_personal = decision.action in {"create", "update"}

            stored_session = False
            store_session = bool((metadata or {}).get("store_session"))
            if clean_session and store_session:
                existing_session = api.retrieve(
                    auth_context,
                    domain=MemoryDomain.SESSION.value,
                    session_id=clean_session,
                    limit=20,
                )
                normalized = clean_text.lower()
                if not any(_extract_record_text(r).lower() == normalized for r in existing_session):
                    api.create(
                        auth_context,
                        {"text": clean_text, "metadata": dict(metadata or {})},
                        category=MemoryCategory.EVENT.value,
                        domain=MemoryDomain.SESSION.value,
                        session_id=clean_session,
                    )
                    stored_session = True

            return stored_personal or stored_session
        except Exception as err:
            logger.warning("MARK-I temporary memory store warning (%s): %s", type(err).__name__, err)
            return False

    def update(
        self,
        memory_id: str,
        content: Any,
        *,
        user_id: str,
        session_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> bool:
        clean_user = _require_user_id(user_id, "TemporaryMarkIMemoryProvider.update")
        if not memory_id or not memory_id.strip():
            return False
        clean_session = session_id.strip() if isinstance(session_id, str) and session_id.strip() else None
        try:
            from memory.models import AuthContext

            api = self._get_api()
            auth_context = AuthContext(
                user_id=clean_user,
                authenticated=True,
                session_id=clean_session,
            )
            api.update(auth_context, memory_id.strip(), content, category=category)
            return True
        except Exception as err:
            logger.warning("MARK-I memory update warning (%s): %s", type(err).__name__, err)
            return False

    def delete(
        self,
        memory_id: str,
        *,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> bool:
        clean_user = _require_user_id(user_id, "TemporaryMarkIMemoryProvider.delete")
        if not memory_id or not memory_id.strip():
            return False
        clean_session = session_id.strip() if isinstance(session_id, str) and session_id.strip() else None
        try:
            from memory.models import AuthContext

            api = self._get_api()
            auth_context = AuthContext(
                user_id=clean_user,
                authenticated=True,
                session_id=clean_session,
            )
            return bool(api.forget(auth_context, memory_id.strip()))
        except Exception as err:
            logger.warning("MARK-I memory delete warning (%s): %s", type(err).__name__, err)
            return False


_memory_subsystem_instance: Optional[MemorySubsystemInterface] = None

# Strict provider allowlist
ALLOWED_MEMORY_PROVIDERS = {"stateless", "mark_i", "mark_ii"}


def get_memory_subsystem() -> MemorySubsystemInterface:
    """Factory returning the active memory subsystem based on strict configuration allowlist.

    Rules:
    1. VENNELA_MEMORY_PROVIDER must be in ALLOWED_MEMORY_PROVIDERS when set:
       - 'mark_i': TemporaryMarkIMemoryProvider
       - 'stateless': StatelessMemoryProvider
       - 'mark_ii': BLOCKED (raises RuntimeError until Phase 4 independent validation passes)
       - Any other value (including 'legacy', 'supabase'): raises ValueError
    2. When VENNELA_MEMORY_PROVIDER is unset:
       - If VENNELA_MEMORY_ENABLED=true -> TemporaryMarkIMemoryProvider
       - Otherwise -> StatelessMemoryProvider
    """
    global _memory_subsystem_instance
    if _memory_subsystem_instance is None:
        raw_provider = os.getenv("VENNELA_MEMORY_PROVIDER", "").strip().lower()
        memory_enabled = os.getenv("VENNELA_MEMORY_ENABLED", "false").strip().lower() == "true"

        if not raw_provider:
            if memory_enabled:
                logger.info("VENNELA_MEMORY_ENABLED=true with unset provider; activating 'mark_i'")
                raw_provider = "mark_i"
            else:
                logger.info("VENNELA_MEMORY_PROVIDER unset; defaulting deterministically to 'stateless'")
                raw_provider = "stateless"

        if raw_provider not in ALLOWED_MEMORY_PROVIDERS:
            raise ValueError(
                f"[SEC-MEM-INVALID-PROVIDER] Unknown memory provider '{raw_provider}'. "
                f"Strict allowlist: {sorted(list(ALLOWED_MEMORY_PROVIDERS))}."
            )

        if raw_provider == "mark_ii":
            raise RuntimeError(
                "[DEVSECOPS BLOCK] MARK-II Cognitive Memory Architecture is currently under "
                "independent development and validation. Direct production activation is blocked "
                "until Phase 4 independent validation passes."
            )

        if raw_provider == "mark_i":
            logger.info("Initializing Temporary MARK-I Memory Provider for Brain B")
            _memory_subsystem_instance = TemporaryMarkIMemoryProvider()
        else:
            _memory_subsystem_instance = StatelessMemoryProvider()

    return _memory_subsystem_instance


def reset_memory_subsystem() -> None:
    """Reset singleton for dynamic configuration changes and testing."""
    global _memory_subsystem_instance
    _memory_subsystem_instance = None


__all__ = [
    "ALLOWED_MEMORY_PROVIDERS",
    "MemoryIsolationMode",
    "MemoryRetrievalRequest",
    "MemoryRetrievalResponse",
    "MemorySubsystemInterface",
    "StatelessMemoryProvider",
    "TemporaryMarkIMemoryProvider",
    "get_memory_subsystem",
    "reset_memory_subsystem",
]
