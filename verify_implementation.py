"""Verification script - confirms all 20 modules created successfully."""

import os
import sys

base_path = r"d:\Vennela A.I.worktrees\agents-adaptive-ai-evolution-plan"

# Expected files
expected_files = [
    # Phase 1: Reinforcement (2)
    "reinforcement_reward_scorer.py",
    "reinforcement_feedback_collector.py",
    # Phase 2: ML Training (4)
    "ml_user_profile_trainer.py",
    "ml_response_embeddings.py",
    "ml_pattern_detector.py",
    "ml_training_pipeline.py",
    # Phase 3: Adaptation (4)
    "adaptation_personality_engine.py",
    "adaptation_mood_detector.py",
    "adaptation_context_adapter.py",
    "adaptation_prompt_modifier.py",
    # Phase 4: Memory Intelligence (3)
    "memory_priority_ranker.py",
    "memory_semantic_linker.py",
    "memory_importance_scorer.py",
    # Phase 5: Continuous Learning (3)
    "pipeline_continuous_learning.py",
    "pipeline_real_time_trainer.py",
    "pipeline_quality_metrics.py",
    # Orchestrators (2)
    "adaptive_ai_main.py",
    "adaptive_ai_init.py",
    # Documentation (2)
    "ADAPTIVE_AI_GUIDE.py",
    "PHASE_IMPLEMENTATION_SUMMARY.md"
]

print("=" * 80)
print("ADAPTIVE AI EVOLUTION - IMPLEMENTATION VERIFICATION")
print("=" * 80)
print()

# Check files
created = []
missing = []

for filename in expected_files:
    filepath = os.path.join(base_path, filename)
    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        created.append((filename, size))
        print(f"✓ {filename:50s} ({size:,} bytes)")
    else:
        missing.append(filename)
        print(f"✗ {filename:50s} MISSING")

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Total Expected:     {len(expected_files)}")
print(f"Created:            {len(created)}")
print(f"Missing:            {len(missing)}")
print()

if missing:
    print("MISSING FILES:")
    for f in missing:
        print(f"  - {f}")
    print()

# Calculate total size
total_size = sum(size for _, size in created)
print(f"Total Code Size:    {total_size:,} bytes ({total_size/1024:.1f} KB)")
print()

# Phase breakdown
print("PHASE BREAKDOWN:")
print(f"  Phase 1 (Reinforcement):        2 files")
print(f"  Phase 2 (ML Training):          4 files")
print(f"  Phase 3 (Adaptation):           4 files")
print(f"  Phase 4 (Memory Intelligence):  3 files")
print(f"  Phase 5 (Continuous Learning):  3 files")
print(f"  Orchestrators:                  2 files")
print(f"  Documentation:                  2 files")
print()

# Verification
if len(created) == len(expected_files):
    print("✓ ALL FILES CREATED SUCCESSFULLY!")
    print()
    print("Next Steps:")
    print("1. Review ADAPTIVE_AI_GUIDE.py for implementation details")
    print("2. Check PHASE_IMPLEMENTATION_SUMMARY.md for architecture")
    print("3. Import orchestrator: from adaptive_ai_main import get_orchestrator")
    print("4. Use: orchestrator.process_user_interaction(...)")
    print()
    sys.exit(0)
else:
    print(f"✗ {len(missing)} files missing!")
    sys.exit(1)
