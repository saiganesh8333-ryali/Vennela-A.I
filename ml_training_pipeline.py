"""ML Training - Phase 2 training pipeline orchestrator."""

import logging
from typing import Dict, Optional
from ml_user_profile_trainer import train_user_profile
from ml_response_embeddings import ResponseEmbeddingEngine, generate_response_embeddings
from ml_pattern_detector import detect_all_patterns

logger = logging.getLogger(__name__)

try:
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    logger.warning("scikit-learn not available, model training disabled")


class MLTrainingPipeline:
    """Orchestrate full ML training pipeline."""
    
    def __init__(self):
        """Initialize pipeline."""
        self.embedding_engine = ResponseEmbeddingEngine()
        self.user_profile = {}
        self.patterns = {}
        self.embeddings = {}
        self.models = {}
    
    def load_memory(self, user_memory: Dict) -> bool:
        """Load and validate user memory."""
        if not user_memory or not isinstance(user_memory, dict):
            logger.error("Invalid user memory")
            return False
        
        try:
            # Verify required fields
            if not user_memory.get("short_term") and not user_memory.get("long_term"):
                logger.warning("No messages found in memory")
                return False
            
            logger.debug("Memory loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Error loading memory: {e}")
            return False
    
    def extract_embeddings(self, user_memory: Dict) -> bool:
        """Extract embeddings from memory."""
        try:
            self.embeddings = generate_response_embeddings(
                user_memory,
                self.embedding_engine
            )
            logger.debug(f"Generated {len(self.embeddings.get('embeddings', []))} embeddings")
            return True
        except Exception as e:
            logger.error(f"Error extracting embeddings: {e}")
            return False
    
    def train_profile(self, user_memory: Dict, feedback_scores: list = None) -> bool:
        """Train user profile."""
        try:
            self.user_profile = train_user_profile(user_memory, feedback_scores)
            logger.debug("User profile trained")
            return True
        except Exception as e:
            logger.error(f"Error training profile: {e}")
            return False
    
    def detect_patterns(self, user_memory: Dict, timestamps: list = None) -> bool:
        """Detect user patterns."""
        try:
            self.patterns = detect_all_patterns(user_memory, timestamps)
            logger.debug("Patterns detected")
            return True
        except Exception as e:
            logger.error(f"Error detecting patterns: {e}")
            return False
    
    def build_classifiers(self) -> bool:
        """Build scikit-learn classifiers (stub for now)."""
        if not HAS_SKLEARN:
            logger.warning("scikit-learn not available, skipping classifier training")
            return False
        
        try:
            # Future: Build response quality, topic, sentiment classifiers
            self.models["initialized"] = True
            logger.debug("Classifiers initialized")
            return True
        except Exception as e:
            logger.error(f"Error building classifiers: {e}")
            return False
    
    def run_full_pipeline(
        self,
        user_memory: Dict,
        feedback_scores: list = None,
        timestamps: list = None
    ) -> Dict:
        """
        Run complete training pipeline.
        
        Args:
            user_memory: User memory dict
            feedback_scores: Optional reinforcement scores
            timestamps: Optional message timestamps
        
        Returns:
            Pipeline result summary
        """
        result = {
            "success": False,
            "stages_completed": [],
            "profile": {},
            "embeddings": {},
            "patterns": {},
            "models": {},
            "errors": []
        }
        
        try:
            # Stage 1: Load memory
            if not self.load_memory(user_memory):
                result["errors"].append("Memory loading failed")
                return result
            result["stages_completed"].append("memory_loaded")
            
            # Stage 2: Extract embeddings
            if not self.extract_embeddings(user_memory):
                result["errors"].append("Embedding extraction failed")
            else:
                result["stages_completed"].append("embeddings_extracted")
                result["embeddings"] = self.embeddings
            
            # Stage 3: Train profile
            if not self.train_profile(user_memory, feedback_scores):
                result["errors"].append("Profile training failed")
            else:
                result["stages_completed"].append("profile_trained")
                result["profile"] = self.user_profile
            
            # Stage 4: Detect patterns
            if not self.detect_patterns(user_memory, timestamps):
                result["errors"].append("Pattern detection failed")
            else:
                result["stages_completed"].append("patterns_detected")
                result["patterns"] = self.patterns
            
            # Stage 5: Build classifiers
            if not self.build_classifiers():
                result["errors"].append("Classifier building skipped")
            else:
                result["stages_completed"].append("classifiers_built")
                result["models"] = self.models
            
            result["success"] = len(result["stages_completed"]) >= 4
            
            logger.info(f"Training pipeline completed: {result['stages_completed']}")
            return result
        
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            result["errors"].append(str(e))
            return result
    
    def persist_models(self, output_path: str = None) -> bool:
        """Save trained models to disk."""
        try:
            import json
            
            output_path = output_path or "user_ml_models.json"
            
            data = {
                "profile": self.user_profile,
                "patterns": self.patterns,
                "embeddings_count": len(self.embeddings.get("embeddings", []))
            }
            
            with open(output_path, 'w') as f:
                json.dump(data, f, default=str, indent=2)
            
            logger.debug(f"Models persisted to {output_path}")
            return True
        
        except Exception as e:
            logger.error(f"Error persisting models: {e}")
            return False
    
    def load_models(self, input_path: str = None) -> bool:
        """Load trained models from disk."""
        try:
            import json
            
            input_path = input_path or "user_ml_models.json"
            
            with open(input_path, 'r') as f:
                data = json.load(f)
            
            self.user_profile = data.get("profile", {})
            self.patterns = data.get("patterns", {})
            
            logger.debug("Models loaded successfully")
            return True
        
        except Exception as e:
            logger.error(f"Error loading models: {e}")
            return False
    
    def get_summary(self) -> Dict:
        """Get current pipeline summary."""
        return {
            "profile_trained": bool(self.user_profile),
            "embeddings_count": len(self.embeddings.get("embeddings", [])),
            "patterns_detected": bool(self.patterns),
            "models_initialized": bool(self.models),
            "favorite_topics": self.patterns.get("favorite_topics", []),
            "sensitivities": self.patterns.get("emotional_triggers", {}).get("sensitive_topics", []),
            "recurring_tasks": len(self.patterns.get("recurring_tasks", []))
        }
