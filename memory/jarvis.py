"""Unified JARVIS / FRIDAY Memory Intelligence Layer (Level 6)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from .api import MemoryAPI
from .intelligent import IntelligentMemory
from .lifecycle import MemoryLifecycleManager
from .models import (
    AuthContext,
    MemoryCategory,
    MemoryDomain,
    MemoryLifecycleState,
    MemoryRecord,
    PreferenceEvolutionResult,
    ProactiveRecallResult,
    UserModel,
)
from .preferences import PreferenceEvolutionEngine
from .proactive import ProactiveRecallEngine, ProactiveRecallPolicy
from .relational import RelationalMemory
from .user_model import UserModelEngine


class JarvisMemory:
    """Master coordinator for Level 6 JARVIS Memory Intelligence.

    Combines:
    - Proactive Recall with Anti-Spam Policy
    - Non-destructive Preference Evolution
    - Deterministic Memory Lifecycle & Obsolescence Management
    - Coherent Derived User Model
    """

    def __init__(
        self,
        api: MemoryAPI,
        relational: Optional[RelationalMemory] = None,
        intelligent: Optional[IntelligentMemory] = None,
        policy: Optional[ProactiveRecallPolicy] = None,
    ):
        self.api = api
        self.relational = relational or RelationalMemory(api)
        self.intelligent = intelligent or IntelligentMemory(api, relational=self.relational)
        self.policy = policy or ProactiveRecallPolicy()

        self.proactive = ProactiveRecallEngine(self.api, self.intelligent, self.policy)
        self.preferences = PreferenceEvolutionEngine(self.api, self.intelligent)
        self.lifecycle = MemoryLifecycleManager(self.api)
        self.user_model = UserModelEngine(self.api, self.relational)

    def proactive_recall(
        self,
        context: AuthContext,
        current_context: str,
        domain: str = MemoryDomain.BOSS_PERSONAL.value,
        session_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> ProactiveRecallResult:
        """Surfaces memories proactively if context, importance, and anti-spam policy justify it."""
        return self.proactive.recall(context, current_context, domain, session_id, now)

    def clear_cooldown(self, user_id: Optional[str] = None) -> None:
        """Clear anti-spam cooldown tracking for tests or session resets."""
        self.proactive.clear_cooldown(user_id)

    def evolve_preference(
        self,
        context: AuthContext,
        new_preference_text: str,
        topic: Optional[str] = None,
        importance: float = 0.80,
    ) -> PreferenceEvolutionResult:
        """Evolve user preference, retaining historical preferences non-destructively."""
        return self.preferences.evolve_preference(context, new_preference_text, topic, importance)

    def get_preference_history(
        self,
        context: AuthContext,
        topic: str,
    ) -> PreferenceEvolutionResult:
        """Retrieve chronological evolution of preferences on a topic."""
        return self.preferences.get_preference_history(context, topic)

    def transition_lifecycle(
        self,
        context: AuthContext,
        memory_id: str,
        target_state: str | MemoryLifecycleState,
        reason: str = "",
    ) -> MemoryRecord:
        """Transition memory through its deterministic lifecycle."""
        return self.lifecycle.transition_state(context, memory_id, target_state, reason)

    def mark_obsolete(
        self,
        context: AuthContext,
        memory_id: str,
        reason: str,
    ) -> MemoryRecord:
        """Soft-deactivate and mark a memory obsolete with audit metadata."""
        return self.lifecycle.mark_obsolete(context, memory_id, reason)

    def detect_obsolete_memories(
        self,
        context: AuthContext,
        domain: str = MemoryDomain.BOSS_PERSONAL.value,
        session_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Identify candidate memories that are superseded, concluded, or expired."""
        return self.lifecycle.detect_obsolete_memories(context, domain, session_id)

    def get_user_model(
        self,
        context: AuthContext,
        domain: str = MemoryDomain.BOSS_PERSONAL.value,
        include_core: bool = False,
        session_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> UserModel:
        """Derive the coherent user model on-the-fly from active canonical memories."""
        return self.user_model.build_user_model(context, domain, include_core, session_id, now)
