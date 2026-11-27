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
import base64
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

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

    @property
    def memory_status(self) -> str:
        """Return runtime memory availability ('healthy' or 'degraded')."""
        return "healthy"

    def validate_startup(self) -> None:
        """Perform startup configuration and connectivity validation."""
        return None

    def check_readiness(self) -> Tuple[bool, Dict[str, Any]]:
        """Check dependency readiness without raising into HTTP handlers."""
        return True, {"memory_status": self.memory_status}


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

    def check_readiness(self) -> Tuple[bool, Dict[str, Any]]:
        """Report intentional stateless isolation without claiming live DB failure."""
        return True, {
            "memory_status": "disabled",
            "memory_mode": self.mode.value,
            "memory_enabled": False,
        }


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


def _is_production_environment() -> bool:
    """Return True when executing in a deployed production/staging/Render environment."""
    env = os.getenv("ENVIRONMENT", "").strip().lower()
    return (
        env in {"production", "prod", "staging"}
        or os.getenv("RENDER", "").strip().lower() == "true"
    )


def _warn_if_anon_supabase_key(key: str) -> None:
    """Safely warn when SUPABASE_KEY looks like an anon JWT without ever logging any secret."""
    parts = key.split(".")
    if len(parts) != 3:
        return
    try:
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        decoded = base64.urlsafe_b64decode(payload_b64.encode("ascii"))
        claims = json.loads(decoded.decode("utf-8"))
        role = str(claims.get("role", "")).strip().lower()
        if role and role != "service_role":
            logger.warning(
                "SUPABASE_KEY appears to use JWT role='%s'; public.memories has RLS enabled with 0 policies "
                "and requires the server-side service_role key.",
                role,
            )
    except Exception:
        return


def _log_zero_rows_warning(owner_id: str, *, context: str) -> None:
    """Emit a privacy-safe warning explaining possible causes of a zero-row memory query."""
    logger.warning(
        "MARK-I Supabase memory query returned 0 rows (context=%s owner_id_queried=%s). "
        "Possible causes: (1) incorrect SUPABASE_KEY configuration, "
        "(2) anon/public key used instead of service_role key with RLS enabled, "
        "(3) VENNELA_BOSS_ID mismatch with existing owner_id values in public.memories, "
        "(4) incorrect provider or memory configuration, or "
        "(5) an actually empty result set.",
        context,
        owner_id,
    )


class TemporaryMarkIMemoryProvider(MemorySubsystemInterface):
    """Temporary operational memory provider adapting MARK-I memory to Brain B.

    Features:
    - Bounded stable memory retrieval (Profile, Preference, Goal, Project).
    - Semantic memory retrieval via IntelligentMemory.
    - Session-scoped short-term memory retrieval/storage when session_id is supplied.
    - Conversation turn persistence & deduplication via SmartMemory.
    - Strict AuthContext user and session isolation enforcing ownership on all operations.
    - Fail-fast production startup validation with explicit Supabase timeouts and
      lightweight connectivity probe (never silently falling back to volatile memory).
    - Controlled degraded-mode stateless Brain B operation with automatic recovery.
    """

    def __init__(self, api_factory: Optional[Callable[[], Any]] = None):
        self._api_factory = api_factory
        self._api_instance: Optional[Any] = None
        self._state_lock = threading.Lock()
        self._probe_lock = threading.Lock()
        self._status: str = "healthy"
        self._last_error: Optional[str] = None

    @property
    def mode(self) -> MemoryIsolationMode:
        return MemoryIsolationMode.MARK_I_TEMPORARY

    @property
    def memory_status(self) -> str:
        with self._state_lock:
            return self._status

    def _mark_healthy(self) -> None:
        with self._state_lock:
            self._status = "healthy"
            self._last_error = None

    def _mark_degraded(self, err: BaseException) -> None:
        with self._state_lock:
            self._status = "degraded"
            self._last_error = type(err).__name__

    def _get_api(self) -> Any:
        with self._state_lock:
            cached = self._api_instance
        if cached is not None:
            return cached

        factory = self._api_factory or self._default_api_factory
        api = factory()
        with self._state_lock:
            if self._api_instance is None:
                self._api_instance = api
            return self._api_instance

    @staticmethod
    def _default_api_factory() -> Any:
        from memory.api import MemoryAPI
        from memory.repository import InMemoryMemoryRepository, SupabaseMemoryRepository

        url = os.getenv("SUPABASE_URL", "").strip()
        key = os.getenv("SUPABASE_KEY", "").strip()
        if url and key:
            from supabase import ClientOptions, create_client

            _warn_if_anon_supabase_key(key)
            options = ClientOptions(
                postgrest_client_timeout=10,
                storage_client_timeout=10,
            )
            client = create_client(url, key, options=options)
            return MemoryAPI(SupabaseMemoryRepository(client))

        if _is_production_environment():
            msg = (
                "[P0-02 FATAL] SUPABASE_URL and SUPABASE_KEY are required when "
                "VENNELA_MEMORY_PROVIDER=mark_i in production/Render environments."
            )
            logger.critical(msg)
            raise RuntimeError(msg)

        logger.warning(
            "SUPABASE_URL/SUPABASE_KEY not configured in non-production environment; "
            "TemporaryMarkIMemoryProvider using InMemoryMemoryRepository"
        )
        return MemoryAPI(InMemoryMemoryRepository())

    def _probe_api(
        self,
        api: Any,
        *,
        owner_id: Optional[str] = None,
        verify_owner_query: bool = False,
    ) -> Dict[str, Any]:
        from memory.repository import InMemoryMemoryRepository, SupabaseMemoryRepository

        repo = getattr(api, "repository", None)
        if isinstance(repo, InMemoryMemoryRepository):
            if _is_production_environment() and self._api_factory is None:
                raise RuntimeError(
                    "[P0-02 FATAL] Volatile InMemoryMemoryRepository is prohibited in production."
                )
            if verify_owner_query and self._api_factory is None:
                raise RuntimeError(
                    "SUPABASE_URL and SUPABASE_KEY are required to verify live MARK-I memory readiness."
                )
            return {"memory_enabled": True, "owner_scoped": False}

        client = getattr(repo, "client", None)
        table_name = getattr(repo, "table_name", "memories")
        if client is not None and hasattr(client, "table"):
            resp = client.table(table_name).select("memory_id").limit(1).execute()
            SupabaseMemoryRepository._check(resp)

            details: Dict[str, Any] = {"memory_enabled": True, "owner_scoped": False}
            if verify_owner_query:
                effective_owner = (owner_id or os.getenv("VENNELA_BOSS_ID", "")).strip()
                if effective_owner:
                    owner_resp = (
                        client.table(table_name)
                        .select("memory_id")
                        .eq("owner_id", effective_owner)
                        .limit(1)
                        .execute()
                    )
                    owner_rows = SupabaseMemoryRepository._check(owner_resp)
                    owner_records_present = len(owner_rows) > 0
                    if not owner_records_present:
                        _log_zero_rows_warning(effective_owner, context="readiness_probe")
                    details["owner_scoped"] = True
                    details["owner_records_present"] = owner_records_present
            return details

        raise RuntimeError("Configured memory repository does not expose a Supabase client")

    def validate_startup(self) -> None:
        """Fail fast at startup if credentials are missing or connectivity probe fails."""
        with self._probe_lock:
            try:
                api = self._get_api()
                self._probe_api(api)
                self._mark_healthy()
            except Exception as exc:
                self._mark_degraded(exc)
                logger.critical(
                    "MARK-I startup validation/connectivity probe failed (%s)",
                    type(exc).__name__,
                )
                raise RuntimeError(
                    f"[P0-02 FATAL] MARK-I memory startup validation failed ({type(exc).__name__})."
                ) from exc

    def check_readiness(self, owner_id: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
        """Probe configured memory backend and update status without crashing /ready."""
        with self._probe_lock:
            try:
                api = self._get_api()
                probe_details = self._probe_api(
                    api,
                    owner_id=owner_id,
                    verify_owner_query=True,
                )
                self._mark_healthy()
                return True, {
                    "memory_status": "healthy",
                    "memory_mode": self.mode.value,
                    **probe_details,
                }
            except Exception as exc:
                self._mark_degraded(exc)
                logger.warning(
                    "MARK-I readiness probe failed (%s); reporting degraded status",
                    type(exc).__name__,
                )
                details: Dict[str, Any] = {
                    "memory_status": "degraded",
                    "memory_mode": self.mode.value,
                    "memory_enabled": True,
                    "error_type": type(exc).__name__,
                }
                if "SUPABASE_URL and SUPABASE_KEY are required" in str(exc) or "P0-02 FATAL" in str(exc):
                    details["reason"] = "missing_supabase_credentials"
                return False, details

    def retrieve(self, request: MemoryRetrievalRequest) -> MemoryRetrievalResponse:
        clean_user = _require_user_id(request.user_id, "TemporaryMarkIMemoryProvider.retrieve")
        started = time.perf_counter()
        request_id = (request.metadata or {}).get("request_id")

        try:
            from memory.intelligent import IntelligentMemory
            from memory.models import AuthContext, MemoryCategory, MemoryDomain

            api = self._get_api()
            repo = getattr(api, "repository", None)
            diag_fn = getattr(repo, "get_last_retrieval_diagnostics", None)

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
            personal_diag = diag_fn() if callable(diag_fn) else None
            if isinstance(personal_diag, dict):
                total_raw = int(personal_diag.get("raw_rows_fetched", len(all_personal)))
                total_valid = int(personal_diag.get("valid_rows_parsed", len(all_personal)))
                total_skipped = int(personal_diag.get("skipped_rows_count", 0))
            else:
                total_raw = len(all_personal)
                total_valid = len(all_personal)
                total_skipped = 0

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
                session_diag = diag_fn() if callable(diag_fn) else None
                if isinstance(session_diag, dict):
                    total_raw += int(session_diag.get("raw_rows_fetched", len(session_records)))
                    total_valid += int(session_diag.get("valid_rows_parsed", len(session_records)))
                    total_skipped += int(session_diag.get("skipped_rows_count", 0))
                else:
                    total_raw += len(session_records)
                    total_valid += len(session_records)
                for rec in session_records:
                    txt = _extract_record_text(rec)
                    if txt and txt.lower() not in seen_stable_texts:
                        seen_stable_texts.add(txt.lower())
                        session_texts.append(txt)

            if total_raw == 0:
                retrieval_status = "empty"
                _log_zero_rows_warning(clean_user, context="retrieve")
            elif total_skipped > 0 and total_valid > 0:
                retrieval_status = "partial_success"
            elif total_skipped > 0 and total_valid == 0:
                retrieval_status = "all_rows_invalid"
            else:
                retrieval_status = "success"

            diag_event: Dict[str, Any] = {
                "event": "mark_i_memory_retrieval",
                "provider": "TemporaryMarkIMemoryProvider",
                "owner_id_queried": clean_user,
                "raw_rows_fetched": total_raw,
                "valid_rows_parsed": total_valid,
                "skipped_rows_count": total_skipped,
                "status": retrieval_status,
            }
            if request_id is not None:
                diag_event["request_id"] = str(request_id)
            logger.info("mark_i_memory_retrieval %s", json.dumps(diag_event, sort_keys=True))

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

            self._mark_healthy()
            return MemoryRetrievalResponse(
                context_strings=context_lines,
                memory_count=len(stable_texts) + len(relevant_texts) + len(session_texts),
                mode=MemoryIsolationMode.MARK_I_TEMPORARY,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                metadata={
                    "stable_count": len(stable_texts),
                    "relevant_count": len(relevant_texts),
                    "session_count": len(session_texts),
                    "memory_status": "healthy",
                    "owner_id_queried": clean_user,
                    "raw_rows_fetched": total_raw,
                    "valid_rows_parsed": total_valid,
                    "skipped_rows_count": total_skipped,
                    "retrieval_status": retrieval_status,
                },
            )
        except Exception as ret_err:
            self._mark_degraded(ret_err)
            fail_event: Dict[str, Any] = {
                "event": "mark_i_memory_retrieval",
                "provider": "TemporaryMarkIMemoryProvider",
                "owner_id_queried": clean_user,
                "raw_rows_fetched": 0,
                "valid_rows_parsed": 0,
                "skipped_rows_count": 0,
                "status": "failed",
                "error_type": type(ret_err).__name__,
            }
            if request_id is not None:
                fail_event["request_id"] = str(request_id)
            logger.warning("mark_i_memory_retrieval %s", json.dumps(fail_event, sort_keys=True))
            return MemoryRetrievalResponse(
                context_strings=[],
                memory_count=0,
                mode=MemoryIsolationMode.MARK_I_TEMPORARY,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                metadata={
                    "error": type(ret_err).__name__,
                    "status": "retrieval_failed",
                    "memory_status": "degraded",
                    "owner_id_queried": clean_user,
                    "raw_rows_fetched": 0,
                    "valid_rows_parsed": 0,
                    "skipped_rows_count": 0,
                },
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

            self._mark_healthy()
            return stored_personal or stored_session
        except Exception as err:
            self._mark_degraded(err)
            logger.warning("MARK-I temporary memory store warning (%s)", type(err).__name__)
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
            self._mark_healthy()
            return True
        except Exception as err:
            if not isinstance(err, (KeyError, ValueError, PermissionError)):
                self._mark_degraded(err)
            logger.warning("MARK-I memory update warning (%s)", type(err).__name__)
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
            result = bool(api.forget(auth_context, memory_id.strip()))
            self._mark_healthy()
            return result
        except Exception as err:
            if not isinstance(err, (KeyError, ValueError, PermissionError)):
                self._mark_degraded(err)
            logger.warning("MARK-I memory delete warning (%s)", type(err).__name__)
            return False


_memory_subsystem_instance: Optional[MemorySubsystemInterface] = None
_memory_subsystem_lock = threading.Lock()

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
    3. In production/Render with 'mark_i', validate credentials and connectivity
       before caching or serving requests.
    """
    global _memory_subsystem_instance
    with _memory_subsystem_lock:
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
                candidate = TemporaryMarkIMemoryProvider()
                if _is_production_environment():
                    candidate.validate_startup()
                _memory_subsystem_instance = candidate
            else:
                _memory_subsystem_instance = StatelessMemoryProvider()

        return _memory_subsystem_instance


def reset_memory_subsystem() -> None:
    """Reset singleton for dynamic configuration changes and testing."""
    global _memory_subsystem_instance
    with _memory_subsystem_lock:
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
