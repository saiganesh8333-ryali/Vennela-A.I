#!/usr/bin/env python3
"""
Emergency fix for requirements.txt - replaces with lightweight version
This script removes heavy dependencies that cause Render build failures
"""
import os

repo_dir = r'd:\Vennela A.I.worktrees\agents-adaptive-ai-evolution-plan'
req_file = os.path.join(repo_dir, 'requirements.txt')

lightweight_content = """# Web framework
fastapi==0.116.1
uvicorn[standard]==0.35.0
gunicorn

# Firebase
firebase-admin
google-cloud-firestore
google-api-core

# Core data processing (lightweight - no torch/transformers/sklearn)
numpy

# Environment config
python-dotenv

# LLM API
google-generativeai

# Heavy ML libraries replaced with lightweight Python modules:
# - sentence-transformers (200MB) -> lightweight_embeddings.py
# - transformers (500MB) -> lightweight_nlp.py
# - torch (500MB) -> numpy
# - scikit-learn (100MB) -> lightweight_ml.py
# This reduces deployment size from 1.3GB to ~30MB
"""

try:
    # Write the lightweight version
    with open(req_file, 'w') as f:
        f.write(lightweight_content)
    
    # Verify
    with open(req_file, 'r') as f:
        content = f.read()
    
    if 'scikit-learn' in content or 'torch' in content or 'transformers' in content or 'sentence-transformers' in content:
        print("❌ ERROR: Heavy dependencies still present!")
        exit(1)
    
    print("✅ Successfully updated requirements.txt")
    print("✅ Removed: scikit-learn, torch, transformers, sentence-transformers")
    print("✅ Kept: fastapi, uvicorn, firebase, numpy, python-dotenv, google-generativeai")
    print("\n📌 Next steps:")
    print("   1. git add requirements.txt")
    print("   2. git commit -m 'Fix: Remove heavy dependencies for Render deployment'")
    print("   3. git push origin main")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
