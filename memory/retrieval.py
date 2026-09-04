"""Memory retrieval engine using semantic similarity."""
import logging
from typing import Any, Dict, Optional, List

from .embedding_engine import get_embedding

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
        results = retrieve_memories(memory, query, threshold=threshold, top_k=top_k)
        return results[0]["text"] if results else None
    except Exception as e:
        logger.error(f"Error retrieving memory: {e}")
        return None


def retrieve_memories(
    memory: Dict[str, Any],
    query: str,
    threshold: float = 0.15,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """Return structured memories ranked by relevance, importance, and recency."""
    if not isinstance(memory, dict) or not isinstance(query, str) or not query.strip():
        return []
    try:
        embeddings = memory.get("embeddings", [])
        if not isinstance(embeddings, list):
            embeddings = []
        if not embeddings:
            embeddings = [
                item for field in ("long_term", "episodic", "short_term")
                for item in (memory.get(field, []) if isinstance(memory.get(field, []), list) else [])
            ]
        
        query_vector = get_embedding(query)
        if not query_vector:
            logger.warning("Failed to generate query embedding")
            query_vector = []

        candidates = []
        for item in embeddings:
            if isinstance(item, dict):
                vector = item.get("vector", [])
                text = item.get("text") or item.get("content") or item.get("event")
            elif isinstance(item, str):
                vector, text = [], item
            else:
                continue
            if not isinstance(text, str) or not text.strip():
                continue
            semantic = (
                cosine_similarity(query_vector, vector)
                if query_vector and isinstance(vector, list) and len(vector) == len(query_vector)
                else _token_similarity(text, query)
            )
            if semantic < threshold:
                continue
            metadata = item if isinstance(item, dict) else {"text": text}
            importance = _number(metadata.get("importance", metadata.get("importance_score", 0.0)))
            recency = _recency(metadata.get("timestamp"))
            candidates.append({
                "text": text,
                "similarity": semantic,
                "importance": importance,
                "retrieval_score": semantic * 0.55 + importance * 0.3 + recency * 0.15,
                "metadata": metadata,
            })
        candidates.sort(key=lambda result: result["retrieval_score"], reverse=True)
        return candidates[:max(0, top_k)]
    except Exception as e:
        logger.error(f"Error retrieving memory: {e}")
        return []


def _number(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _token_similarity(left: str, right: str) -> float:
    left_words, right_words = set(left.lower().split()), set(right.lower().split())
    union = left_words | right_words
    return len(left_words & right_words) / len(union) if union else 0.0


def _recency(timestamp: Any) -> float:
    import time
    if isinstance(timestamp, (int, float)):
        age_days = max(0.0, (time.time() - timestamp) / 86400)
        return 1.0 / (1.0 + age_days / 30.0)
    return 0.5
