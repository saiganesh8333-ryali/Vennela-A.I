"""Memory Intelligence - Phase 4 semantic linker."""

import logging
from typing import Dict, List, Set, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


def find_semantic_clusters(
    embeddings_list: List[Dict],
    similarity_threshold: float = 0.7
) -> List[List[int]]:
    """
    Find clusters of semantically similar memories.
    
    Args:
        embeddings_list: List of embedding dicts
        similarity_threshold: Threshold for clustering
    
    Returns:
        List of clusters (lists of indices)
    """
    if not embeddings_list or not isinstance(embeddings_list, list):
        return []
    
    try:
        import numpy as np
        
        clusters = []
        assigned = set()
        
        for i, item_i in enumerate(embeddings_list):
            if i in assigned:
                continue
            
            if not item_i.get("vector"):
                continue
            
            cluster = [i]
            assigned.add(i)
            
            for j, item_j in enumerate(embeddings_list):
                if j <= i or j in assigned:
                    continue
                
                if not item_j.get("vector"):
                    continue
                
                # Calculate cosine similarity
                vec_i = np.array(item_i["vector"])
                vec_j = np.array(item_j["vector"])
                
                similarity = np.dot(vec_i, vec_j) / (np.linalg.norm(vec_i) * np.linalg.norm(vec_j))
                
                if similarity >= similarity_threshold:
                    cluster.append(j)
                    assigned.add(j)
            
            if cluster:
                clusters.append(cluster)
        
        return clusters
    
    except Exception as e:
        logger.error(f"Error finding semantic clusters: {e}")
        return []


def extract_knowledge_graph_entities(memory_text: str) -> Set[str]:
    """
    Extract potential entities for knowledge graph.
    
    Returns:
        Set of entity strings
    """
    if not memory_text or not isinstance(memory_text, str):
        return set()
    
    try:
        entities = set()
        
        # Simple pattern matching for entities
        patterns = {
            "person": r"(Mr|Mrs|Ms|Dr|Prof|[A-Z][a-z]+ [A-Z][a-z]+)",
            "place": r"(New York|London|Paris|[A-Z][a-z]+ [A-Z][a-z]+)",
            "topic": r"(programming|science|technology|business|music|art)"
        }
        
        import re
        
        for entity_type, pattern in patterns.items():
            matches = re.findall(pattern, memory_text)
            for match in matches:
                entities.add(match.lower().strip())
        
        return entities
    
    except Exception as e:
        logger.error(f"Error extracting entities: {e}")
        return set()


def build_knowledge_graph(user_memories: List[Dict]) -> Dict:
    """
    Build knowledge graph from user memories.
    
    Returns:
        Dict representing knowledge graph
    """
    if not user_memories or not isinstance(user_memories, list):
        return {"nodes": {}, "edges": [], "clusters": []}
    
    try:
        graph = {
            "nodes": {},
            "edges": [],
            "clusters": [],
            "statistics": {
                "total_memories": len(user_memories),
                "unique_entities": 0
            }
        }
        
        entity_memory_map = defaultdict(list)
        
        # Extract entities from each memory
        for i, memory in enumerate(user_memories):
            text = memory.get("text", memory.get("content", ""))
            entities = extract_knowledge_graph_entities(text)
            
            for entity in entities:
                entity_memory_map[entity].append(i)
                
                if entity not in graph["nodes"]:
                    graph["nodes"][entity] = {
                        "type": "entity",
                        "memories": [],
                        "frequency": 0
                    }
                
                graph["nodes"][entity]["memories"].append(i)
                graph["nodes"][entity]["frequency"] += 1
        
        # Create edges between related entities
        entities_list = list(entity_memory_map.keys())
        for i, entity1 in enumerate(entities_list):
            for entity2 in entities_list[i + 1:]:
                # Check if entities appear in same memory
                common_memories = set(entity_memory_map[entity1]) & set(entity_memory_map[entity2])
                if common_memories:
                    graph["edges"].append({
                        "from": entity1,
                        "to": entity2,
                        "weight": len(common_memories),
                        "shared_memories": list(common_memories)
                    })
        
        graph["statistics"]["unique_entities"] = len(graph["nodes"])
        
        return graph
    
    except Exception as e:
        logger.error(f"Error building knowledge graph: {e}")
        return {"nodes": {}, "edges": [], "clusters": []}


def link_related_memories(
    memory_item: Dict,
    all_memories: List[Dict],
    similarity_threshold: float = 0.6
) -> List[Dict]:
    """
    Find related memories to a given memory.
    
    Args:
        memory_item: Target memory
        all_memories: All memories to search
        similarity_threshold: Minimum similarity
    
    Returns:
        List of related memories
    """
    if not memory_item or not all_memories:
        return []
    
    try:
        related = []
        target_text = memory_item.get("text", memory_item.get("content", "")).lower()
        
        for other_mem in all_memories:
            if other_mem == memory_item:
                continue
            
            other_text = other_mem.get("text", other_mem.get("content", "")).lower()
            
            # Simple text similarity
            target_words = set(target_text.split())
            other_words = set(other_text.split())
            
            if not target_words or not other_words:
                continue
            
            intersection = target_words & other_words
            union = target_words | other_words
            
            jaccard_similarity = len(intersection) / len(union)
            
            if jaccard_similarity >= similarity_threshold:
                related.append({
                    "memory": other_mem,
                    "similarity": jaccard_similarity,
                    "shared_terms": list(intersection)[:5]
                })
        
        # Sort by similarity
        related.sort(key=lambda x: x["similarity"], reverse=True)
        
        return related[:3]
    
    except Exception as e:
        logger.error(f"Error linking memories: {e}")
        return []


def update_memory_links(user_memory: Dict) -> Dict:
    """
    Update all memory links in user memory.
    
    Returns:
        Updated memory with links
    """
    if not user_memory or not isinstance(user_memory, dict):
        return user_memory
    
    try:
        # Get all memories
        short_term = user_memory.get("short_term", [])
        long_term = user_memory.get("long_term", [])
        episodic = user_memory.get("episodic", [])
        
        all_memories = short_term + long_term + episodic
        
        # Build knowledge graph
        graph = build_knowledge_graph(all_memories)
        
        # Add/update semantic links
        semantic_links = []
        for i, mem in enumerate(all_memories):
            related = link_related_memories(mem, all_memories)
            if related:
                semantic_links.append({
                    "memory_index": i,
                    "related_count": len(related),
                    "relations": [
                        {
                            "similarity": r["similarity"],
                            "shared_terms": r["shared_terms"]
                        }
                        for r in related
                    ]
                })
        
        # Update user memory
        user_memory["knowledge_graph"] = graph
        user_memory["semantic_links"] = semantic_links
        
        logger.debug(f"Updated {len(semantic_links)} memory links")
        
        return user_memory
    
    except Exception as e:
        logger.error(f"Error updating memory links: {e}")
        return user_memory
