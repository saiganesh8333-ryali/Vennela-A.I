#!/usr/bin/env python3
import os
import shutil

repo_dir = r'd:\Vennela A.I.worktrees\agents-adaptive-ai-evolution-plan'
old_file = os.path.join(repo_dir, 'requirements.txt')
new_file = os.path.join(repo_dir, 'requirements_new.txt')

try:
    # Remove old corrupted file
    if os.path.exists(old_file):
        os.remove(old_file)
        print(f"✓ Removed corrupted {old_file}")
    
    # Copy new file to requirements.txt
    shutil.copy(new_file, old_file)
    print(f"✓ Created clean {old_file}")
    
    # Remove temp file
    os.remove(new_file)
    print(f"✓ Cleaned up temp file")
    
    # Verify
    with open(old_file, 'r') as f:
        content = f.read()
        if 'scikit-learn' in content:
            print("✗ ERROR: scikit-learn still in requirements.txt!")
        else:
            print("✓ scikit-learn successfully removed")
            print(f"✓ requirements.txt ready for commit")
            
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
