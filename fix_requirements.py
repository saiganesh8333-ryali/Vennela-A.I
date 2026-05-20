import shutil
import os

# Fix corrupted requirements.txt
src = "requirements.txt.new"
dst = "requirements.txt"

if os.path.exists(src):
    shutil.copy(src, dst)
    print(f"Copied {src} to {dst}")
    
    # Verify the file
    with open(dst, 'r') as f:
        content = f.read()
        print(f"requirements.txt now contains:\n{content}")
else:
    print(f"{src} not found")
