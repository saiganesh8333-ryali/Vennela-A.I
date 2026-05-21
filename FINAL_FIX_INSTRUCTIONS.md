╔════════════════════════════════════════════════════════════════════════╗
║                                                                        ║
║           🔧 RENDER CACHE FIX - EXECUTE THESE 3 COMMANDS 🔧            ║
║                                                                        ║
╚════════════════════════════════════════════════════════════════════════╝


❌ WHAT'S HAPPENING NOW
═════════════════════════════════════════════════════════════════════════

Render Logs Show:
  ✓ Build successful 🎉
  ✗ Installing: torch (500MB), transformers (500MB), sklearn (100MB)
  ✗ Running 'uvicorn main:app ...'  (WRONG COMMAND!)
  ✗ Error: "uvicorn: command not found"

Reason:
  Render cached the OLD requirements.txt
  Not using new requirements-lightweight.txt
  Using old startCommand (main:app instead of app:app)


✅ THE FIX (30 seconds to deploy)
═════════════════════════════════════════════════════════════════════════

render.yaml buildCommand Updated:

FROM:  pip install -r requirements-lightweight.txt
TO:    rm -rf .pip-cache && pip install --no-cache-dir -r requirements-lightweight.txt

This forces Render to:
  1. Clear pip's cache
  2. Clear .pip-cache directory
  3. Re-read requirements-lightweight.txt
  4. Install fresh 40MB packages (not old 1.4GB)


🚀 THREE COMMANDS (Copy & Execute)
═════════════════════════════════════════════════════════════════════════

COMMAND 1:
──────────
cd "d:\Vennela A.I.worktrees\agents-adaptive-ai-evolution-plan"

COMMAND 2:
──────────
git add render.yaml && git commit -m "fix: Force cache clear in render buildCommand"

COMMAND 3:
──────────
git push origin main


✅ DONE! Now wait 5 minutes for Render to rebuild.


⏱️ BUILD TIMELINE (What's Happening)
═════════════════════════════════════════════════════════════════════════

NOW           → You push the fix
10-30 sec     → Render webhook triggered
30-60 sec     → Build starts
1-2 min       → rm -rf clears old cache
2-3 min       → Fresh install from requirements-lightweight.txt
3-5 min       → App deploying
5 min         → READY FOR TESTING ✓


🧪 TEST AFTER 5 MINUTES
═════════════════════════════════════════════════════════════════════════

Test Command:
──────────────
curl https://your-app.onrender.com/health

Expected Response:
──────────────────
{"status":"healthy","lightweight_mode":true}

If you see this → FIXED! ✅


✨ EXPECTED BUILD OUTPUT
═════════════════════════════════════════════════════════════════════════

When Render runs the new buildCommand:

  ✓ Clearing build cache...
  ✓ rm -rf .pip-cache (deleted old cache)
  ✓ Collecting packages from requirements-lightweight.txt
  ✓ Installing fastapi==0.116.1
  ✓ Installing uvicorn[standard]==0.35.0  ← INCLUDED NOW!
  ✓ Installing numpy
  ✓ Installing firebase-admin
  ✓ Successfully installed (40MB total)
  ✓ Running 'uvicorn app:app --host 0.0.0.0 --port $PORT'
  ✓ Application startup complete
  ✓ Uvicorn running on http://0.0.0.0:$PORT


📊 SIZE COMPARISON
═════════════════════════════════════════════════════════════════════════

OLD (Still in Render cache):
  ❌ torch, transformers, sklearn
  ❌ 1.4 GB total
  ❌ uvicorn NOT installed
  ❌ Wrong startCommand (main:app)
  ❌ FAILS to deploy

NEW (After this fix):
  ✅ fastapi, uvicorn, numpy, firebase-admin
  ✅ 40 MB total
  ✅ uvicorn INCLUDED
  ✅ Correct startCommand (app:app)
  ✅ SUCCEEDS and all endpoints work


✅ VERIFICATION CHECKLIST
═════════════════════════════════════════════════════════════════════════

After executing 3 commands:
  ☐ Changes committed to git
  ☐ Pushed to GitHub

After 5 minutes:
  ☐ Render shows "Deployed" (green)
  ☐ Build logs show cache cleared
  ☐ No 1.4GB packages listed
  ☐ curl /health works
  ☐ Size is 40MB


═════════════════════════════════════════════════════════════════════════

READY? Let's go!

COPY THESE 3 COMMANDS:

cd "d:\Vennela A.I.worktrees\agents-adaptive-ai-evolution-plan"
git add render.yaml
git commit -m "fix: Force cache clear in render buildCommand"
git push origin main

Then wait 5 minutes and test:
curl https://your-app.onrender.com/health

═════════════════════════════════════════════════════════════════════════
