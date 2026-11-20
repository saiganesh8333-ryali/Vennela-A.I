@echo off
REM 🚀 FIX: Git push rejection - Force push to main

cd /d "d:\Vennela A.I.worktrees\agents-adaptive-ai-evolution-plan"

echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║    🚀 FIX: Force Push to Main                                ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

echo Current branch:
git branch
echo.

echo Pushing updated branch to main with force...
git push origin updated:main --force

echo.
echo ✅ Done! All changes pushed to main
pause
