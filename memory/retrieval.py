"""Memory retrieval engine using semantic similarity."""
import logging
from typing import Optional, List

from embedding_engine import get_embedding

logger = logging.getLogger(__name__)


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors.
    
    Args:
        a: First vector
        b: Second vector
        
    Returns:
        float: Similarity score between -1 and 1
    """
    if not a or not b:
        return 0.0
    
    try:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        
        return dot / (norm_a * norm_b + 1e-9)
    except Exception as e:
        logger.error(f"Error calculating cosine similarity: {e}")
        return 0.0


def retrieve_memory(
    memory: dict,
    query: str,
    threshold: float = 0.15,
    top_k: int = 1
) -> Optional[str]:
    """
    Retrieve the most relevant memory item based on semantic similarity.
    
    Args:
        memory: User's memory dictionary
        query: Query text
        threshold: Minimum similarity score to return
        top_k: Number of top results to return (currently only returns 1)
        
    Returns:
        str: Most relevant memory text or None if below threshold
    """
    if not memory or not query:
        return None
    
    try:
        embeddings = memory.get("embeddings", [])
        if not embeddings:
            logger.debug("No embeddings found in memory")
            return None
        
        query_vector = get_embedding(query)
        if not query_vector:
            logger.warning("Failed to generate query embedding")
            return None
        
        best_text = None
        best_score = 0
        
        for item in embeddings:
            if not isinstance(item, dict) or "vector" not in item:
                continue
            
            vector = item.get("vector", [])
            if not vector:
                continue
            
            score = cosine_similarity(query_vector, vector)
            
            if score > best_score:
                best_score = score
                best_text = item.get("text")
        
        if best_score < threshold:
            logger.debug(f"Best similarity score {best_score} below threshold {threshold}")
            return None
        
        logger.debug(f"Retrieved memory with similarity {best_score:.3f}: {best_text[:50]}...")
        return best_text
        
    except Exception as e:
        logger.error(f"Error retrieving memory: {e}")
        return None
