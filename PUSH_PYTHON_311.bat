@echo off
REM 🚀 PYTHON 3.11 UPDATE - PowerShell Compatible

cd /d "d:\Vennela A.I.worktrees\agents-adaptive-ai-evolution-plan"

echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║    🚀 PUSH PYTHON 3.11 UPDATE                                ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

echo Step 1: Add runtime.txt
git add runtime.txt
echo.

echo Step 2: Commit
git commit -m "Update Python: 3.14 → 3.11"
echo.

echo Step 3: Push
git push origin main
echo.

echo ✅ Done! Python 3.11 update pushed to Render
echo Wait 10 minutes for deployment
pause
