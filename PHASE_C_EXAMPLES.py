"""
Phase C: Memory Reflection Cycle - Usage Examples and Demonstrations

This module shows how to use Phase C components in real applications.
"""

import asyncio
import time
from typing import Dict, Any, List

# Imports from Phase C
from memory_reflection_engine import (
    MemoryConsolidationEngine,
    ReflectionHandler,
    ConsolidationPhase
)
from memory_importance_analyzer import (
    ImportanceAnalyzer,
    ImportanceScoringHandler,
    ImportanceLevel
)
from memory_semantic_network import (
    SemanticNetwork,
    RelationshipType,
    SemanticLinkingHandler
)
from event_types import EventType, BaseEvent


# ============================================================================
# EXAMPLE 1: Basic Memory Consolidation
# ============================================================================

async def example_basic_consolidation():
    """
    Demonstrates basic memory consolidation workflow.
    
    Process:
    1. Create an engine
    2. Add working memories
    3. Age them (simulate time passing)
    4. Run consolidation cycle
    5. Inspect results
    """
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic Memory Consolidation")
    print("="*70)
    
    # Initialize engine
    engine = MemoryConsolidationEngine()
    user_id = "user_demo_1"
    
    print(f"\n1. Creating engine and adding memories for {user_id}...")
    
    # Add some memories
    memories = [
        ("mem_001", "User asked about Python programming", "question", 0.8),
        ("mem_002", "Discussed async/await patterns", "discussion", 0.7),
        ("mem_003", "Shared code example for threading", "tutorial", 0.6),
    ]
    
    for mem_id, content, mem_type, importance in memories:
        record = engine.add_working_memory(
            user_id=user_id,
            memory_id=mem_id,
            content=content,
            memory_type=mem_type,
            importance=importance
        )
        print(f"   ✓ Added: {mem_id} (importance: {importance})")
    
    # Simulate time passing - age the memories
    print(f"\n2. Aging memories (simulating time passage)...")
    context = engine.get_or_create_context(user_id)
    for record in context.working_memories.values():
        record.timestamp = time.time() - 400  # 400 seconds old
    print(f"   ✓ All memories aged to 400 seconds")
    
    # Run consolidation cycle
    print(f"\n3. Running full consolidation cycle...")
    result = await engine.run_full_consolidation_cycle(user_id)
    
    print(f"\n4. Consolidation Results:")
    print(f"   Short-term → Episodic: {result['phases']['short_term']['consolidated_count']} memories")
    print(f"   Episodic → Semantic: {result['phases']['semantic']['patterns_extracted']} patterns")
    print(f"   Summary Created: {result['phases']['summary']['summary_created']}")
    print(f"   Total Duration: {result['cycle_duration']:.3f}s")
    
    # Inspect final state
    print(f"\n5. Final Memory State:")
    print(f"   Working Memories: {len(context.working_memories)}")
    print(f"   Episodic Memories: {len(context.episodic_memories)}")
    print(f"   Semantic Patterns: {len(context.semantic_patterns)}")
    
    if context.semantic_patterns:
        pattern = context.semantic_patterns[0]
        print(f"\n   First Pattern:")
        print(f"     ID: {pattern['pattern_id']}")
        print(f"     Type: {pattern['memory_type']}")
        print(f"     Source Memories: {pattern['memory_count']}")
        print(f"     Avg Importance: {pattern['avg_importance']:.2f}")
    
    return context


# ============================================================================
# EXAMPLE 2: Importance Scoring and Classification
# ============================================================================

async def example_importance_scoring():
    """
    Demonstrates importance analysis and scoring.
    
    Shows:
    1. Memory tracking
    2. Recording various interactions
    3. Computing importance scores
    4. Classifying importance levels
    5. Retrieving important memories
    """
    print("\n" + "="*70)
    print("EXAMPLE 2: Importance Scoring and Classification")
    print("="*70)
    
    # Initialize analyzer
    analyzer = ImportanceAnalyzer()
    
    print("\n1. Tracking memories with different interaction patterns...")
    
    # Simulate different memory access patterns
    test_memories = {
        "mem_frequently_accessed": 15,  # 15 accesses
        "mem_recent": 3,                # 3 accesses, just accessed
        "mem_important_interaction": 5, # 5 updates (high value interactions)
        "mem_emotional": 2,             # 2 accesses, has emotional tag
        "mem_old": 1,                   # 1 access, old
    }
    
    for mem_id, access_count in test_memories.items():
        record = analyzer.track_memory(mem_id)
        
        # Add interactions
        for i in range(access_count):
            if "important" in mem_id:
                analyzer.record_interaction(mem_id, "update")
            else:
                analyzer.record_interaction(mem_id, "retrieve")
        
        # Add emotional tags to one
        if "emotional" in mem_id:
            record.emotional_tags = ["positive", "meaningful"]
        
        # Age one memory
        if "old" in mem_id:
            record.last_access_time = time.time() - 86400  # 1 day ago
        
        print(f"   ✓ {mem_id}: {access_count} interactions")
    
    # Analyze importance
    print("\n2. Computing importance scores...")
    scores = {}
    for mem_id in test_memories.keys():
        score = analyzer.score_memory(mem_id, include_cache=False)
        level = analyzer.classify_importance(score)
        scores[mem_id] = (score, level)
        print(f"   {mem_id}: {score:.3f} ({level.value})")
    
    # Get detailed breakdown for one memory
    print("\n3. Detailed factor breakdown for 'mem_frequently_accessed':")
    details = analyzer.get_memory_details("mem_frequently_accessed")
    factors = details['factors']
    print(f"   Frequency Score: {factors['frequency_score']:.3f}")
    print(f"   Recency Score: {factors['recency_score']:.3f}")
    print(f"   Interaction Score: {factors['interaction_score']:.3f}")
    print(f"   Relevance Score: {factors['relevance_score']:.3f}")
    print(f"   Emotional Weight: {factors['emotional_weight']:.3f}")
    print(f"   → Overall: {details['overall_score']:.3f}")
    
    # Get important memories
    print("\n4. Top important memories (threshold: 0.3):")
    important = analyzer.get_important_memories(min_importance=0.3, limit=10)
    for i, mem in enumerate(important, 1):
        print(f"   {i}. {mem['memory_id']}: {mem['importance_score']:.3f} ({mem['importance_level']})")
    
    # Statistics
    print("\n5. Analyzer Statistics:")
    stats = analyzer.get_stats()
    print(f"   Total Memories Tracked: {stats['total_memories_tracked']}")
    print(f"   Average Importance: {stats['average_importance']:.3f}")
    print(f"   Critical Memories: {stats['memories_by_level']['critical']}")
    print(f"   High Memories: {stats['memories_by_level']['high']}")
    print(f"   Medium Memories: {stats['memories_by_level']['medium']}")
    
    return analyzer


# ============================================================================
# EXAMPLE 3: Semantic Network Building
# ============================================================================

async def example_semantic_network():
    """
    Demonstrates semantic network construction and analysis.
    
    Shows:
    1. Creating semantic links between memories
    2. Finding related memories
    3. Building and analyzing network structure
    4. Reinforcing important paths
    """
    print("\n" + "="*70)
    print("EXAMPLE 3: Semantic Network Building and Analysis")
    print("="*70)
    
    # Initialize network
    network = SemanticNetwork()
    
    print("\n1. Building semantic network...")
    
    # Define a knowledge structure
    links = [
        ("memory_python", "memory_async", RelationshipType.CONCEPTUAL, 0.8),
        ("memory_async", "memory_threading", RelationshipType.SIMILAR, 0.7),
        ("memory_threading", "memory_performance", RelationshipType.CAUSAL, 0.8),
        ("memory_python", "memory_performance", RelationshipType.REFERENCE, 0.6),
        ("memory_performance", "memory_optimization", RelationshipType.TEMPORAL, 0.7),
        ("memory_optimization", "memory_profiling", RelationshipType.CAUSAL, 0.8),
    ]
    
    for mem1, mem2, rel_type, strength in links:
        link = network.add_link(
            memory_id_1=mem1,
            memory_id_2=mem2,
            relationship_type=rel_type,
            strength=strength,
            bidirectional=True
        )
        print(f"   ✓ {mem1} --[{rel_type.value}]--> {mem2} (strength: {strength})")
    
    # Find related memories
    print("\n2. Finding related memories (BFS exploration)...")
    related = network.find_related("memory_python", max_depth=3)
    
    print(f"\n   Starting from: memory_python")
    print(f"   Total related: {related['total_count']}")
    
    for depth, memories in related['by_depth'].items():
        if memories:
            print(f"\n   Depth {depth}:")
            for mem in memories:
                print(f"     - {mem['memory_id']} ({mem['relationship_type']})")
    
    # Analyze network structure
    print("\n3. Network Statistics:")
    stats = network.get_network_stats()
    print(f"   Total Links: {stats['total_links']}")
    print(f"   Total Memories: {stats['total_memories']}")
    print(f"   Average Connections: {stats['average_connections']:.2f}")
    print(f"   Network Density: {stats['network_density']:.3f}")
    print(f"   Average Link Strength: {stats['average_link_strength']:.3f}")
    print(f"   Links by Type:")
    for rel_type, count in stats['by_type'].items():
        print(f"     - {rel_type}: {count}")
    
    # Reinforce an important path
    print("\n4. Reinforcing important knowledge path...")
    path = ["memory_python", "memory_async", "memory_threading"]
    reinforced = network.reinforce_path(path, factor=0.15)
    print(f"   ✓ Reinforced {reinforced} links in knowledge path")
    
    # Show strongest links
    print("\n5. Strongest links in network:")
    strongest = network.get_strongest_links(limit=3)
    for i, link in enumerate(strongest, 1):
        print(f"   {i}. {link['memory_id_1']} → {link['memory_id_2']}: {link['strength']:.2f}")
    
    return network


# ============================================================================
# EXAMPLE 4: Full Integration - Complete Workflow
# ============================================================================

async def example_full_integration():
    """
    Demonstrates complete workflow using all Phase C components together.
    
    Shows:
    1. Creating consolidated memories
    2. Tracking importance
    3. Building network relationships
    4. Full analysis pipeline
    """
    print("\n" + "="*70)
    print("EXAMPLE 4: Full Integration - Complete Workflow")
    print("="*70)
    
    # Initialize all components
    engine = MemoryConsolidationEngine()
    analyzer = ImportanceAnalyzer()
    network = SemanticNetwork()
    
    user_id = "integration_user"
    
    print(f"\n1. Creating conversation memories for {user_id}...")
    
    # Simulate a conversation with multiple topics
    conversation_memories = [
        ("conv_greeting", "User greeted and introduced themselves", "greeting", 0.5),
        ("conv_question_1", "Asked about Python async programming", "question", 0.8),
        ("conv_answer_1", "Explained async/await concepts", "response", 0.8),
        ("conv_code_example", "Shared practical async code example", "example", 0.9),
        ("conv_follow_up", "User asked about error handling", "question", 0.7),
        ("conv_solution", "Provided error handling strategy", "response", 0.8),
    ]
    
    memory_ids = []
    for mem_id, content, mem_type, importance in conversation_memories:
        # Add to consolidation engine
        record = engine.add_working_memory(
            user_id=user_id,
            memory_id=mem_id,
            content=content,
            memory_type=mem_type,
            importance=importance
        )
        memory_ids.append(mem_id)
        
        # Track in importance analyzer
        analyzer.track_memory(mem_id)
        if mem_type in ["example", "solution"]:
            analyzer.record_interaction(mem_id, "update")  # High-value updates
        
        print(f"   ✓ {mem_id} (importance: {importance})")
    
    # Build semantic relationships
    print(f"\n2. Building conversation structure (semantic network)...")
    
    # Question-Answer pairs
    network.add_link("conv_question_1", "conv_answer_1", RelationshipType.CAUSAL)
    network.add_link("conv_answer_1", "conv_code_example", RelationshipType.TEMPORAL)
    network.add_link("conv_follow_up", "conv_solution", RelationshipType.CAUSAL)
    network.add_link("conv_code_example", "conv_follow_up", RelationshipType.REFERENCE)
    
    # Conceptual connections
    network.add_link("conv_answer_1", "conv_solution", RelationshipType.CONCEPTUAL)
    
    print(f"   ✓ Created {len(network.links)} semantic links")
    
    # Age memories and consolidate
    print(f"\n3. Consolidating memories (simulating time passage)...")
    context = engine.get_or_create_context(user_id)
    for record in context.working_memories.values():
        record.timestamp = time.time() - 400
    
    result = await engine.run_full_consolidation_cycle(user_id)
    
    print(f"   ✓ Consolidated {result['phases']['short_term']['consolidated_count']} memories")
    print(f"   ✓ Extracted {result['phases']['semantic']['patterns_extracted']} patterns")
    print(f"   ✓ Created summary: {result['phases']['summary']['summary_created']}")
    
    # Analyze importance distribution
    print(f"\n4. Analyzing importance distribution...")
    important = analyzer.get_important_memories(min_importance=0.5, limit=10)
    
    print(f"   Important memories (score ≥ 0.5):")
    for mem in important:
        print(f"     {mem['memory_id']}: {mem['importance_score']:.3f}")
    
    # Analyze network
    print(f"\n5. Network analysis:")
    stats = network.get_network_stats()
    print(f"   Total links: {stats['total_links']}")
    print(f"   Memory nodes: {stats['total_memories']}")
    print(f"   Network density: {stats['network_density']:.3f}")
    
    # Find related memories from network perspective
    print(f"\n6. Tracing conversation flow...")
    related = network.find_related("conv_question_1", max_depth=3)
    print(f"   Related to 'conv_question_1': {related['total_count']} memories")
    
    # Final summary
    print(f"\n7. INTEGRATION SUMMARY:")
    print(f"   ├─ Engine State:")
    print(f"   │  ├─ Working: {len(context.working_memories)}")
    print(f"   │  ├─ Episodic: {len(context.episodic_memories)}")
    print(f"   │  └─ Patterns: {len(context.semantic_patterns)}")
    print(f"   ├─ Analyzer State:")
    stats = analyzer.get_stats()
    print(f"   │  ├─ Tracked: {stats['total_memories_tracked']}")
    print(f"   │  └─ Avg Importance: {stats['average_importance']:.3f}")
    print(f"   └─ Network State:")
    print(f"      ├─ Links: {stats['total_links']}")
    print(f"      └─ Density: {stats['network_density']:.3f}")


# ============================================================================
# EXAMPLE 5: Event Handler Usage
# ============================================================================

async def example_event_handlers():
    """
    Demonstrates using Phase C components with the event bus.
    
    Shows how handlers automatically process events.
    """
    print("\n" + "="*70)
    print("EXAMPLE 5: Event Handler Integration")
    print("="*70)
    
    # Initialize handlers
    reflection_handler = ReflectionHandler()
    scoring_handler = ImportanceScoringHandler()
    linking_handler = SemanticLinkingHandler()
    
    print("\n1. Event Handlers Initialized:")
    print(f"   ✓ {reflection_handler.name}")
    print(f"     Subscribes to: {[et.value for et in reflection_handler.event_types]}")
    print(f"\n   ✓ {scoring_handler.name}")
    print(f"     Subscribes to: {[et.value for et in scoring_handler.event_types]}")
    print(f"\n   ✓ {linking_handler.name}")
    print(f"     Subscribes to: {[et.value for et in linking_handler.event_types]}")
    
    print("\n2. Usage in Event Bus:")
    print(f"   These handlers would be registered with the event bus:")
    print(f"   ```python")
    print(f"   event_bus.register_handler(reflection_handler)")
    print(f"   event_bus.register_handler(scoring_handler)")
    print(f"   event_bus.register_handler(linking_handler)")
    print(f"   ```")
    
    print("\n3. Automatic Processing:")
    print(f"   When events are published:")
    print(f"   - MEMORY_CREATED → All 3 handlers process it")
    print(f"   - MEMORY_UPDATED → Scoring & Linking handlers respond")
    print(f"   - REFLECTION_STARTED → Reflection handler triggers consolidation")
    print(f"   - REFLECTION_COMPLETED → Linking handler applies decay")


# ============================================================================
# MAIN RUNNER
# ============================================================================

async def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("PHASE C: MEMORY REFLECTION CYCLE - USAGE EXAMPLES")
    print("="*70)
    
    try:
        # Run examples
        await example_basic_consolidation()
        await example_importance_scoring()
        await example_semantic_network()
        await example_full_integration()
        await example_event_handlers()
        
        print("\n" + "="*70)
        print("ALL EXAMPLES COMPLETED SUCCESSFULLY")
        print("="*70)
        print("\nPhase C is ready for production use!")
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(main())
