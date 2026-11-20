#!/usr/bin/env python3
"""Setup script to create necessary directories for Vennela AI evolution."""

import os
import sys

def create_directories():
    """Create all necessary directories for the evolution phases."""
    directories = [
        r'd:\Vennela A.I.worktrees\agents-adaptive-ai-evolution-plan\reinforcement',
        r'd:\Vennela A.I.worktrees\agents-adaptive-ai-evolution-plan\ml',
        r'd:\Vennela A.I.worktrees\agents-adaptive-ai-evolution-plan\adaptation',
        r'd:\Vennela A.I.worktrees\agents-adaptive-ai-evolution-plan\pipeline',
        r'd:\Vennela A.I.worktrees\agents-adaptive-ai-evolution-plan\models',
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f'✓ Created/verified: {directory}')
    
    print('\n✓ All directories ready!')

if __name__ == '__main__':
    create_directories()
