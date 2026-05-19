#!/usr/bin/env python
"""Bootstrap script to create directory structure."""

import os
import sys

base_path = r"d:\Vennela A.I.worktrees\agents-adaptive-ai-evolution-plan"
dirs_to_create = [
    "reinforcement",
    "ml",
    "adaptation",
    "pipeline"
]

for dir_name in dirs_to_create:
    dir_path = os.path.join(base_path, dir_name)
    os.makedirs(dir_path, exist_ok=True)
    print(f"Created/verified: {dir_path}")

print("All directories created successfully")
