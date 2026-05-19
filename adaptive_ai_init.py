"""Adaptive AI Evolution - Integrated module exports."""

# Phase 1: Reinforcement Layer
from reinforcement_reward_scorer import score_response, batch_score_responses
from reinforcement_feedback_collector import collect_implicit_feedback, collect_explicit_feedback, process_feedback

# Phase 2: ML Training
from ml_user_profile_trainer import train_user_profile
from ml_response_embeddings import ResponseEmbeddingEngine, generate_response_embeddings
from ml_pattern_detector import detect_all_patterns
from ml_training_pipeline import MLTrainingPipeline

# Phase 3: Adaptation Engine
from adaptation_personality_engine import PersonalityEngine
from adaptation_mood_detector import real_time_mood_detection
from adaptation_context_adapter import ContextAdapter
from adaptation_prompt_modifier import PromptModifier

# Phase 4: Memory Intelligence
from memory_priority_ranker import MemoryPriorityRanker
from memory_semantic_linker import build_knowledge_graph, update_memory_links
from memory_importance_scorer import ImportanceScorer

# Phase 5: Continuous Learning
from pipeline_continuous_learning import ContinuousLearningPipeline
from pipeline_real_time_trainer import RealTimeTrainer
from pipeline_quality_metrics import QualityMetricsComputer

__all__ = [
    # Phase 1
    "score_response",
    "batch_score_responses",
    "collect_implicit_feedback",
    "collect_explicit_feedback",
    "process_feedback",
    # Phase 2
    "train_user_profile",
    "ResponseEmbeddingEngine",
    "generate_response_embeddings",
    "detect_all_patterns",
    "MLTrainingPipeline",
    # Phase 3
    "PersonalityEngine",
    "real_time_mood_detection",
    "ContextAdapter",
    "PromptModifier",
    # Phase 4
    "MemoryPriorityRanker",
    "build_knowledge_graph",
    "update_memory_links",
    "ImportanceScorer",
    # Phase 5
    "ContinuousLearningPipeline",
    "RealTimeTrainer",
    "QualityMetricsComputer"
]
