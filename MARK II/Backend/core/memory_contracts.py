"""Memory contracts and stateless provider boundary for Vennela AI MARK-II.

Architecture & Isolation Rules:
1. Brain B remains the active reasoning engine.
2. Production runs strictly in STATELESS ISOLATION MODE until MARK-II
   Cognitive Memory completes independent development and validation.
3. Legacy MARK-I memory is completely decoupled and forbidden in MARK-II.
4. MARK-II Cognitive Memory (STM, MTM, LTM, Neural Schema, Secrets Vault)
   is gated and protected from premature production activation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MemoryIsolationMode(str, Enum):
    """Runtime memory execution mode."""

    STATELESS_ISOLATED = "STATELESS_ISOLATED"
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
        user_id: str,
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
    2. Zero connection or fallback to legacy MARK-I databases.
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


_memory_subsystem_instance: Optional[MemorySubsystemInterface] = None

# Strict provider allowlist
ALLOWED_MEMORY_PROVIDERS = {"stateless", "mark_ii"}


def get_memory_subsystem() -> MemorySubsystemInterface:
    """Factory returning the active memory subsystem based on strict configuration allowlist.

    Rules:
    1. VENNELA_MEMORY_PROVIDER must be in ALLOWED_MEMORY_PROVIDERS:
       - 'stateless' (default if unset or empty): returns StatelessMemoryProvider
       - 'mark_ii': BLOCKED (raises RuntimeError until Phase 4 independent validation passes)
       - Any other value (including 'mark_i', 'legacy', 'supabase'): raises ConfigurationError / ValueError
    2. VENNELA_MEMORY_ENABLED=true cannot implicitly activate legacy memory.
    """
    global _memory_subsystem_instance
    if _memory_subsystem_instance is None:
        raw_provider = os.getenv("VENNELA_MEMORY_PROVIDER", "").strip().lower()

        # Documented deterministic fallback when unset or empty
        if not raw_provider:
            logger.info("VENNELA_MEMORY_PROVIDER unset; defaulting deterministically to 'stateless'")
            raw_provider = "stateless"

        if raw_provider == "mark_i" or raw_provider == "legacy":
            raise ValueError(
                "[SEC-MEM-LEGACY-BLOCKED] Legacy MARK-I memory provider has been deprecated "
                "and permanently isolated from MARK-II. Legacy memory cannot be activated."
            )

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

        # raw_provider == "stateless"
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
    "get_memory_subsystem",
    "reset_memory_subsystem",
]
