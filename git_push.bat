@echo off
REM Git Push Commands for Vennela A.I
REM Windows Batch Script

echo.
echo ========================================
echo  VENNELA A.I - GIT PUSH COMMANDS
echo ========================================
echo.

REM Step 1: Navigate to project
cd /d "d:\Vennela A.I.worktrees\agents-adaptive-ai-evolution-plan"

REM Step 2: Check status
echo [1/5] Checking git status...
echo.
git status
echo.
pause

REM Step 3: Add all changes
echo [2/5] Adding all changes...
git add .
echo Git add complete!
echo.
pause

REM Step 4: Show what's staged
echo [3/5] Showing staged changes...
git status
echo.
pause

REM Step 5: Commit
echo [4/5] Committing changes...
git commit -m "Update render.yaml with Vennela A.I configuration and API key setup - Added Gemini API configuration (Primary LLM - Phase A) - Added Groq API fallback configuration - Added OpenRouter API final fallback - Configured all 7 phases (B through G) - Added comprehensive environment variables - Updated startCommand for Python - Added deployment documentation"
echo.
pause

REM Step 6: Push
echo [5/5] Pushing to remote repository...
git push origin main
echo.
echo ========================================
echo  GIT PUSH COMPLETE! 
echo ========================================
echo.
git log -1 --oneline
echo.
pause
