#!/usr/bin/env python3
"""Test runner for Phase C Memory Reflection Cycle."""

import sys
import subprocess

if __name__ == '__main__':
    result = subprocess.run(
        [sys.executable, '-m', 'unittest', 'test_memory_reflection', '-v'],
        cwd=r'd:\Vennela A.I.worktrees\agents-adaptive-ai-evolution-plan',
        capture_output=False
    )
    sys.exit(result.returncode)
