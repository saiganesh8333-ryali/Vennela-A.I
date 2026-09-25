"""Lightweight semantic embedding engine with optional MiniLM support."""
import hashlib
import logging
import os
import re
from typing import List

os.environ.setdefault("HF_HOME", os.path.join(os.getcwd(), ".hf_cache"))
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", os.path.join(os.getcwd(), ".hf_cache", "sentence-transformers"))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

logger = logging.getLogger(__name__)

ENABLE_MINILM = os.getenv("VENNELA_ENABLE_MINILM", "false").lower() == "true"

_embedding_model = None
_embedding_cache = {}


def _load_embedding_model():
    """Load optional MiniLM model, otherwise use the no-dependency fallback."""
    global _embedding_model

    if not ENABLE_MINILM:
        _embedding_model = "fallback"
        return None

    if _embedding_model is not None:
        return None if _embedding_model == "fallback" else _embedding_model

    try:
        from sentence_transformers import SentenceTransformer

        model_name = os.getenv("VENNELA_EMBEDDING_MODEL", "paraphrase-MiniLM-L3-v2")
        logger.info(f"Loading optional embedding model: {model_name}")
        _embedding_model = SentenceTransformer(model_name)

        try:
            _embedding_model.half()
        except Exception as e:
            logger.debug(f"FP16 conversion skipped: {e}")

        logger.info(f"Embedding model loaded: {model_name}")
        return _embedding_model
    except Exception as e:
        logger.warning(f"Failed to load embedding model: {e}. Using fallback embedding.")
        _embedding_model = "fallback"
        return None


def _fallback_embedding(text: str) -> List[float]:
    """
    Generate a deterministic hash embedding.

    This is not as smart as MiniLM, but it is fast, stable, and keeps memory
    retrieval working on low-resource deployments without model downloads.
    """
    tokens = re.findall(r"[a-z0-9]+", text.lower())[:96]
    vector = [0.0] * 128

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        index = int(digest[:8], 16) % len(vector)
        vector[index] += 1.0

    norm = sum(x * x for x in vector) ** 0.5
    if norm > 0:
        vector = [x / norm for x in vector]

    return vector


def get_embedding(text: str, use_cache: bool = True) -> List[float]:
    """Generate an embedding using optional MiniLM or fallback hashing."""
    if not text or not isinstance(text, str):
        logger.warning(f"Invalid input for embedding: {type(text)}")
        return [0.0] * 128

    text = text[:1000]
    cache_key = f"{'minilm' if ENABLE_MINILM else 'fallback'}:{text}"

    if use_cache and cache_key in _embedding_cache:
        return _embedding_cache[cache_key]

    try:
        model = _load_embedding_model()
        if model is None:
            embedding = _fallback_embedding(text)
        else:
            embedding = model.encode(text).tolist()

        if use_cache:
            _embedding_cache[cache_key] = embedding

        return embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return _fallback_embedding(text)


def clear_embedding_cache():
    """Clear the embedding cache."""
    size_before = len(_embedding_cache)
    _embedding_cache.clear()
    logger.info(f"Cleared embedding cache ({size_before} entries removed)")


def get_cache_stats() -> dict:
    """Get embedding cache statistics."""
    return {
        "cached_embeddings": len(_embedding_cache),
        "cache_size_mb": sum(len(str(v)) for v in _embedding_cache.values()) / (1024 * 1024),
        "minilm_enabled": ENABLE_MINILM,
    }
