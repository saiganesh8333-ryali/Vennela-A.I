#!/bin/bash
# Git Commands - Vennela A.I Deployment

# Navigate to project directory
cd "d:\Vennela A.I.worktrees\agents-adaptive-ai-evolution-plan"

# Step 1: Check what changed
echo "📋 Checking git status..."
git status

# Step 2: Add all changes
echo "📦 Adding all changes..."
git add .

# Step 3: Check what's staged
echo "✅ Staged changes:"
git status

# Step 4: Commit with message
echo "💾 Committing changes..."
git commit -m "Update render.yaml with Vennela A.I configuration and API key setup

- Added Gemini API configuration (Primary LLM - Phase A)
- Added Groq API fallback configuration
- Added OpenRouter API final fallback
- Configured all 7 phases (B through G)
- Added comprehensive environment variables
- Updated startCommand for Python
- Added deployment documentation

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

# Step 5: Push to remote
echo "🚀 Pushing to remote repository..."
git push origin main

# Step 6: Verify push
echo "✅ Push complete!"
git log -1 --oneline
