"""ML Training - Phase 2 response embeddings."""

import logging
from typing import Dict, List, Optional
import numpy as np

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    logger.warning("sentence-transformers not available, embeddings disabled")


class ResponseEmbeddingEngine:
    """Generate and manage response embeddings."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize embedding engine."""
        self.model_name = model_name
        self.model = None
        self.embeddings_cache = {}
        
        if HAS_SENTENCE_TRANSFORMERS:
            try:
                self.model = SentenceTransformer(model_name)
                logger.debug(f"Loaded embedding model: {model_name}")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
    
    def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for text.
        
        Args:
            text: Text to embed
        
        Returns:
            Vector embedding or empty list if unavailable
        """
        if not text or not isinstance(text, str):
            return []
        
        # Check cache
        if text in self.embeddings_cache:
            return self.embeddings_cache[text]
        
        if not HAS_SENTENCE_TRANSFORMERS or self.model is None:
            logger.warning("Embedding model not available")
            return []
        
        try:
            embedding = self.model.encode(text).tolist()
            self.embeddings_cache[text] = embedding
            return embedding
        
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return []
    
    def batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        if not texts or not isinstance(texts, list):
            return []
        
        if not HAS_SENTENCE_TRANSFORMERS or self.model is None:
            return [[] for _ in texts]
        
        try:
            embeddings = self.model.encode(texts).tolist()
            
            for text, emb in zip(texts, embeddings):
                self.embeddings_cache[text] = emb
            
            return embeddings
        
        except Exception as e:
            logger.error(f"Error batch encoding: {e}")
            return [[] for _ in texts]
    
    def similarity(self, text1: str, text2: str) -> float:
        """Calculate cosine similarity between two texts."""
        if not text1 or not text2:
            return 0.0
        
        if not HAS_SENTENCE_TRANSFORMERS or self.model is None:
            return 0.0
        
        try:
            emb1 = self.get_embedding(text1)
            emb2 = self.get_embedding(text2)
            
            if not emb1 or not emb2:
                return 0.0
            
            arr1 = np.array(emb1)
            arr2 = np.array(emb2)
            
            similarity = np.dot(arr1, arr2) / (np.linalg.norm(arr1) * np.linalg.norm(arr2))
            return float(similarity)
        
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0


def extract_quality_patterns(responses: List[str], scores: List[float] = None) -> Dict:
    """
    Extract quality patterns from high-scoring responses.
    
    Returns:
        Dict with patterns and characteristics
    """
    if not responses or not isinstance(responses, list):
        return {"avg_length": 0, "high_quality_count": 0, "patterns": {}}
    
    try:
        scores = scores or [0.5] * len(responses)
        
        high_quality = [
            resp for resp, score in zip(responses, scores) if score > 0.6
        ]
        
        patterns = {
            "avg_length": 0,
            "high_quality_count": len(high_quality),
            "patterns": {
                "has_examples": 0,
                "has_explanations": 0,
                "has_questions": 0,
                "structured_format": 0
            },
            "quality_ratio": len(high_quality) / len(responses) if responses else 0
        }
        
        if high_quality:
            avg_len = sum(len(r) for r in high_quality) / len(high_quality)
            patterns["avg_length"] = int(avg_len)
            
            for resp in high_quality:
                if "for example" in resp.lower() or "e.g." in resp.lower():
                    patterns["patterns"]["has_examples"] += 1
                if "because" in resp.lower() or "reason" in resp.lower():
                    patterns["patterns"]["has_explanations"] += 1
                if "?" in resp:
                    patterns["patterns"]["has_questions"] += 1
                if "1." in resp or "-" in resp or "•" in resp:
                    patterns["patterns"]["structured_format"] += 1
        
        return patterns
    
    except Exception as e:
        logger.error(f"Error extracting quality patterns: {e}")
        return {"avg_length": 0, "high_quality_count": 0, "patterns": {}}


def generate_response_embeddings(user_memory: Dict, embedding_engine: ResponseEmbeddingEngine = None) -> Dict:
    """
    Generate embeddings for all user responses.
    
    Args:
        user_memory: User memory dict
        embedding_engine: Optional embedding engine instance
    
    Returns:
        Dict with embeddings and patterns
    """
    if not user_memory or not isinstance(user_memory, dict):
        return {"embeddings": [], "patterns": {}, "quality_summary": {}}
    
    try:
        if embedding_engine is None:
            embedding_engine = ResponseEmbeddingEngine()
        
        short_term = user_memory.get("short_term", [])
        embeddings_data = user_memory.get("embeddings", [])
        
        # Extract texts
        texts = []
        for item in short_term + embeddings_data:
            if isinstance(item, dict):
                text = item.get("text", item.get("content", ""))
            else:
                text = str(item)
            
            if text and text not in texts:
                texts.append(text)
        
        # Generate embeddings
        vectors = embedding_engine.batch_embeddings(texts)
        
        result_embeddings = [
            {"text": text, "vector": vec}
            for text, vec in zip(texts, vectors)
            if vec
        ]
        
        # Extract quality patterns
        long_term = user_memory.get("long_term", [])
        importance_scores = [item.get("importance", 0) for item in embeddings_data]
        
        quality_patterns = extract_quality_patterns(
            [item.get("text", "") for item in embeddings_data],
            importance_scores
        )
        
        return {
            "embeddings": result_embeddings,
            "total_count": len(result_embeddings),
            "patterns": quality_patterns,
            "cache_size": len(embedding_engine.embeddings_cache)
        }
    
    except Exception as e:
        logger.error(f"Error generating response embeddings: {e}")
        return {"embeddings": [], "patterns": {}, "quality_summary": {}}


def find_similar_responses(
    query_text: str,
    embeddings_list: List[Dict],
    embedding_engine: ResponseEmbeddingEngine = None,
    top_k: int = 5
) -> List[Dict]:
    """
    Find most similar responses to query.
    
    Args:
        query_text: Query text
        embeddings_list: List of embedding dicts
        embedding_engine: Optional embedding engine
        top_k: Number of results
    
    Returns:
        List of similar responses with similarity scores
    """
    if not query_text or not embeddings_list:
        return []
    
    try:
        if embedding_engine is None:
            embedding_engine = ResponseEmbeddingEngine()
        
        query_embedding = np.array(embedding_engine.get_embedding(query_text))
        
        if query_embedding.size == 0:
            return []
        
        similarities = []
        for item in embeddings_list:
            if not item.get("vector"):
                continue
            
            vec = np.array(item["vector"])
            sim = np.dot(query_embedding, vec) / (np.linalg.norm(query_embedding) * np.linalg.norm(vec))
            
            similarities.append({
                "text": item.get("text", ""),
                "similarity": float(sim),
                "original_item": item
            })
        
        similarities.sort(key=lambda x: x["similarity"], reverse=True)
        return similarities[:top_k]
    
    except Exception as e:
        logger.error(f"Error finding similar responses: {e}")
        return []
