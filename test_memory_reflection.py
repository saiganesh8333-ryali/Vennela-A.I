"""
Comprehensive Tests for Memory Reflection Cycle (Phase C)

Tests for:
- Memory consolidation engine and phases
- Importance scoring and classification
- Semantic network building and analysis
- Event integration and async handling
- Thread safety
- Error handling

Author: Vennela A.I Evolution
"""

import asyncio
import logging
import time
import unittest
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List

from memory_reflection_engine import (
    MemoryConsolidationEngine,
    ConsolidationContext,
    ConsolidationPhase,
    MemoryRecord,
    ReflectionHandler
)
from memory_importance_analyzer import (
    ImportanceAnalyzer,
    ImportanceLevel,
    ImportanceScoringHandler,
    MemoryAccessRecord
)
from memory_semantic_network import (
    SemanticNetwork,
    SemanticLink,
    RelationshipType,
    SemanticLinkingHandler
)
from event_types import BaseEvent, EventType

logger = logging.getLogger(__name__)


# ===========================
# CONSOLIDATION ENGINE TESTS
# ===========================

class TestMemoryConsolidationEngine(unittest.TestCase):
    """Tests for MemoryConsolidationEngine."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.engine = MemoryConsolidationEngine()
        self.user_id = "test_user_123"
    
    def test_engine_initialization(self):
        """Test engine initializes correctly."""
        self.assertIsNotNone(self.engine.contexts)
        self.assertEqual(len(self.engine.contexts), 0)
    
    def test_get_or_create_context(self):
        """Test context creation and retrieval."""
        context = self.engine.get_or_create_context(self.user_id)
        self.assertIsNotNone(context)
        self.assertEqual(context.user_id, self.user_id)
        
        # Should return same context on second call
        context2 = self.engine.get_or_create_context(self.user_id)
        self.assertIs(context, context2)
    
    def test_add_working_memory(self):
        """Test adding working memory."""
        record = self.engine.add_working_memory(
            user_id=self.user_id,
            memory_id="mem1",
            content="Test memory content",
            memory_type="episodic",
            importance=0.7
        )
        
        self.assertEqual(record.memory_id, "mem1")
        self.assertEqual(record.content, "Test memory content")
        self.assertEqual(record.importance, 0.7)
        
        # Verify it's in working memory
        context = self.engine.get_or_create_context(self.user_id)
        self.assertIn("mem1", context.working_memories)
    
    def test_add_working_memory_validation(self):
        """Test validation of working memory parameters."""
        with self.assertRaises(ValueError):
            self.engine.add_working_memory(
                user_id=self.user_id,
                memory_id="",
                content="Test",
                memory_type="episodic"
            )
        
        with self.assertRaises(ValueError):
            self.engine.add_working_memory(
                user_id=self.user_id,
                memory_id="mem2",
                content="Test",
                memory_type="episodic",
                importance=1.5  # Invalid: > 1
            )
    
    def test_consolidation_context_stats(self):
        """Test consolidation context statistics."""
        context = self.engine.get_or_create_context(self.user_id)
        
        # Add some memories
        for i in range(3):
            self.engine.add_working_memory(
                user_id=self.user_id,
                memory_id=f"mem{i}",
                content=f"Memory {i}",
                memory_type="episodic"
            )
        
        stats = context.get_stats()
        self.assertEqual(stats['working_memories_count'], 3)
        self.assertEqual(stats['episodic_memories_count'], 0)
    
    def test_short_term_consolidation_age_threshold(self):
        """Test short-term to episodic consolidation with age threshold."""
        # Add old memory
        old_time = time.time() - 400  # Older than threshold
        context = self.engine.get_or_create_context(self.user_id)
        
        record = MemoryRecord(
            memory_id="old_mem",
            content="Old memory",
            memory_type="episodic",
            timestamp=old_time,
            importance=0.5
        )
        context.working_memories["old_mem"] = record
        
        # Run consolidation
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            self.engine.consolidate_short_term(self.user_id)
        )
        loop.close()
        
        self.assertEqual(result['consolidated_count'], 1)
        self.assertIn("old_mem", context.episodic_memories)
        self.assertNotIn("old_mem", context.working_memories)
    
    def test_short_term_consolidation_importance_threshold(self):
        """Test that low importance memories don't consolidate."""
        context = self.engine.get_or_create_context(self.user_id)
        
        # Add old but low importance memory
        old_time = time.time() - 400
        record = MemoryRecord(
            memory_id="low_importance",
            content="Low importance",
            memory_type="episodic",
            timestamp=old_time,
            importance=0.1  # Below MIN_IMPORTANCE_FOR_CONSOLIDATION
        )
        context.working_memories["low_importance"] = record
        
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            self.engine.consolidate_short_term(self.user_id)
        )
        loop.close()
        
        # Should not be consolidated
        self.assertEqual(result['consolidated_count'], 0)
        self.assertIn("low_importance", context.working_memories)
    
    def test_semantic_consolidation(self):
        """Test consolidation to semantic patterns."""
        context = self.engine.get_or_create_context(self.user_id)
        
        # Add episodic memories of same type
        for i in range(3):
            record = MemoryRecord(
                memory_id=f"episodic_{i}",
                content=f"Episodic memory {i}",
                memory_type="conversation",
                timestamp=time.time(),
                importance=0.6
            )
            record.current_phase = ConsolidationPhase.EPISODIC
            context.episodic_memories[f"episodic_{i}"] = record
        
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            self.engine.consolidate_to_semantic(self.user_id)
        )
        loop.close()
        
        self.assertEqual(result['patterns_extracted'], 1)
        self.assertEqual(len(context.semantic_patterns), 1)
    
    def test_summary_consolidation(self):
        """Test summary consolidation."""
        context = self.engine.get_or_create_context(self.user_id)
        
        # Add episodic memories
        for i in range(5):
            record = MemoryRecord(
                memory_id=f"mem_{i}",
                content=f"Memory {i}",
                memory_type="episodic",
                timestamp=time.time(),
                importance=0.5 + i * 0.1
            )
            record.current_phase = ConsolidationPhase.EPISODIC
            context.episodic_memories[f"mem_{i}"] = record
        
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            self.engine.consolidate_to_summary(self.user_id)
        )
        loop.close()
        
        self.assertTrue(result['summary_created'])
        self.assertIsNotNone(context.summary_data)
        self.assertIn('statistics', context.summary_data)
    
    def test_full_consolidation_cycle(self):
        """Test complete consolidation cycle."""
        # Setup memories in working state
        for i in range(2):
            self.engine.add_working_memory(
                user_id=self.user_id,
                memory_id=f"mem_{i}",
                content=f"Memory {i}",
                memory_type="episodic",
                importance=0.6
            )
        
        # Age the memories
        context = self.engine.get_or_create_context(self.user_id)
        for record in context.working_memories.values():
            record.timestamp = time.time() - 400
        
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            self.engine.run_full_consolidation_cycle(self.user_id)
        )
        loop.close()
        
        self.assertIn('phases', result)
        self.assertIn('short_term', result['phases'])
        self.assertIn('semantic', result['phases'])
        self.assertIn('summary', result['phases'])


# ===========================
# IMPORTANCE ANALYZER TESTS
# ===========================

class TestImportanceAnalyzer(unittest.TestCase):
    """Tests for ImportanceAnalyzer."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = ImportanceAnalyzer()
        self.memory_id = "test_mem"
    
    def test_analyzer_initialization(self):
        """Test analyzer initializes correctly."""
        self.assertIsNotNone(self.analyzer.memory_records)
        self.assertEqual(len(self.analyzer.memory_records), 0)
    
    def test_track_memory(self):
        """Test memory tracking."""
        record = self.analyzer.track_memory(self.memory_id)
        
        self.assertIsNotNone(record)
        self.assertEqual(record.memory_id, self.memory_id)
        self.assertIn(self.memory_id, self.analyzer.memory_records)
    
    def test_track_memory_validation(self):
        """Test memory tracking validation."""
        with self.assertRaises(ValueError):
            self.analyzer.track_memory("")
    
    def test_record_interaction(self):
        """Test recording interactions."""
        self.analyzer.track_memory(self.memory_id)
        self.analyzer.record_interaction(self.memory_id, "retrieve")
        
        record = self.analyzer.memory_records[self.memory_id]
        self.assertEqual(record.access_count, 1)
        self.assertIn("retrieve", record.interaction_events)
    
    def test_frequency_score(self):
        """Test frequency score calculation."""
        self.analyzer.track_memory(self.memory_id)
        record = self.analyzer.memory_records[self.memory_id]
        
        # No accesses
        score = self.analyzer._calculate_frequency_score(record)
        self.assertEqual(score, 0.0)
        
        # Add accesses
        for _ in range(10):
            record.add_interaction("retrieve")
        
        score = self.analyzer._calculate_frequency_score(record)
        self.assertEqual(score, 1.0)  # At baseline
    
    def test_recency_score(self):
        """Test recency score calculation."""
        self.analyzer.track_memory(self.memory_id)
        record = self.analyzer.memory_records[self.memory_id]
        
        # Fresh memory
        score = self.analyzer._calculate_recency_score(record)
        self.assertGreater(score, 0.9)
        
        # Simulate old access
        record.last_access_time = time.time() - 86400  # 1 day ago
        score = self.analyzer._calculate_recency_score(record)
        self.assertLess(score, 0.6)
    
    def test_importance_scoring(self):
        """Test overall importance scoring."""
        self.analyzer.track_memory(self.memory_id)
        
        # Initial score
        score1 = self.analyzer.score_memory(self.memory_id)
        self.assertGreaterEqual(score1, 0.0)
        self.assertLessEqual(score1, 1.0)
        
        # Score after interactions
        record = self.analyzer.memory_records[self.memory_id]
        for _ in range(5):
            record.add_interaction("retrieve")
        
        score2 = self.analyzer.score_memory(self.memory_id, include_cache=False)
        self.assertGreater(score2, score1)  # Should increase with more access
    
    def test_importance_classification(self):
        """Test importance level classification."""
        self.assertEqual(
            self.analyzer.classify_importance(0.9),
            ImportanceLevel.CRITICAL
        )
        self.assertEqual(
            self.analyzer.classify_importance(0.7),
            ImportanceLevel.HIGH
        )
        self.assertEqual(
            self.analyzer.classify_importance(0.5),
            ImportanceLevel.MEDIUM
        )
        self.assertEqual(
            self.analyzer.classify_importance(0.3),
            ImportanceLevel.LOW
        )
        self.assertEqual(
            self.analyzer.classify_importance(0.1),
            ImportanceLevel.MINIMAL
        )
    
    def test_get_important_memories(self):
        """Test retrieval of important memories."""
        # Add multiple memories with different importance
        for i in range(5):
            memory_id = f"mem_{i}"
            self.analyzer.track_memory(memory_id)
            record = self.analyzer.memory_records[memory_id]
            
            # Add interactions to increase importance
            for _ in range(i * 2):
                record.add_interaction("retrieve")
        
        important = self.analyzer.get_important_memories(min_importance=0.3, limit=10)
        self.assertGreaterEqual(len(important), 0)
        
        # Should be sorted by importance
        for i in range(len(important) - 1):
            self.assertGreaterEqual(
                important[i]['importance_score'],
                important[i + 1]['importance_score']
            )
    
    def test_memory_details(self):
        """Test detailed memory information."""
        self.analyzer.track_memory(self.memory_id)
        record = self.analyzer.memory_records[self.memory_id]
        record.add_interaction("retrieve")
        record.emotional_tags = ["important"]
        
        details = self.analyzer.get_memory_details(self.memory_id)
        
        self.assertEqual(details['memory_id'], self.memory_id)
        self.assertIn('factors', details)
        self.assertIn('overall_score', details)
        self.assertIn('metadata', details)
    
    def test_analyzer_stats(self):
        """Test analyzer statistics."""
        for i in range(3):
            self.analyzer.track_memory(f"mem_{i}")
        
        stats = self.analyzer.get_stats()
        self.assertEqual(stats['total_memories_tracked'], 3)
        self.assertIn('average_importance', stats)
        self.assertIn('memories_by_level', stats)


# ===========================
# SEMANTIC NETWORK TESTS
# ===========================

class TestSemanticNetwork(unittest.TestCase):
    """Tests for SemanticNetwork."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.network = SemanticNetwork()
        self.mem1 = "memory_1"
        self.mem2 = "memory_2"
        self.mem3 = "memory_3"
    
    def test_network_initialization(self):
        """Test network initializes correctly."""
        self.assertIsNotNone(self.network.links)
        self.assertEqual(len(self.network.links), 0)
    
    def test_add_link(self):
        """Test adding semantic links."""
        link = self.network.add_link(
            memory_id_1=self.mem1,
            memory_id_2=self.mem2,
            relationship_type=RelationshipType.CAUSAL,
            strength=0.8
        )
        
        self.assertIsNotNone(link)
        self.assertEqual(link.strength, 0.8)
        self.assertEqual(len(self.network.links), 1)
    
    def test_add_link_validation(self):
        """Test link validation."""
        with self.assertRaises(ValueError):
            self.network.add_link(
                memory_id_1="",
                memory_id_2=self.mem2,
                relationship_type=RelationshipType.CAUSAL
            )
        
        with self.assertRaises(ValueError):
            self.network.add_link(
                memory_id_1=self.mem1,
                memory_id_2=self.mem1,  # Same memory
                relationship_type=RelationshipType.CAUSAL
            )
    
    def test_link_strength_update(self):
        """Test updating link strength."""
        link = self.network.add_link(
            memory_id_1=self.mem1,
            memory_id_2=self.mem2,
            relationship_type=RelationshipType.CONCEPTUAL,
            strength=0.5
        )
        
        link.update_strength(0.8)
        self.assertEqual(link.strength, 0.8)
    
    def test_link_reinforce(self):
        """Test reinforcing links."""
        link = self.network.add_link(
            memory_id_1=self.mem1,
            memory_id_2=self.mem2,
            relationship_type=RelationshipType.TEMPORAL,
            strength=0.5
        )
        
        link.reinforce(0.2)
        self.assertEqual(link.strength, 0.7)
        
        # Test max bound
        link.reinforce(0.5)
        self.assertEqual(link.strength, 1.0)
    
    def test_link_decay(self):
        """Test decaying links."""
        link = self.network.add_link(
            memory_id_1=self.mem1,
            memory_id_2=self.mem2,
            relationship_type=RelationshipType.EMOTIONAL,
            strength=0.7
        )
        
        link.decay(0.2)
        self.assertEqual(link.strength, 0.5)
        
        # Test min bound
        link.decay(0.7)
        self.assertEqual(link.strength, 0.0)
    
    def test_get_link(self):
        """Test retrieving a specific link."""
        link1 = self.network.add_link(
            memory_id_1=self.mem1,
            memory_id_2=self.mem2,
            relationship_type=RelationshipType.CAUSAL
        )
        
        retrieved = self.network.get_link(self.mem1, self.mem2)
        self.assertEqual(retrieved.link_id, link1.link_id)
    
    def test_find_related(self):
        """Test finding related memories."""
        # Create a network: mem1 -> mem2 -> mem3
        self.network.add_link(
            memory_id_1=self.mem1,
            memory_id_2=self.mem2,
            relationship_type=RelationshipType.CAUSAL,
            bidirectional=True
        )
        self.network.add_link(
            memory_id_1=self.mem2,
            memory_id_2=self.mem3,
            relationship_type=RelationshipType.TEMPORAL,
            bidirectional=True
        )
        
        # Find related to mem1
        related = self.network.find_related(self.mem1, max_depth=2)
        
        self.assertEqual(related['memory_id'], self.mem1)
        self.assertGreater(related['total_count'], 0)
    
    def test_remove_link(self):
        """Test removing links."""
        self.network.add_link(
            memory_id_1=self.mem1,
            memory_id_2=self.mem2,
            relationship_type=RelationshipType.CAUSAL
        )
        
        initial_count = len(self.network.links)
        removed = self.network.remove_link(self.mem1, self.mem2)
        
        self.assertTrue(removed)
        self.assertEqual(len(self.network.links), initial_count - 1)
    
    def test_network_stats(self):
        """Test network statistics."""
        # Create a small network
        for i in range(3):
            for j in range(i + 1, 3):
                self.network.add_link(
                    memory_id_1=f"mem_{i}",
                    memory_id_2=f"mem_{j}",
                    relationship_type=RelationshipType.CONCEPTUAL
                )
        
        stats = self.network.get_network_stats()
        
        self.assertGreater(stats['total_links'], 0)
        self.assertGreater(stats['total_memories'], 0)
        self.assertIn('by_type', stats)
    
    def test_reinforce_path(self):
        """Test reinforcing a memory path."""
        path = [self.mem1, self.mem2, self.mem3]
        
        # Create links
        self.network.add_link(
            memory_id_1=self.mem1,
            memory_id_2=self.mem2,
            relationship_type=RelationshipType.CAUSAL,
            strength=0.5
        )
        self.network.add_link(
            memory_id_1=self.mem2,
            memory_id_2=self.mem3,
            relationship_type=RelationshipType.CAUSAL,
            strength=0.5
        )
        
        reinforced = self.network.reinforce_path(path, factor=0.2)
        
        self.assertEqual(reinforced, 2)
        
        # Check links were reinforced
        link1 = self.network.get_link(self.mem1, self.mem2)
        self.assertEqual(link1.strength, 0.7)
    
    def test_decay_all_links(self):
        """Test decaying all links."""
        # Create links
        for i in range(3):
            self.network.add_link(
                memory_id_1=f"mem_{i}",
                memory_id_2=f"mem_{(i+1)%3}",
                relationship_type=RelationshipType.TEMPORAL,
                strength=0.8
            )
        
        decayed = self.network.decay_all_links(0.1)
        
        self.assertEqual(decayed, 3)
        
        # Check all links decayed
        for link in self.network.links.values():
            self.assertEqual(link.strength, 0.7)


# ===========================
# EVENT INTEGRATION TESTS
# ===========================

class TestEventIntegration(unittest.TestCase):
    """Tests for event handler integration."""
    
    def test_reflection_handler_initialization(self):
        """Test ReflectionHandler initializes."""
        handler = ReflectionHandler()
        
        self.assertIsNotNone(handler.engine)
        self.assertEqual(handler.name, "ReflectionHandler")
        self.assertIn(EventType.MEMORY_CREATED, handler.event_types)
    
    def test_importance_scoring_handler_initialization(self):
        """Test ImportanceScoringHandler initializes."""
        handler = ImportanceScoringHandler()
        
        self.assertIsNotNone(handler.analyzer)
        self.assertEqual(handler.name, "ImportanceScoringHandler")
        self.assertIn(EventType.MEMORY_CREATED, handler.event_types)
    
    def test_semantic_linking_handler_initialization(self):
        """Test SemanticLinkingHandler initializes."""
        handler = SemanticLinkingHandler()
        
        self.assertIsNotNone(handler.network)
        self.assertEqual(handler.name, "SemanticLinkingHandler")
        self.assertIn(EventType.MEMORY_CREATED, handler.event_types)


# ===========================
# THREAD SAFETY TESTS
# ===========================

class TestThreadSafety(unittest.TestCase):
    """Tests for thread safety."""
    
    def test_consolidation_context_thread_safety(self):
        """Test thread-safe consolidation context."""
        engine = MemoryConsolidationEngine()
        user_id = "test_user"
        results = []
        
        def add_memories(start, end):
            for i in range(start, end):
                engine.add_working_memory(
                    user_id=user_id,
                    memory_id=f"mem_{i}",
                    content=f"Memory {i}",
                    memory_type="episodic"
                )
            
            context = engine.get_or_create_context(user_id)
            results.append(len(context.working_memories))
        
        # Run concurrent additions
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(add_memories, i*10, (i+1)*10)
                for i in range(5)
            ]
            for future in concurrent.futures.as_completed(futures):
                future.result()
        
        # Verify all memories were added
        context = engine.get_or_create_context(user_id)
        self.assertEqual(len(context.working_memories), 50)
    
    def test_semantic_network_thread_safety(self):
        """Test thread-safe semantic network."""
        network = SemanticNetwork()
        
        def add_links(start, end):
            for i in range(start, end):
                network.add_link(
                    memory_id_1=f"mem_{i}",
                    memory_id_2=f"mem_{i+1}",
                    relationship_type=RelationshipType.TEMPORAL
                )
        
        # Run concurrent additions
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(add_links, i*10, (i+1)*10)
                for i in range(5)
            ]
            for future in concurrent.futures.as_completed(futures):
                future.result()
        
        # Verify links were added
        self.assertGreater(len(network.links), 0)


# ===========================
# INTEGRATION TESTS
# ===========================

class TestFullIntegration(unittest.TestCase):
    """Integration tests for Phase C."""
    
    def test_complete_memory_lifecycle(self):
        """Test complete memory lifecycle through all components."""
        engine = MemoryConsolidationEngine()
        analyzer = ImportanceAnalyzer()
        network = SemanticNetwork()
        
        user_id = "integration_test_user"
        
        # 1. Create working memory
        engine.add_working_memory(
            user_id=user_id,
            memory_id="mem_1",
            content="Test memory 1",
            memory_type="episodic",
            importance=0.7
        )
        
        # 2. Track in analyzer
        analyzer.track_memory("mem_1")
        analyzer.record_interaction("mem_1", "retrieve")
        
        # 3. Get importance score
        score = analyzer.score_memory("mem_1")
        self.assertGreater(score, 0.0)
        
        # 4. Create network links
        engine.add_working_memory(
            user_id=user_id,
            memory_id="mem_2",
            content="Test memory 2",
            memory_type="episodic",
            importance=0.6
        )
        
        network.add_link(
            memory_id_1="mem_1",
            memory_id_2="mem_2",
            relationship_type=RelationshipType.CAUSAL
        )
        
        # 5. Run consolidation
        context = engine.get_or_create_context(user_id)
        for record in context.working_memories.values():
            record.timestamp = time.time() - 400
        
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            engine.run_full_consolidation_cycle(user_id)
        )
        loop.close()
        
        # 6. Verify all components updated
        self.assertIn('phases', result)
        self.assertIn('mem_1', context.episodic_memories)
        self.assertIn('mem_2', context.episodic_memories)


if __name__ == '__main__':
    # Configure logging for tests
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run tests
    unittest.main(verbosity=2)
