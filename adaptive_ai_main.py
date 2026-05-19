"""Main adaptive AI orchestrator - integrates all 5 phases."""

import logging
from typing import Dict, Optional
import time

# Import all phase modules
from reinforcement_reward_scorer import score_response
from reinforcement_feedback_collector import process_feedback

from ml_training_pipeline import MLTrainingPipeline

from adaptation_personality_engine import PersonalityEngine
from adaptation_mood_detector import real_time_mood_detection
from adaptation_context_adapter import ContextAdapter
from adaptation_prompt_modifier import PromptModifier

from memory_priority_ranker import MemoryPriorityRanker
from memory_semantic_linker import update_memory_links
from memory_importance_scorer import ImportanceScorer

from pipeline_continuous_learning import ContinuousLearningPipeline
from pipeline_real_time_trainer import RealTimeTrainer
from pipeline_quality_metrics import QualityMetricsComputer

logger = logging.getLogger(__name__)


class AdaptiveAIOrchestrator:
    """Master orchestrator for adaptive AI system (Phases 1-5)."""
    
    def __init__(self):
        """Initialize all components."""
        logger.info("Initializing Adaptive AI Orchestrator")
        
        # Phase 1: Reinforcement
        self.feedback_processor = None
        
        # Phase 2: ML Training
        self.ml_pipeline = MLTrainingPipeline()
        
        # Phase 3: Adaptation
        self.personality_engine = PersonalityEngine()
        self.context_adapter = ContextAdapter()
        self.prompt_modifier = PromptModifier()
        
        # Phase 4: Memory Intelligence
        self.memory_ranker = MemoryPriorityRanker()
        self.importance_scorer = ImportanceScorer()
        
        # Phase 5: Continuous Learning
        self.continuous_pipeline = ContinuousLearningPipeline()
        self.real_time_trainer = RealTimeTrainer()
        self.quality_metrics = QualityMetricsComputer()
        
        # State
        self.user_profiles = {}
        self.last_interactions = {}
    
    def process_user_interaction(
        self,
        user_id: str,
        user_message: str,
        user_memory: Dict,
        ai_response: str = "",
        metadata: Dict = None
    ) -> Dict:
        """
        Process complete user interaction through all phases.
        
        Returns:
            Complete interaction result
        """
        metadata = metadata or {}
        
        try:
            logger.info(f"Processing interaction for user {user_id}")
            
            result = {
                "user_id": user_id,
                "timestamp": time.time(),
                "phases": {}
            }
            
            # ========== PHASE 1: REINFORCEMENT ==========
            logger.debug("Running Phase 1: Reinforcement")
            try:
                reinforcement_result = process_feedback(
                    user_message,
                    self.last_interactions.get(user_id, {}).get("response", ""),
                    metadata
                )
                result["phases"]["reinforcement"] = reinforcement_result
                reinforcement_score = reinforcement_result.get("reinforcement_score", 0.0)
            except Exception as e:
                logger.error(f"Phase 1 error: {e}")
                result["phases"]["reinforcement"] = {"error": str(e)}
                reinforcement_score = 0.0
            
            # ========== PHASE 2: ML TRAINING ==========
            logger.debug("Running Phase 2: ML Training")
            try:
                ml_result = self.ml_pipeline.run_full_pipeline(
                    user_memory,
                    [reinforcement_score]
                )
                result["phases"]["ml_training"] = ml_result
                user_profile = ml_result.get("profile", {})
                self.user_profiles[user_id] = user_profile
            except Exception as e:
                logger.error(f"Phase 2 error: {e}")
                result["phases"]["ml_training"] = {"error": str(e)}
                user_profile = self.user_profiles.get(user_id, {})
            
            # ========== PHASE 3: ADAPTATION ==========
            logger.debug("Running Phase 3: Adaptation")
            try:
                # Detect mood
                mood_result = real_time_mood_detection(
                    user_message,
                    metadata,
                    user_memory
                )
                current_mood = mood_result.get("overall_mood", "neutral")
                
                # Calculate personality
                personality = self.personality_engine.calculate_personality(
                    user_profile,
                    current_mood,
                    {"sensitivity_level": mood_result.get("sensitivity_level", 0.5)}
                )
                
                # Adapt to context
                context_adaptation = self.context_adapter.adapt_to_context(
                    user_message,
                    user_memory,
                    metadata.get("timestamp"),
                    current_mood
                )
                
                # Generate modified prompt
                modified_prompt = self.prompt_modifier.modify_prompt(
                    personality=personality,
                    user_profile=user_profile,
                    context=mood_result
                )
                
                result["phases"]["adaptation"] = {
                    "mood": mood_result,
                    "personality": personality,
                    "context": context_adaptation,
                    "modified_prompt": modified_prompt[:200] + "..."
                }
            except Exception as e:
                logger.error(f"Phase 3 error: {e}")
                result["phases"]["adaptation"] = {"error": str(e)}
            
            # ========== PHASE 4: MEMORY INTELLIGENCE ==========
            logger.debug("Running Phase 4: Memory Intelligence")
            try:
                # Update semantic links
                updated_memory = update_memory_links(user_memory)
                
                # Score importances
                all_memories = (
                    updated_memory.get("short_term", []) +
                    updated_memory.get("long_term", [])
                )
                
                scored_memories = self.importance_scorer.score_all_memories(
                    all_memories,
                    updated_memory.get("emotions", {})
                )
                
                # Rank by priority
                ranked_memories = self.memory_ranker.rank_memories(
                    scored_memories,
                    user_message,
                    updated_memory.get("emotions", {}),
                    top_k=5
                )
                
                result["phases"]["memory_intelligence"] = {
                    "semantic_links_updated": True,
                    "importance_scored": len(scored_memories),
                    "top_memories": len(ranked_memories),
                    "knowledge_graph_nodes": len(updated_memory.get("knowledge_graph", {}).get("nodes", {}))
                }
            except Exception as e:
                logger.error(f"Phase 4 error: {e}")
                result["phases"]["memory_intelligence"] = {"error": str(e)}
            
            # ========== PHASE 5: CONTINUOUS LEARNING ==========
            logger.debug("Running Phase 5: Continuous Learning")
            try:
                # Run full pipeline
                pipeline_result = self.continuous_pipeline.run_full_pipeline(
                    user_message,
                    user_id,
                    user_memory,
                    ai_response,
                    metadata
                )
                result["phases"]["continuous_learning"] = pipeline_result
                
                # Add to training batch
                self.real_time_trainer.add_interaction({
                    "message": user_message,
                    "response": ai_response,
                    "score": reinforcement_score,
                    "emotion": mood_result.get("overall_mood", "neutral") if "adaptation" in result["phases"] else "neutral"
                })
                
                # Compute quality metrics
                if ai_response:
                    quality_metrics = self.quality_metrics.compute_response_quality(
                        user_message,
                        ai_response,
                        reinforcement_score,
                        metadata
                    )
                    result["phases"]["quality_metrics"] = quality_metrics
            except Exception as e:
                logger.error(f"Phase 5 error: {e}")
                result["phases"]["continuous_learning"] = {"error": str(e)}
            
            # Store for next iteration
            self.last_interactions[user_id] = {
                "message": user_message,
                "response": ai_response,
                "timestamp": time.time()
            }
            
            result["success"] = len([p for p in result["phases"].values() if "error" not in p]) >= 4
            
            logger.info(f"Interaction processed successfully: {result['success']}")
            return result
        
        except Exception as e:
            logger.error(f"Critical error in interaction processing: {e}")
            return {
                "user_id": user_id,
                "success": False,
                "error": str(e),
                "phases": {}
            }
    
    def get_adaptive_prompt(self, user_id: str, user_memory: Dict, user_message: str = "") -> str:
        """Get adaptively modified system prompt for user."""
        try:
            user_profile = self.user_profiles.get(user_id, {})
            
            mood_result = real_time_mood_detection(user_message, {}, user_memory)
            
            personality = self.personality_engine.calculate_personality(
                user_profile,
                mood_result.get("overall_mood", "neutral")
            )
            
            return self.prompt_modifier.modify_prompt(
                personality=personality,
                user_profile=user_profile,
                context=mood_result
            )
        
        except Exception as e:
            logger.error(f"Error generating adaptive prompt: {e}")
            return self.prompt_modifier.base_system_prompt
    
    def get_system_status(self) -> Dict:
        """Get current system status."""
        return {
            "users_profiled": len(self.user_profiles),
            "training_ready": self.real_time_trainer.get_training_status()["ready_to_train"],
            "quality_trend": self.quality_metrics.get_trend_analysis(),
            "avg_metrics": self.quality_metrics.get_average_metrics()
        }


# Singleton instance
_orchestrator = None


def get_orchestrator() -> AdaptiveAIOrchestrator:
    """Get or create orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AdaptiveAIOrchestrator()
    return _orchestrator
