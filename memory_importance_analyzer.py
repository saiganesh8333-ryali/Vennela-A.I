"""
Memory Importance Analyzer for Vennela A.I (Phase C)

This module provides sophisticated importance scoring for memories based on
multiple factors including frequency, recency, user interaction, and relevance.

Key Features:
- Multi-factor importance scoring (0-1)
- Frequency analysis
- Recency weighting
- User interaction tracking
- Importance level classification
- Event-driven async scoring
- Thread-safe operations

Author: Vennela A.I Evolution
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from event_bus import EventHandler
from event_types import BaseEvent, EventType

logger = logging.getLogger(__name__)


class ImportanceLevel(Enum):
    """Classification of memory importance."""
    CRITICAL = "critical"      # 0.8-1.0
    HIGH = "high"              # 0.6-0.79
    MEDIUM = "medium"          # 0.4-0.59
    LOW = "low"                # 0.2-0.39
    MINIMAL = "minimal"        # 0.0-0.19


@dataclass
class ImportanceFactors:
    """
    Factors used in importance scoring.
    
    Attributes:
        frequency_score: How often the memory is accessed (0-1)
        recency_score: How recent the memory is (0-1)
        interaction_score: User interaction intensity (0-1)
        relevance_score: Relevance to current context (0-1)
        emotional_weight: Emotional significance (0-1)
        weights: Dictionary of factor weights (must sum to 1.0)
    """
    frequency_score: float = 0.0
    recency_score: float = 0.0
    interaction_score: float = 0.0
    relevance_score: float = 0.0
    emotional_weight: float = 0.0
    weights: Dict[str, float] = field(default_factory=lambda: {
        'frequency': 0.25,
        'recency': 0.25,
        'interaction': 0.25,
        'relevance': 0.15,
        'emotional': 0.10
    })
    
    def calculate_total(self) -> float:
        """Calculate weighted importance score."""
        total = (
            self.frequency_score * self.weights.get('frequency', 0.0) +
            self.recency_score * self.weights.get('recency', 0.0) +
            self.interaction_score * self.weights.get('interaction', 0.0) +
            self.relevance_score * self.weights.get('relevance', 0.0) +
            self.emotional_weight * self.weights.get('emotional', 0.0)
        )
        # Clamp to 0-1 range
        return min(max(total, 0.0), 1.0)


@dataclass
class MemoryAccessRecord:
    """Record of memory access for scoring."""
    memory_id: str
    creation_time: float
    last_access_time: float = field(default_factory=time.time)
    access_count: int = 0
    interaction_events: List[str] = field(default_factory=list)
    relevance_context: Dict[str, Any] = field(default_factory=dict)
    emotional_tags: List[str] = field(default_factory=list)
    
    def add_interaction(self, interaction_type: str) -> None:
        """Record an interaction with this memory."""
        self.interaction_events.append(interaction_type)
        self.access_count += 1
        self.last_access_time = time.time()
    
    def age_seconds(self) -> float:
        """Get age of memory in seconds."""
        return time.time() - self.creation_time
    
    def time_since_access(self) -> float:
        """Get seconds since last access."""
        return time.time() - self.last_access_time


class ImportanceAnalyzer:
    """
    Analyzer for scoring memory importance.
    
    Uses multiple factors to compute a comprehensive importance score
    that identifies which memories are most critical for retention.
    """
    
    # Configuration constants
    MAX_MEMORY_AGE = 86400 * 30  # 30 days
    RECENCY_HALF_LIFE = 3600 * 24  # 1 day (recency decays exponentially)
    FREQUENCY_BASELINE = 10  # Number of accesses for max frequency score
    
    def __init__(self):
        """Initialize the importance analyzer."""
        self.memory_records: Dict[str, MemoryAccessRecord] = {}
        self.lock = threading.RLock()
        self.importance_cache: Dict[str, float] = {}
        self.cache_timestamps: Dict[str, float] = {}
        self.cache_ttl = 300  # 5 minutes
        logger.info("ImportanceAnalyzer initialized")
    
    def track_memory(
        self,
        memory_id: str,
        creation_time: Optional[float] = None,
        initial_importance: float = 0.5
    ) -> MemoryAccessRecord:
        """
        Start tracking a memory for importance scoring.
        
        Args:
            memory_id: Unique memory identifier
            creation_time: When the memory was created (now if None)
            initial_importance: Initial importance score
            
        Returns:
            The created MemoryAccessRecord
            
        Raises:
            ValueError: If memory_id is invalid
        """
        if not memory_id:
            raise ValueError("memory_id is required")
        
        with self.lock:
            if memory_id not in self.memory_records:
                record = MemoryAccessRecord(
                    memory_id=memory_id,
                    creation_time=creation_time or time.time()
                )
                self.memory_records[memory_id] = record
                logger.debug(f"Started tracking memory: {memory_id}")
                return record
            
            return self.memory_records[memory_id]
    
    def record_interaction(
        self,
        memory_id: str,
        interaction_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record an interaction with a memory.
        
        Args:
            memory_id: Memory identifier
            interaction_type: Type of interaction (retrieve, update, etc.)
            metadata: Additional interaction data
            
        Raises:
            KeyError: If memory_id not found in tracking
        """
        with self.lock:
            if memory_id not in self.memory_records:
                raise KeyError(f"Memory {memory_id} not found in tracking")
            
            record = self.memory_records[memory_id]
            record.add_interaction(interaction_type)
            
            # Update cache invalidation
            self.cache_timestamps[memory_id] = 0
            
            logger.debug(f"Recorded interaction for {memory_id}: {interaction_type}")
    
    def _calculate_frequency_score(self, record: MemoryAccessRecord) -> float:
        """
        Calculate frequency score (0-1).
        
        Based on how often the memory is accessed.
        """
        # Normalize access count relative to baseline
        normalized = min(record.access_count / self.FREQUENCY_BASELINE, 1.0)
        return normalized
    
    def _calculate_recency_score(self, record: MemoryAccessRecord) -> float:
        """
        Calculate recency score (0-1).
        
        Uses exponential decay based on time since last access.
        """
        time_since_access = record.time_since_access()
        
        # Exponential decay: e^(-t/half_life)
        decay_factor = 2 ** (-time_since_access / self.RECENCY_HALF_LIFE)
        return decay_factor
    
    def _calculate_interaction_score(self, record: MemoryAccessRecord) -> float:
        """
        Calculate interaction score (0-1).
        
        Based on types and intensity of interactions.
        """
        if not record.interaction_events:
            return 0.0
        
        # Weight different interaction types
        interaction_weights = {
            'retrieve': 0.5,
            'update': 1.0,
            'reference': 0.3,
            'share': 0.7,
            'consolidate': 0.8
        }
        
        total_weight = 0.0
        for event_type in record.interaction_events:
            weight = interaction_weights.get(event_type, 0.5)
            total_weight += weight
        
        # Normalize to 0-1 range
        normalized = min(total_weight / len(record.interaction_events), 1.0)
        return normalized
    
    def _calculate_relevance_score(self, record: MemoryAccessRecord) -> float:
        """
        Calculate relevance score (0-1).
        
        Based on contextual relevance metadata.
        """
        context = record.relevance_context
        
        if not context:
            return 0.5  # Default if no context provided
        
        score = 0.0
        factor_count = 0
        
        # Check various relevance factors
        if context.get('is_frequently_referenced', False):
            score += 1.0
            factor_count += 1
        
        if context.get('is_core_domain', False):
            score += 0.8
            factor_count += 1
        
        if context.get('connections_count', 0) > 5:
            score += 0.7
            factor_count += 1
        
        if context.get('user_rated', False):
            user_rating = context.get('user_rating', 0)
            score += user_rating  # Assume 0-1
            factor_count += 1
        
        if factor_count == 0:
            return 0.5
        
        return min(score / factor_count, 1.0)
    
    def _calculate_emotional_weight(self, record: MemoryAccessRecord) -> float:
        """
        Calculate emotional weight (0-1).
        
        Based on emotional tags and significance.
        """
        if not record.emotional_tags:
            return 0.0
        
        # Map emotional tags to scores
        emotional_scores = {
            'positive': 0.6,
            'negative': 0.8,  # Negative emotions often more memorable
            'intense': 0.9,
            'milestone': 1.0,
            'personal': 0.7,
            'meaningful': 0.8
        }
        
        total_score = 0.0
        for tag in record.emotional_tags:
            total_score += emotional_scores.get(tag, 0.5)
        
        # Average emotional weight
        return min(total_score / len(record.emotional_tags), 1.0)
    
    def score_memory(
        self,
        memory_id: str,
        include_cache: bool = True,
        custom_weights: Optional[Dict[str, float]] = None
    ) -> float:
        """
        Calculate importance score for a memory (0-1).
        
        Args:
            memory_id: Memory identifier
            include_cache: Use cached score if available
            custom_weights: Override default factor weights
            
        Returns:
            Importance score (0-1)
            
        Raises:
            KeyError: If memory_id not found
        """
        with self.lock:
            # Check cache
            if include_cache and memory_id in self.importance_cache:
                cache_time = self.cache_timestamps.get(memory_id, 0)
                if time.time() - cache_time < self.cache_ttl:
                    return self.importance_cache[memory_id]
            
            if memory_id not in self.memory_records:
                raise KeyError(f"Memory {memory_id} not tracked")
            
            record = self.memory_records[memory_id]
            
            # Calculate individual factors
            factors = ImportanceFactors(
                frequency_score=self._calculate_frequency_score(record),
                recency_score=self._calculate_recency_score(record),
                interaction_score=self._calculate_interaction_score(record),
                relevance_score=self._calculate_relevance_score(record),
                emotional_weight=self._calculate_emotional_weight(record),
                weights=custom_weights or ImportanceFactors().weights
            )
            
            # Calculate total score
            score = factors.calculate_total()
            
            # Cache the result
            self.importance_cache[memory_id] = score
            self.cache_timestamps[memory_id] = time.time()
            
            logger.debug(f"Scored memory {memory_id}: {score:.2f}")
            
            return score
    
    def classify_importance(self, score: float) -> ImportanceLevel:
        """
        Classify importance score into a level.
        
        Args:
            score: Importance score (0-1)
            
        Returns:
            ImportanceLevel classification
        """
        if score >= 0.8:
            return ImportanceLevel.CRITICAL
        elif score >= 0.6:
            return ImportanceLevel.HIGH
        elif score >= 0.4:
            return ImportanceLevel.MEDIUM
        elif score >= 0.2:
            return ImportanceLevel.LOW
        else:
            return ImportanceLevel.MINIMAL
    
    def get_important_memories(
        self,
        min_importance: float = 0.5,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get most important memories above a threshold.
        
        Args:
            min_importance: Minimum importance score (0-1)
            limit: Maximum number to return
            
        Returns:
            List of memory info dicts, sorted by importance
        """
        with self.lock:
            # Score all memories and filter
            scored_memories = []
            for memory_id in self.memory_records.keys():
                try:
                    score = self.score_memory(memory_id, include_cache=False)
                    if score >= min_importance:
                        record = self.memory_records[memory_id]
                        scored_memories.append({
                            'memory_id': memory_id,
                            'importance_score': score,
                            'importance_level': self.classify_importance(score).value,
                            'access_count': record.access_count,
                            'age_seconds': record.age_seconds(),
                            'last_access': record.last_access_time
                        })
                except KeyError:
                    pass
            
            # Sort by importance descending
            scored_memories.sort(key=lambda x: x['importance_score'], reverse=True)
            
            return scored_memories[:limit]
    
    def get_memory_details(self, memory_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a memory's importance factors.
        
        Args:
            memory_id: Memory identifier
            
        Returns:
            Dictionary with detailed factor breakdown
            
        Raises:
            KeyError: If memory_id not found
        """
        with self.lock:
            if memory_id not in self.memory_records:
                raise KeyError(f"Memory {memory_id} not tracked")
            
            record = self.memory_records[memory_id]
            
            return {
                'memory_id': memory_id,
                'factors': {
                    'frequency_score': self._calculate_frequency_score(record),
                    'recency_score': self._calculate_recency_score(record),
                    'interaction_score': self._calculate_interaction_score(record),
                    'relevance_score': self._calculate_relevance_score(record),
                    'emotional_weight': self._calculate_emotional_weight(record)
                },
                'overall_score': self.score_memory(memory_id),
                'overall_level': self.classify_importance(self.score_memory(memory_id)).value,
                'metadata': {
                    'creation_time': record.creation_time,
                    'last_access_time': record.last_access_time,
                    'access_count': record.access_count,
                    'age_seconds': record.age_seconds(),
                    'time_since_access': record.time_since_access(),
                    'emotional_tags': record.emotional_tags,
                    'interaction_events': record.interaction_events
                }
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get analyzer statistics.
        
        Returns:
            Dictionary with statistics
        """
        with self.lock:
            scores = [self.score_memory(mid) for mid in self.memory_records.keys()]
            
            if not scores:
                return {
                    'total_memories_tracked': 0,
                    'cache_size': 0
                }
            
            return {
                'total_memories_tracked': len(self.memory_records),
                'cache_size': len(self.importance_cache),
                'average_importance': sum(scores) / len(scores),
                'min_importance': min(scores),
                'max_importance': max(scores),
                'memories_by_level': {
                    level.value: len([s for s in scores if self.classify_importance(s) == level])
                    for level in ImportanceLevel
                }
            }


class ImportanceScoringHandler(EventHandler):
    """
    Event handler that performs importance scoring on memory events.
    
    Listens for memory events and asynchronously computes and updates
    importance scores.
    """
    
    def __init__(self, analyzer: Optional[ImportanceAnalyzer] = None):
        """
        Initialize the scoring handler.
        
        Args:
            analyzer: ImportanceAnalyzer instance (creates new if None)
        """
        self.analyzer = analyzer or ImportanceAnalyzer()
        self._name = "ImportanceScoringHandler"
        logger.info("ImportanceScoringHandler initialized")
    
    @property
    def name(self) -> str:
        """Handler name."""
        return self._name
    
    @property
    def event_types(self) -> List[EventType]:
        """Event types this handler subscribes to."""
        return [
            EventType.MEMORY_CREATED,
            EventType.MEMORY_RETRIEVED,
            EventType.MEMORY_UPDATED
        ]
    
    async def handle(self, event: BaseEvent) -> None:
        """
        Handle memory events for importance scoring.
        
        Args:
            event: The event to handle
        """
        try:
            memory_id = event.metadata.get('memory_id')
            if not memory_id:
                return
            
            if event.event_type == EventType.MEMORY_CREATED:
                await self._handle_memory_created(event, memory_id)
            elif event.event_type == EventType.MEMORY_RETRIEVED:
                await self._handle_memory_retrieved(event, memory_id)
            elif event.event_type == EventType.MEMORY_UPDATED:
                await self._handle_memory_updated(event, memory_id)
            
        except Exception as e:
            logger.error(f"Error in ImportanceScoringHandler.handle: {e}", exc_info=True)
    
    async def _handle_memory_created(self, event: BaseEvent, memory_id: str) -> None:
        """Handle memory created event."""
        initial_score = event.metadata.get('importance', 0.5)
        self.analyzer.track_memory(
            memory_id=memory_id,
            initial_importance=initial_score
        )
        
        # Add emotional tags if present
        record = self.analyzer.memory_records.get(memory_id)
        if record and 'emotional_tags' in event.metadata:
            record.emotional_tags = event.metadata['emotional_tags']
        
        logger.debug(f"Created importance tracking for memory: {memory_id}")
    
    async def _handle_memory_retrieved(self, event: BaseEvent, memory_id: str) -> None:
        """Handle memory retrieved event."""
        try:
            self.analyzer.record_interaction(
                memory_id=memory_id,
                interaction_type='retrieve',
                metadata=event.metadata
            )
            
            # Get and log new score
            score = self.analyzer.score_memory(memory_id, include_cache=False)
            logger.debug(f"Updated importance score for {memory_id}: {score:.2f}")
            
        except KeyError:
            # Memory not yet tracked, create tracking
            self.analyzer.track_memory(memory_id=memory_id)
            self.analyzer.record_interaction(
                memory_id=memory_id,
                interaction_type='retrieve'
            )
    
    async def _handle_memory_updated(self, event: BaseEvent, memory_id: str) -> None:
        """Handle memory updated event."""
        try:
            self.analyzer.record_interaction(
                memory_id=memory_id,
                interaction_type='update',
                metadata=event.metadata
            )
            
            score = self.analyzer.score_memory(memory_id, include_cache=False)
            logger.debug(f"Updated importance score for {memory_id}: {score:.2f}")
            
        except KeyError:
            self.analyzer.track_memory(memory_id=memory_id)
            self.analyzer.record_interaction(
                memory_id=memory_id,
                interaction_type='update'
            )
