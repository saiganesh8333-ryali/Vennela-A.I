import hashlib
import logging
import os
import re
from typing import List, Optional

os.environ.setdefault("HF_HOME", os.path.join(os.getcwd(), ".hf_cache"))
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", os.path.join(os.getcwd(), ".hf_cache", "sentence-transformers"))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

logger = logging.getLogger(__name__)

_embedding_model = None
_embedding_cache = {}  # Simple in-memory cache for embeddings


def _load_embedding_model():
    """Load sentence transformer model with error handling."""
    global _embedding_model
    
    if _embedding_model is not None:
        return _embedding_model
    
    try:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading embedding model (all-MiniLM-L6-v2)...")
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Embedding model loaded successfully")
        return _embedding_model
    except Exception as e:
        logger.warning(f"Failed to load embedding model: {e}. Using fallback.")
        return None


def _fallback_embedding(text: str) -> List[float]:
    """
    Fallback embedding using hash-based vector generation.
    Deterministic: same text always produces same vector.
    """
    tokens = re.findall(r"[a-z0-9]+", text.lower())[:64]
    vector = [0.0] * 128
    
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        index = int(digest[:8], 16) % len(vector)
        vector[index] += 1.0
    
    # Normalize
    norm = sum(x * x for x in vector) ** 0.5
    if norm > 0:
        vector = [x / norm for x in vector]
    
    return vector


def get_embedding(text: str, use_cache: bool = True) -> List[float]:
    """
    Generate semantic embedding for text.
    
    Args:
        text: Input text to embed
        use_cache: Whether to use cached embeddings
        
    Returns:
        List of floats representing the embedding vector
    """
    if not text or not isinstance(text, str):
        logger.warning(f"Invalid input for embedding: {type(text)}")
        return [0.0] * 128
    
    # Truncate very long texts
    text = text[:1000]
    
    # Check cache
    if use_cache and text in _embedding_cache:
        return _embedding_cache[text]
    
    try:
        model = _load_embedding_model()
        if model is None:
            embedding = _fallback_embedding(text)
        else:
            embedding = model.encode(text).tolist()
        
        # Cache the result
        if use_cache:
            _embedding_cache[text] = embedding
        
        return embedding
        
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return _fallback_embedding(text)


def clear_embedding_cache():
    """Clear the embedding cache (useful for memory management)."""
    global _embedding_cache
    size_before = len(_embedding_cache)
    _embedding_cache.clear()
    logger.info(f"Cleared embedding cache ({size_before} entries removed)")


def get_cache_stats() -> dict:
    """Get embedding cache statistics."""
    return {
        "cached_embeddings": len(_embedding_cache),
        "cache_size_mb": sum(len(str(v)) for v in _embedding_cache.values()) / (1024 * 1024)
    }
