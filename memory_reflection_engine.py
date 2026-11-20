"""
Memory Reflection Engine for Vennela A.I (Phase C)

This module provides the core consolidation logic for the memory reflection cycle,
enabling short-term memories to be consolidated into episodic, semantic, and summary
forms for long-term retention and pattern extraction.

Key Features:
- Consolidation context tracking
- Multi-tier memory consolidation (short-term → episodic → semantic → summary)
- Event-driven consolidation triggers
- Thread-safe operations
- Comprehensive logging and error handling

Author: Vennela A.I Evolution
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from event_bus import EventHandler
from event_types import BaseEvent, EventType, MemoryCreatedEvent

logger = logging.getLogger(__name__)


class ConsolidationPhase(Enum):
    """Phases of memory consolidation."""
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    SUMMARY = "summary"


@dataclass
class MemoryRecord:
    """Record of a single memory for consolidation."""
    memory_id: str
    content: str
    memory_type: str
    timestamp: float
    importance: float = 0.5
    access_count: int = 0
    current_phase: ConsolidationPhase = ConsolidationPhase.WORKING
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_accessed: float = field(default_factory=time.time)
    
    def update_access(self) -> None:
        """Update access tracking."""
        self.access_count += 1
        self.last_accessed = time.time()
    
    def age_seconds(self) -> float:
        """Get age of memory in seconds."""
        return time.time() - self.timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'memory_id': self.memory_id,
            'content': self.content,
            'memory_type': self.memory_type,
            'timestamp': self.timestamp,
            'importance': self.importance,
            'access_count': self.access_count,
            'current_phase': self.current_phase.value,
            'last_accessed': self.last_accessed,
            'metadata': self.metadata
        }


@dataclass
class ConsolidationContext:
    """
    Tracks the state of memory consolidation for a user.
    
    This dataclass maintains consolidation metrics and state across
    the entire consolidation process.
    """
    user_id: str
    consolidation_started: float = field(default_factory=time.time)
    working_memories: Dict[str, MemoryRecord] = field(default_factory=dict)
    episodic_memories: Dict[str, MemoryRecord] = field(default_factory=dict)
    semantic_patterns: List[Dict[str, Any]] = field(default_factory=list)
    summary_data: Dict[str, Any] = field(default_factory=dict)
    consolidation_metrics: Dict[str, Any] = field(default_factory=dict)
    last_consolidation: Optional[float] = None
    consolidation_lock: threading.Lock = field(default_factory=threading.Lock)
    
    def is_active(self) -> bool:
        """Check if consolidation context is still active."""
        return len(self.working_memories) > 0 or len(self.episodic_memories) > 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get consolidation statistics."""
        return {
            'user_id': self.user_id,
            'active_since': self.consolidation_started,
            'working_memories_count': len(self.working_memories),
            'episodic_memories_count': len(self.episodic_memories),
            'semantic_patterns_count': len(self.semantic_patterns),
            'has_summary': bool(self.summary_data),
            'last_consolidation': self.last_consolidation,
            'consolidation_metrics': self.consolidation_metrics
        }


class MemoryConsolidationEngine:
    """
    Main orchestrator for memory consolidation.
    
    Handles the movement of memories from working memory through multiple
    consolidation phases to long-term storage, extracting patterns and
    creating summaries along the way.
    """
    
    # Thresholds for consolidation
    SHORT_TERM_AGE_THRESHOLD = 300  # 5 minutes
    MIN_IMPORTANCE_FOR_CONSOLIDATION = 0.3
    EPISODIC_CONSOLIDATION_INTERVAL = 600  # 10 minutes
    SEMANTIC_CONSOLIDATION_INTERVAL = 1800  # 30 minutes
    
    def __init__(self):
        """Initialize the consolidation engine."""
        self.contexts: Dict[str, ConsolidationContext] = {}
        self.lock = threading.RLock()
        logger.info("MemoryConsolidationEngine initialized")
    
    def get_or_create_context(self, user_id: str) -> ConsolidationContext:
        """
        Get or create consolidation context for a user.
        
        Args:
            user_id: The user identifier
            
        Returns:
            ConsolidationContext for the user
        """
        with self.lock:
            if user_id not in self.contexts:
                self.contexts[user_id] = ConsolidationContext(user_id=user_id)
                logger.debug(f"Created consolidation context for user {user_id}")
            return self.contexts[user_id]
    
    def add_working_memory(
        self,
        user_id: str,
        memory_id: str,
        content: str,
        memory_type: str,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryRecord:
        """
        Add a new memory to working memory.
        
        Args:
            user_id: User identifier
            memory_id: Unique memory identifier
            content: Memory content
            memory_type: Type of memory (episodic, semantic, skill)
            importance: Importance score (0-1)
            metadata: Additional metadata
            
        Returns:
            The created MemoryRecord
            
        Raises:
            ValueError: If parameters are invalid
        """
        if not memory_id or not content:
            raise ValueError("memory_id and content are required")
        
        if not 0 <= importance <= 1:
            raise ValueError(f"importance must be 0-1, got {importance}")
        
        context = self.get_or_create_context(user_id)
        
        with context.consolidation_lock:
            record = MemoryRecord(
                memory_id=memory_id,
                content=content,
                memory_type=memory_type,
                timestamp=time.time(),
                importance=importance,
                metadata=metadata or {}
            )
            context.working_memories[memory_id] = record
            logger.debug(f"Added working memory {memory_id} for user {user_id}")
            return record
    
    async def consolidate_short_term(self, user_id: str) -> Dict[str, Any]:
        """
        Consolidate short-term memories to episodic memories.
        
        Moves memories from working memory to episodic storage based on
        age and importance thresholds.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with consolidation results
        """
        context = self.get_or_create_context(user_id)
        
        with context.consolidation_lock:
            consolidated = []
            not_ready = []
            current_time = time.time()
            
            for memory_id, record in list(context.working_memories.items()):
                age = current_time - record.timestamp
                
                # Check consolidation criteria
                if (age >= self.SHORT_TERM_AGE_THRESHOLD and 
                    record.importance >= self.MIN_IMPORTANCE_FOR_CONSOLIDATION):
                    
                    # Move to episodic
                    record.current_phase = ConsolidationPhase.EPISODIC
                    context.episodic_memories[memory_id] = record
                    del context.working_memories[memory_id]
                    consolidated.append(memory_id)
                    logger.debug(f"Consolidated {memory_id} to episodic for user {user_id}")
                else:
                    not_ready.append(memory_id)
            
            context.last_consolidation = time.time()
            
            result = {
                'user_id': user_id,
                'phase': 'short_term_to_episodic',
                'consolidated_count': len(consolidated),
                'consolidated_ids': consolidated,
                'not_ready_count': len(not_ready),
                'timestamp': context.last_consolidation
            }
            
            context.consolidation_metrics['last_short_term_consolidation'] = result
            logger.info(f"Short-term consolidation for {user_id}: {len(consolidated)} consolidated")
            
            return result
    
    async def consolidate_to_semantic(self, user_id: str) -> Dict[str, Any]:
        """
        Extract semantic patterns from episodic memories.
        
        Analyzes episodic memories to identify patterns, relationships,
        and generalizable knowledge.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with semantic patterns extracted
        """
        context = self.get_or_create_context(user_id)
        
        with context.consolidation_lock:
            # Group episodic memories by type
            memories_by_type: Dict[str, List[MemoryRecord]] = {}
            for memory_id, record in context.episodic_memories.items():
                if record.memory_type not in memories_by_type:
                    memories_by_type[record.memory_type] = []
                memories_by_type[record.memory_type].append(record)
            
            # Extract patterns for each type
            new_patterns = []
            for memory_type, memories in memories_by_type.items():
                if len(memories) >= 2:  # Need at least 2 memories to find patterns
                    pattern = {
                        'pattern_id': f"pattern_{memory_type}_{int(time.time())}",
                        'memory_type': memory_type,
                        'extracted_at': time.time(),
                        'source_memories': [m.memory_id for m in memories],
                        'memory_count': len(memories),
                        'avg_importance': sum(m.importance for m in memories) / len(memories),
                        'pattern_metadata': {
                            'earliest_memory': min(m.timestamp for m in memories),
                            'latest_memory': max(m.timestamp for m in memories),
                            'total_access_count': sum(m.access_count for m in memories)
                        }
                    }
                    context.semantic_patterns.append(pattern)
                    new_patterns.append(pattern['pattern_id'])
                    logger.debug(f"Extracted semantic pattern {pattern['pattern_id']}")
            
            context.last_consolidation = time.time()
            
            result = {
                'user_id': user_id,
                'phase': 'episodic_to_semantic',
                'patterns_extracted': len(new_patterns),
                'pattern_ids': new_patterns,
                'total_patterns': len(context.semantic_patterns),
                'timestamp': context.last_consolidation
            }
            
            context.consolidation_metrics['last_semantic_consolidation'] = result
            logger.info(f"Semantic consolidation for {user_id}: {len(new_patterns)} patterns extracted")
            
            return result
    
    async def consolidate_to_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Create summaries from consolidated memories and patterns.
        
        Generates high-level summaries of memories, patterns, and interactions
        for quick access and understanding.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with summary data
        """
        context = self.get_or_create_context(user_id)
        
        with context.consolidation_lock:
            # Build comprehensive summary
            summary_data = {
                'created_at': time.time(),
                'user_id': user_id,
                'summary_type': 'comprehensive',
                'statistics': {
                    'total_episodic_memories': len(context.episodic_memories),
                    'total_semantic_patterns': len(context.semantic_patterns),
                    'average_memory_importance': (
                        sum(m.importance for m in context.episodic_memories.values()) / 
                        len(context.episodic_memories) if context.episodic_memories else 0
                    ),
                    'memory_types': list(set(
                        m.memory_type for m in context.episodic_memories.values()
                    ))
                },
                'high_importance_memories': [
                    record.memory_id for record in 
                    sorted(
                        context.episodic_memories.values(),
                        key=lambda r: r.importance,
                        reverse=True
                    )[:10]  # Top 10
                ],
                'pattern_summary': {
                    'total_patterns': len(context.semantic_patterns),
                    'patterns_by_type': {}
                }
            }
            
            # Summarize patterns by type
            for pattern in context.semantic_patterns:
                ptype = pattern['memory_type']
                if ptype not in summary_data['pattern_summary']['patterns_by_type']:
                    summary_data['pattern_summary']['patterns_by_type'][ptype] = []
                summary_data['pattern_summary']['patterns_by_type'][ptype].append({
                    'pattern_id': pattern['pattern_id'],
                    'memory_count': pattern['memory_count'],
                    'avg_importance': pattern['avg_importance']
                })
            
            context.summary_data = summary_data
            context.last_consolidation = time.time()
            
            result = {
                'user_id': user_id,
                'phase': 'create_summary',
                'summary_created': True,
                'summary_size': len(str(summary_data)),
                'timestamp': context.last_consolidation
            }
            
            context.consolidation_metrics['last_summary_consolidation'] = result
            logger.info(f"Summary consolidation for {user_id}: summary created")
            
            return result
    
    async def run_full_consolidation_cycle(self, user_id: str) -> Dict[str, Any]:
        """
        Run complete consolidation cycle for a user.
        
        Executes all consolidation phases in sequence.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with results from all phases
        """
        logger.info(f"Starting full consolidation cycle for user {user_id}")
        start_time = time.time()
        
        results = {
            'user_id': user_id,
            'cycle_started': start_time,
            'phases': {}
        }
        
        try:
            # Phase 1: Short-term to episodic
            results['phases']['short_term'] = await self.consolidate_short_term(user_id)
            
            # Phase 2: Episodic to semantic
            results['phases']['semantic'] = await self.consolidate_to_semantic(user_id)
            
            # Phase 3: Create summary
            results['phases']['summary'] = await self.consolidate_to_summary(user_id)
            
            results['cycle_completed'] = time.time()
            results['cycle_duration'] = results['cycle_completed'] - start_time
            
            logger.info(f"Completed consolidation cycle for {user_id} in {results['cycle_duration']:.2f}s")
            
        except Exception as e:
            logger.error(f"Error during consolidation cycle for {user_id}: {e}", exc_info=True)
            results['error'] = str(e)
        
        return results
    
    def get_context_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get statistics for a user's consolidation context.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with context statistics
        """
        context = self.get_or_create_context(user_id)
        with context.consolidation_lock:
            return context.get_stats()
    
    def get_all_stats(self) -> Dict[str, Any]:
        """
        Get statistics for all consolidation contexts.
        
        Returns:
            Dictionary with global statistics
        """
        with self.lock:
            return {
                'total_active_contexts': len(self.contexts),
                'contexts': {
                    user_id: ctx.get_stats() 
                    for user_id, ctx in self.contexts.items()
                }
            }


class ReflectionHandler(EventHandler):
    """
    Event handler that triggers memory consolidation on relevant events.
    
    Listens for memory and reflection events and orchestrates the
    consolidation cycle.
    """
    
    def __init__(self, engine: Optional[MemoryConsolidationEngine] = None):
        """
        Initialize the reflection handler.
        
        Args:
            engine: MemoryConsolidationEngine instance (creates new if None)
        """
        self.engine = engine or MemoryConsolidationEngine()
        self._name = "ReflectionHandler"
        logger.info("ReflectionHandler initialized")
    
    @property
    def name(self) -> str:
        """Handler name."""
        return self._name
    
    @property
    def event_types(self) -> List[EventType]:
        """Event types this handler subscribes to."""
        return [
            EventType.MEMORY_CREATED,
            EventType.MEMORY_UPDATED,
            EventType.REFLECTION_STARTED
        ]
    
    async def handle(self, event: BaseEvent) -> None:
        """
        Handle memory-related events.
        
        Args:
            event: The event to handle
        """
        try:
            user_id = event.user_id
            
            if event.event_type == EventType.MEMORY_CREATED:
                await self._handle_memory_created(event, user_id)
            elif event.event_type == EventType.MEMORY_UPDATED:
                await self._handle_memory_updated(event, user_id)
            elif event.event_type == EventType.REFLECTION_STARTED:
                await self._handle_reflection_started(event, user_id)
            
        except Exception as e:
            logger.error(f"Error in ReflectionHandler.handle: {e}", exc_info=True)
    
    async def _handle_memory_created(self, event: BaseEvent, user_id: str) -> None:
        """Handle memory created event."""
        memory_type = event.metadata.get('memory_type', 'unknown')
        content = event.metadata.get('content', '')
        importance = event.metadata.get('importance', 0.5)
        memory_id = event.metadata.get('memory_id', f"mem_{int(time.time())}")
        
        # Add to working memory
        self.engine.add_working_memory(
            user_id=user_id,
            memory_id=memory_id,
            content=content,
            memory_type=memory_type,
            importance=importance,
            metadata=event.metadata
        )
        
        logger.debug(f"Added working memory from event: {memory_id}")
    
    async def _handle_memory_updated(self, event: BaseEvent, user_id: str) -> None:
        """Handle memory updated event."""
        context = self.engine.get_or_create_context(user_id)
        memory_id = event.metadata.get('memory_id')
        
        if memory_id:
            with context.consolidation_lock:
                # Update memory if found in any phase
                for memory_dict in [context.working_memories, context.episodic_memories]:
                    if memory_id in memory_dict:
                        memory_dict[memory_id].update_access()
                        logger.debug(f"Updated memory access: {memory_id}")
    
    async def _handle_reflection_started(self, event: BaseEvent, user_id: str) -> None:
        """Handle reflection started event."""
        logger.info(f"Reflection started for user {user_id}, running consolidation")
        await self.engine.run_full_consolidation_cycle(user_id)
