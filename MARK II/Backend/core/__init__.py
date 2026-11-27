"""Core platform utilities and contracts for Vennela AI."""

from .intelligence_contracts import BrainResult, DelegationDecision, DelegationType
from .memory_contracts import (
    ALLOWED_MEMORY_PROVIDERS,
    MemoryIsolationMode,
    MemoryRetrievalRequest,
    MemoryRetrievalResponse,
    MemorySubsystemInterface,
    StatelessMemoryProvider,
    TemporaryMarkIMemoryProvider,
    classify_memory_error,
    get_memory_subsystem,
    reset_memory_subsystem,
    resolve_supabase_credentials,
)

__all__ = [
    "ALLOWED_MEMORY_PROVIDERS",
    "BrainResult",
    "DelegationDecision",
    "DelegationType",
    "MemoryIsolationMode",
    "MemoryRetrievalRequest",
    "MemoryRetrievalResponse",
    "MemorySubsystemInterface",
    "StatelessMemoryProvider",
    "TemporaryMarkIMemoryProvider",
    "classify_memory_error",
    "get_memory_subsystem",
    "reset_memory_subsystem",
    "resolve_supabase_credentials",
]
