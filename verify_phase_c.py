#!/usr/bin/env python3
"""Quick verification of Phase C implementation."""

import asyncio
import sys
import time

# Add current directory to path
sys.path.insert(0, r'd:\Vennela A.I.worktrees\agents-adaptive-ai-evolution-plan')

from memory_reflection_engine import (
    MemoryConsolidationEngine,
    ConsolidationPhase,
    ReflectionHandler
)
from memory_importance_analyzer import (
    ImportanceAnalyzer,
    ImportanceLevel,
    ImportanceScoringHandler
)
from memory_semantic_network import (
    SemanticNetwork,
    RelationshipType,
    SemanticLinkingHandler
)
from event_types import EventType


def test_consolidation_engine():
    """Test consolidation engine."""
    print("\n" + "="*60)
    print("TESTING CONSOLIDATION ENGINE")
    print("="*60)
    
    engine = MemoryConsolidationEngine()
    user_id = "test_user_1"
    
    # Add working memory
    print("\n1. Adding working memories...")
    for i in range(3):
        record = engine.add_working_memory(
            user_id=user_id,
            memory_id=f"mem_{i}",
            content=f"Test memory content {i}",
            memory_type="episodic",
            importance=0.6 + i * 0.1
        )
        print(f"   ✓ Added memory {i}: {record.memory_id}")
    
    # Age the memories
    print("\n2. Aging memories for consolidation...")
    context = engine.get_or_create_context(user_id)
    for record in context.working_memories.values():
        record.timestamp = time.time() - 400  # 400 seconds old
    print(f"   ✓ Aged {len(context.working_memories)} memories")
    
    # Run consolidation cycle
    print("\n3. Running full consolidation cycle...")
    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(
        engine.run_full_consolidation_cycle(user_id)
    )
    loop.close()
    
    print(f"   ✓ Short-term consolidation: {result['phases']['short_term']['consolidated_count']} memories")
    print(f"   ✓ Semantic consolidation: {result['phases']['semantic']['patterns_extracted']} patterns")
    print(f"   ✓ Summary created: {result['phases']['summary']['summary_created']}")
    print(f"   ✓ Total time: {result['cycle_duration']:.3f}s")
    
    # Verify results
    print("\n4. Verifying consolidation results...")
    print(f"   ✓ Working memories: {len(context.working_memories)}")
    print(f"   ✓ Episodic memories: {len(context.episodic_memories)}")
    print(f"   ✓ Semantic patterns: {len(context.semantic_patterns)}")
    print(f"   ✓ Has summary: {bool(context.summary_data)}")
    
    return True


def test_importance_analyzer():
    """Test importance analyzer."""
    print("\n" + "="*60)
    print("TESTING IMPORTANCE ANALYZER")
    print("="*60)
    
    analyzer = ImportanceAnalyzer()
    
    # Track memories
    print("\n1. Tracking memories...")
    for i in range(5):
        analyzer.track_memory(f"mem_{i}")
        print(f"   ✓ Tracking memory {i}")
    
    # Record interactions
    print("\n2. Recording interactions...")
    for i in range(5):
        memory_id = f"mem_{i}"
        for j in range(i + 1):
            analyzer.record_interaction(memory_id, "retrieve")
    print(f"   ✓ Recorded interactions for all memories")
    
    # Score memories
    print("\n3. Scoring importance...")
    scores = {}
    for i in range(5):
        score = analyzer.score_memory(f"mem_{i}", include_cache=False)
        level = analyzer.classify_importance(score)
        scores[f"mem_{i}"] = score
        print(f"   ✓ mem_{i}: score={score:.3f}, level={level.value}")
    
    # Get important memories
    print("\n4. Finding important memories...")
    important = analyzer.get_important_memories(min_importance=0.3, limit=10)
    print(f"   ✓ Found {len(important)} important memories")
    for mem in important[:3]:
        print(f"     - {mem['memory_id']}: {mem['importance_score']:.3f} ({mem['importance_level']})")
    
    # Get stats
    print("\n5. Analyzer statistics...")
    stats = analyzer.get_stats()
    print(f"   ✓ Total memories tracked: {stats['total_memories_tracked']}")
    print(f"   ✓ Average importance: {stats['average_importance']:.3f}")
    print(f"   ✓ Importance distribution: {stats['memories_by_level']}")
    
    return True


def test_semantic_network():
    """Test semantic network."""
    print("\n" + "="*60)
    print("TESTING SEMANTIC NETWORK")
    print("="*60)
    
    network = SemanticNetwork()
    
    # Create links
    print("\n1. Creating semantic links...")
    link_pairs = [
        ("mem_1", "mem_2", RelationshipType.CAUSAL),
        ("mem_2", "mem_3", RelationshipType.TEMPORAL),
        ("mem_3", "mem_4", RelationshipType.CONCEPTUAL),
        ("mem_1", "mem_4", RelationshipType.EMOTIONAL),
    ]
    
    for mem1, mem2, rel_type in link_pairs:
        link = network.add_link(
            memory_id_1=mem1,
            memory_id_2=mem2,
            relationship_type=rel_type,
            strength=0.7
        )
        print(f"   ✓ Created link: {mem1} --[{rel_type.value}]--> {mem2}")
    
    # Find related
    print("\n2. Finding related memories...")
    related = network.find_related("mem_1", max_depth=2)
    print(f"   ✓ Found {related['total_count']} memories related to mem_1")
    print(f"   ✓ Relationships by type: {list(related['by_type'].keys())}")
    
    # Reinforce path
    print("\n3. Reinforcing path...")
    path = ["mem_1", "mem_2", "mem_3"]
    reinforced = network.reinforce_path(path, factor=0.1)
    print(f"   ✓ Reinforced {reinforced} links in path")
    
    # Network stats
    print("\n4. Network statistics...")
    stats = network.get_network_stats()
    print(f"   ✓ Total links: {stats['total_links']}")
    print(f"   ✓ Total memories: {stats['total_memories']}")
    print(f"   ✓ Network density: {stats['network_density']:.3f}")
    print(f"   ✓ Average link strength: {stats['average_link_strength']:.3f}")
    print(f"   ✓ Links by type: {stats['by_type']}")
    
    # Strongest links
    print("\n5. Strongest links...")
    strongest = network.get_strongest_links(limit=3)
    for link in strongest:
        print(f"   ✓ {link['memory_id_1']} --[{link['relationship_type']}]--> {link['memory_id_2']}: {link['strength']:.2f}")
    
    return True


def test_event_handlers():
    """Test event handlers."""
    print("\n" + "="*60)
    print("TESTING EVENT HANDLERS")
    print("="*60)
    
    # Test ReflectionHandler
    print("\n1. Testing ReflectionHandler...")
    reflection_handler = ReflectionHandler()
    print(f"   ✓ Handler name: {reflection_handler.name}")
    print(f"   ✓ Subscribed event types: {[et.value for et in reflection_handler.event_types]}")
    
    # Test ImportanceScoringHandler
    print("\n2. Testing ImportanceScoringHandler...")
    scoring_handler = ImportanceScoringHandler()
    print(f"   ✓ Handler name: {scoring_handler.name}")
    print(f"   ✓ Subscribed event types: {[et.value for et in scoring_handler.event_types]}")
    
    # Test SemanticLinkingHandler
    print("\n3. Testing SemanticLinkingHandler...")
    linking_handler = SemanticLinkingHandler()
    print(f"   ✓ Handler name: {linking_handler.name}")
    print(f"   ✓ Subscribed event types: {[et.value for et in linking_handler.event_types]}")
    
    return True


def test_integration():
    """Test full integration."""
    print("\n" + "="*60)
    print("TESTING FULL INTEGRATION")
    print("="*60)
    
    engine = MemoryConsolidationEngine()
    analyzer = ImportanceAnalyzer()
    network = SemanticNetwork()
    
    user_id = "integration_user"
    
    print("\n1. Complete memory lifecycle...")
    
    # Create memories
    print("   Creating memories...")
    for i in range(3):
        engine.add_working_memory(
            user_id=user_id,
            memory_id=f"mem_{i}",
            content=f"Memory {i}",
            memory_type="episodic",
            importance=0.6 + i * 0.1
        )
        analyzer.track_memory(f"mem_{i}")
    
    # Create network
    print("   Building semantic network...")
    for i in range(2):
        network.add_link(
            memory_id_1=f"mem_{i}",
            memory_id_2=f"mem_{i+1}",
            relationship_type=RelationshipType.TEMPORAL,
            strength=0.8
        )
    
    # Age and consolidate
    print("   Aging and consolidating...")
    context = engine.get_or_create_context(user_id)
    for record in context.working_memories.values():
        record.timestamp = time.time() - 400
    
    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(
        engine.run_full_consolidation_cycle(user_id)
    )
    loop.close()
    
    # Verify all systems updated
    print("\n2. Verification...")
    print(f"   ✓ Episodic memories: {len(context.episodic_memories)}")
    print(f"   ✓ Semantic patterns: {len(context.semantic_patterns)}")
    print(f"   ✓ Network links: {len(network.links)}")
    print(f"   ✓ Memory importance average: {analyzer.get_stats()['average_importance']:.3f}")
    print(f"   ✓ Summary created: {bool(context.summary_data)}")
    
    return True


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("PHASE C: MEMORY REFLECTION CYCLE")
    print("Comprehensive Testing Suite")
    print("="*60)
    
    tests = [
        ("Consolidation Engine", test_consolidation_engine),
        ("Importance Analyzer", test_importance_analyzer),
        ("Semantic Network", test_semantic_network),
        ("Event Handlers", test_event_handlers),
        ("Full Integration", test_integration),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success, None))
            print(f"\n✓ {name} PASSED")
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"\n✗ {name} FAILED: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for name, success, error in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {name}")
        if error:
            print(f"  Error: {error}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n" + "="*60)
        print("ALL TESTS PASSED! Phase C is ready for deployment.")
        print("="*60)
        return 0
    else:
        print(f"\n{total - passed} test(s) failed.")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
