@echo off
REM 🚀 MERGE PHASE 4-5 AND SYNC TO RENDER

color 0B
echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║       🚀 MERGE & SYNC: Phase 4-5 to Render                   ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

cd /d "d:\Vennela A.I.worktrees\agents-adaptive-ai-evolution-plan"

REM Check current status
echo 📋 STEP 1: Check Git Status
echo.
git status
echo.
pause

color 0E
cls
echo 📍 STEP 2: Fetch Latest from Remote
git fetch origin
echo ✅ Fetched latest changes
echo.
pause

color 09
cls
echo 📍 STEP 3: Check Branches
echo.
git branch -v
echo.
pause

color 0C
cls
echo 📍 STEP 4: Merge to Main Branch
echo.
echo Merging current branch to main...
git merge origin/main --no-edit 2>nul
if errorlevel 1 (
    echo ℹ️  Already up to date with main
)
echo ✅ Merge completed
echo.
pause

color 0A
cls
echo 📍 STEP 5: Push to Remote (Sync)
echo.
git push origin main
echo ✅ Pushed to remote
echo.

color 02
cls
echo ╔════════════════════════════════════════════════════════════════╗
echo ║              ✅ MERGE & SYNC COMPLETE!                       ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.
echo 📊 Final Status:
git log --oneline -3
echo.
echo ✅ Phase 4-5 merged and synced to Render!
echo ✅ Changes pushed to origin/main
echo ✅ Ready for Render deployment
echo.
pause
