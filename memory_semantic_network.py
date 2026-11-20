"""
Memory Semantic Network for Vennela A.I (Phase C)

This module builds and manages a semantic network of memories, creating
connections between memories to enable pattern discovery and knowledge integration.

Key Features:
- Semantic link creation and management
- Multiple relationship types (causal, temporal, conceptual, emotional)
- Network analysis and statistics
- Link strength and weight management
- Bidirectional relationship support
- Thread-safe operations
- Event-driven link building

Author: Vennela A.I Evolution
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from event_bus import EventHandler
from event_types import BaseEvent, EventType

logger = logging.getLogger(__name__)


class RelationshipType(Enum):
    """Types of relationships between memories."""
    CAUSAL = "causal"              # A causes B
    TEMPORAL = "temporal"          # A precedes B in time
    CONCEPTUAL = "conceptual"      # A and B share concepts
    EMOTIONAL = "emotional"        # A and B share emotions
    REFERENCE = "reference"        # A references B
    SIMILAR = "similar"            # A is similar to B
    HIERARCHICAL = "hierarchical"  # A is parent/child of B
    REINFORCING = "reinforcing"    # A reinforces B


@dataclass
class SemanticLink:
    """
    Represents a connection between two memories.
    
    Attributes:
        link_id: Unique identifier for this link
        memory_id_1: First memory in the relationship
        memory_id_2: Second memory in the relationship
        relationship_type: Type of relationship
        strength: Link strength (0-1)
        weight: Link weight for importance (0-1)
        created_at: Timestamp of creation
        last_updated: Last update timestamp
        metadata: Additional link information
        bidirectional: Whether relationship goes both ways
    """
    link_id: str
    memory_id_1: str
    memory_id_2: str
    relationship_type: RelationshipType
    strength: float = 0.5
    weight: float = 1.0
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    bidirectional: bool = True
    
    def __post_init__(self):
        """Validate link parameters."""
        if not all([self.memory_id_1, self.memory_id_2]):
            raise ValueError("Both memory IDs are required")
        
        if self.memory_id_1 == self.memory_id_2:
            raise ValueError("Cannot link memory to itself")
        
        if not (0 <= self.strength <= 1):
            raise ValueError(f"strength must be 0-1, got {self.strength}")
        
        if not (0 <= self.weight <= 1):
            raise ValueError(f"weight must be 0-1, got {self.weight}")
    
    def update_strength(self, new_strength: float) -> None:
        """
        Update link strength.
        
        Args:
            new_strength: New strength value (0-1)
            
        Raises:
            ValueError: If new_strength is invalid
        """
        if not (0 <= new_strength <= 1):
            raise ValueError(f"strength must be 0-1, got {new_strength}")
        
        self.strength = new_strength
        self.last_updated = time.time()
    
    def reinforce(self, factor: float = 0.1) -> None:
        """
        Reinforce this link (increase strength).
        
        Args:
            factor: Amount to increase strength by (0-1)
        """
        new_strength = min(self.strength + factor, 1.0)
        self.update_strength(new_strength)
    
    def decay(self, factor: float = 0.05) -> None:
        """
        Decay this link (decrease strength).
        
        Args:
            factor: Amount to decrease strength by (0-1)
        """
        new_strength = max(self.strength - factor, 0.0)
        self.update_strength(new_strength)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'link_id': self.link_id,
            'memory_id_1': self.memory_id_1,
            'memory_id_2': self.memory_id_2,
            'relationship_type': self.relationship_type.value,
            'strength': self.strength,
            'weight': self.weight,
            'created_at': self.created_at,
            'last_updated': self.last_updated,
            'metadata': self.metadata,
            'bidirectional': self.bidirectional
        }


class SemanticNetwork:
    """
    Manages a network of semantic links between memories.
    
    Enables discovery of relationships, pattern recognition, and
    knowledge integration across memories.
    """
    
    def __init__(self):
        """Initialize the semantic network."""
        self.links: Dict[str, SemanticLink] = {}
        self.link_index: Dict[str, Set[str]] = {}  # memory_id -> set of linked memory_ids
        self.lock = threading.RLock()
        logger.info("SemanticNetwork initialized")
    
    def add_link(
        self,
        memory_id_1: str,
        memory_id_2: str,
        relationship_type: RelationshipType,
        strength: float = 0.5,
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
        bidirectional: bool = True
    ) -> SemanticLink:
        """
        Add a link between two memories.
        
        Args:
            memory_id_1: First memory identifier
            memory_id_2: Second memory identifier
            relationship_type: Type of relationship
            strength: Link strength (0-1)
            weight: Link weight (0-1)
            metadata: Additional information
            bidirectional: Whether relationship is bidirectional
            
        Returns:
            The created SemanticLink
            
        Raises:
            ValueError: If parameters are invalid
        """
        if not memory_id_1 or not memory_id_2:
            raise ValueError("Both memory IDs are required")
        
        if memory_id_1 == memory_id_2:
            raise ValueError("Cannot link memory to itself")
        
        with self.lock:
            # Create link ID
            link_id = self._generate_link_id(memory_id_1, memory_id_2, relationship_type)
            
            # Check if link already exists
            if link_id in self.links:
                # Update existing link
                link = self.links[link_id]
                link.update_strength(strength)
                link.weight = weight
                link.metadata.update(metadata or {})
                logger.debug(f"Updated link: {link_id}")
                return link
            
            # Create new link
            link = SemanticLink(
                link_id=link_id,
                memory_id_1=memory_id_1,
                memory_id_2=memory_id_2,
                relationship_type=relationship_type,
                strength=strength,
                weight=weight,
                metadata=metadata or {},
                bidirectional=bidirectional
            )
            
            self.links[link_id] = link
            
            # Update index
            if memory_id_1 not in self.link_index:
                self.link_index[memory_id_1] = set()
            self.link_index[memory_id_1].add(memory_id_2)
            
            if bidirectional:
                if memory_id_2 not in self.link_index:
                    self.link_index[memory_id_2] = set()
                self.link_index[memory_id_2].add(memory_id_1)
            
            logger.debug(f"Added link: {link_id} ({relationship_type.value})")
            
            return link
    
    def remove_link(self, memory_id_1: str, memory_id_2: str) -> bool:
        """
        Remove a link between two memories.
        
        Args:
            memory_id_1: First memory identifier
            memory_id_2: Second memory identifier
            
        Returns:
            True if link was removed, False if not found
        """
        with self.lock:
            link_id = self._generate_link_id(memory_id_1, memory_id_2)
            
            if link_id not in self.links:
                return False
            
            link = self.links[link_id]
            
            # Remove from index
            if memory_id_1 in self.link_index:
                self.link_index[memory_id_1].discard(memory_id_2)
            
            if link.bidirectional and memory_id_2 in self.link_index:
                self.link_index[memory_id_2].discard(memory_id_1)
            
            del self.links[link_id]
            logger.debug(f"Removed link: {link_id}")
            
            return True
    
    def get_link(
        self,
        memory_id_1: str,
        memory_id_2: str
    ) -> Optional[SemanticLink]:
        """
        Get a specific link between two memories.
        
        Args:
            memory_id_1: First memory identifier
            memory_id_2: Second memory identifier
            
        Returns:
            SemanticLink if found, None otherwise
        """
        with self.lock:
            link_id = self._generate_link_id(memory_id_1, memory_id_2)
            return self.links.get(link_id)
    
    def find_related(
        self,
        memory_id: str,
        max_depth: int = 2,
        relationship_type: Optional[RelationshipType] = None
    ) -> Dict[str, Any]:
        """
        Find all memories related to a given memory.
        
        Uses breadth-first search to find related memories up to a maximum depth.
        
        Args:
            memory_id: Starting memory identifier
            max_depth: Maximum relationship depth to search (1-3)
            relationship_type: Filter by relationship type (None = all)
            
        Returns:
            Dictionary with related memories organized by depth and type
            
        Raises:
            ValueError: If max_depth is invalid
        """
        if not (1 <= max_depth <= 3):
            raise ValueError(f"max_depth must be 1-3, got {max_depth}")
        
        with self.lock:
            results = {
                'memory_id': memory_id,
                'depth': max_depth,
                'by_depth': {i: [] for i in range(1, max_depth + 1)},
                'by_type': {},
                'total_count': 0
            }
            
            # BFS to find related memories
            visited = {memory_id}
            current_level = [memory_id]
            
            for depth in range(1, max_depth + 1):
                next_level = []
                
                for current_id in current_level:
                    if current_id not in self.link_index:
                        continue
                    
                    for related_id in self.link_index[current_id]:
                        if related_id in visited:
                            continue
                        
                        visited.add(related_id)
                        
                        # Get link info
                        link = self.get_link(current_id, related_id)
                        if link:
                            if relationship_type is None or link.relationship_type == relationship_type:
                                related_info = {
                                    'memory_id': related_id,
                                    'relationship_type': link.relationship_type.value,
                                    'strength': link.strength,
                                    'weight': link.weight,
                                    'via': current_id
                                }
                                
                                results['by_depth'][depth].append(related_info)
                                
                                # Track by type
                                rtype = link.relationship_type.value
                                if rtype not in results['by_type']:
                                    results['by_type'][rtype] = []
                                results['by_type'][rtype].append(related_info)
                                
                                results['total_count'] += 1
                                next_level.append(related_id)
                
                current_level = next_level
                if not current_level:  # No more related memories
                    break
            
            logger.debug(f"Found {results['total_count']} related memories for {memory_id}")
            
            return results
    
    def get_network_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive network statistics.
        
        Returns:
            Dictionary with network metrics
        """
        with self.lock:
            if not self.links:
                return {
                    'total_links': 0,
                    'total_memories': 0,
                    'average_connections': 0.0,
                    'by_type': {}
                }
            
            # Count by type
            by_type = {}
            for link in self.links.values():
                rtype = link.relationship_type.value
                if rtype not in by_type:
                    by_type[rtype] = 0
                by_type[rtype] += 1
            
            # Average connections per memory
            total_connections = sum(len(ids) for ids in self.link_index.values())
            avg_connections = (
                total_connections / len(self.link_index) 
                if self.link_index else 0.0
            )
            
            # Network density
            total_memories = len(self.link_index)
            max_possible_links = total_memories * (total_memories - 1) / 2
            network_density = (
                len(self.links) / max_possible_links 
                if max_possible_links > 0 else 0.0
            )
            
            return {
                'total_links': len(self.links),
                'total_memories': total_memories,
                'average_connections': avg_connections,
                'network_density': network_density,
                'by_type': by_type,
                'average_link_strength': (
                    sum(link.strength for link in self.links.values()) / len(self.links)
                    if self.links else 0.0
                )
            }
    
    def reinforce_path(
        self,
        memory_ids: List[str],
        factor: float = 0.1
    ) -> int:
        """
        Reinforce a path of related memories.
        
        Args:
            memory_ids: Ordered list of memory IDs in the path
            factor: Reinforcement factor
            
        Returns:
            Number of links reinforced
            
        Raises:
            ValueError: If path is too short
        """
        if len(memory_ids) < 2:
            raise ValueError("Path must contain at least 2 memories")
        
        with self.lock:
            reinforced = 0
            
            # Reinforce consecutive pairs in path
            for i in range(len(memory_ids) - 1):
                link = self.get_link(memory_ids[i], memory_ids[i + 1])
                if link:
                    link.reinforce(factor)
                    reinforced += 1
            
            logger.debug(f"Reinforced path of {reinforced} links")
            
            return reinforced
    
    def decay_all_links(self, factor: float = 0.01) -> int:
        """
        Decay all links (time-based decay).
        
        Args:
            factor: Decay factor
            
        Returns:
            Number of links decayed
        """
        with self.lock:
            decayed = 0
            
            for link in self.links.values():
                link.decay(factor)
                decayed += 1
            
            logger.debug(f"Decayed {decayed} links")
            
            return decayed
    
    def get_strongest_links(
        self,
        memory_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get the strongest links in the network.
        
        Args:
            memory_id: If provided, get strongest links for this memory
            limit: Maximum number of links to return
            
        Returns:
            List of strongest links sorted by strength
        """
        with self.lock:
            if memory_id:
                # Get links for specific memory
                links_to_check = []
                if memory_id in self.link_index:
                    for related_id in self.link_index[memory_id]:
                        link = self.get_link(memory_id, related_id)
                        if link:
                            links_to_check.append(link)
            else:
                # Get all links
                links_to_check = list(self.links.values())
            
            # Sort by strength
            links_to_check.sort(key=lambda l: l.strength, reverse=True)
            
            return [link.to_dict() for link in links_to_check[:limit]]
    
    def _generate_link_id(
        self,
        memory_id_1: str,
        memory_id_2: str,
        relationship_type: Optional[RelationshipType] = None
    ) -> str:
        """
        Generate a unique link ID.
        
        Args:
            memory_id_1: First memory
            memory_id_2: Second memory
            relationship_type: Optional relationship type
            
        Returns:
            Unique link ID
        """
        # Ensure consistent ordering for bidirectional links
        sorted_ids = sorted([memory_id_1, memory_id_2])
        base = f"{sorted_ids[0]}_{sorted_ids[1]}"
        
        if relationship_type:
            return f"{base}_{relationship_type.value}"
        
        return base


class SemanticLinkingHandler(EventHandler):
    """
    Event handler that builds the semantic network.
    
    Listens for memory and reflection events and automatically creates
    semantic links between related memories.
    """
    
    def __init__(self, network: Optional[SemanticNetwork] = None):
        """
        Initialize the semantic linking handler.
        
        Args:
            network: SemanticNetwork instance (creates new if None)
        """
        self.network = network or SemanticNetwork()
        self._name = "SemanticLinkingHandler"
        self.processing_lock = threading.Lock()
        logger.info("SemanticLinkingHandler initialized")
    
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
            EventType.REFLECTION_COMPLETED
        ]
    
    async def handle(self, event: BaseEvent) -> None:
        """
        Handle memory events for semantic linking.
        
        Args:
            event: The event to handle
        """
        try:
            if event.event_type == EventType.MEMORY_CREATED:
                await self._handle_memory_created(event)
            elif event.event_type == EventType.MEMORY_UPDATED:
                await self._handle_memory_updated(event)
            elif event.event_type == EventType.REFLECTION_COMPLETED:
                await self._handle_reflection_completed(event)
            
        except Exception as e:
            logger.error(f"Error in SemanticLinkingHandler.handle: {e}", exc_info=True)
    
    async def _handle_memory_created(self, event: BaseEvent) -> None:
        """Handle memory created event - create links based on content."""
        memory_id = event.metadata.get('memory_id')
        content = event.metadata.get('content', '')
        
        if not memory_id:
            return
        
        # Try to identify related memories in metadata
        related_ids = event.metadata.get('related_memories', [])
        
        for related_id in related_ids:
            relationship_type = event.metadata.get(
                f'relationship_to_{related_id}',
                RelationshipType.CONCEPTUAL
            )
            
            if isinstance(relationship_type, str):
                try:
                    relationship_type = RelationshipType(relationship_type)
                except ValueError:
                    relationship_type = RelationshipType.CONCEPTUAL
            
            self.network.add_link(
                memory_id_1=memory_id,
                memory_id_2=related_id,
                relationship_type=relationship_type,
                strength=0.7,
                metadata={'created_from': 'memory_creation_event'}
            )
            
            logger.debug(f"Created link from {memory_id} to {related_id}")
    
    async def _handle_memory_updated(self, event: BaseEvent) -> None:
        """Handle memory updated event - strengthen existing links."""
        memory_id = event.metadata.get('memory_id')
        
        if not memory_id:
            return
        
        # Strengthen links for updated memories (indicates importance)
        # Get all links for this memory
        with self.network.lock:
            if memory_id in self.network.link_index:
                for related_id in self.network.link_index[memory_id]:
                    link = self.network.get_link(memory_id, related_id)
                    if link:
                        link.reinforce(0.05)
                        logger.debug(f"Reinforced link {memory_id} <-> {related_id}")
    
    async def _handle_reflection_completed(self, event: BaseEvent) -> None:
        """Handle reflection completed event - apply decay to old links."""
        # Apply time-based decay to network
        self.network.decay_all_links(0.02)
        
        logger.debug("Applied link decay during reflection")
