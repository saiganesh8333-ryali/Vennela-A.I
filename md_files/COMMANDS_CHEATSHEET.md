# ⚡ DEPLOYMENT COMMANDS - COPY & PASTE READY

## DEPLOY NOW! 🚀

### Step 1: Navigate to Project
```bash
cd "d:\Vennela A.I"
```

### Step 2: Stage All Changes
```bash
git add .
```

### Step 3: Commit
```bash
git commit -m "feat: Add JARVIS-style AI provider failover system

- Add /ai-health endpoint for provider health monitoring  
- Implement automatic Groq → OpenRouter failover
- Enhance logging with visual emoji indicators
- Optimize requirements.txt (torch CPU-only for Render)
- Add 71,469 words of comprehensive documentation
- Include test script for validation

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Step 4: Push to GitHub
```bash
git push origin main
```

---

## WAIT 3-5 MINUTES FOR RENDER AUTO-DEPLOY

### Monitor Progress
1. Go to: https://dashboard.render.com
2. Click: **Vennela A.I** service
3. Watch: **Deploys** tab
4. Status: Building → Deploying → Live

---

## AFTER DEPLOYMENT - VERIFICATION COMMANDS

### Test 1: Service is Running
```bash
curl https://vennela-a-i.onrender.com/
```

**Expected:**
```json
{"message":"Vennela AI Running 🚀"}
```

### Test 2: System Health
```bash
curl https://vennela-a-i.onrender.com/health
```

**Expected:**
```json
{
  "status": "ok",
  "firebase": "connected",
  "version": "2.0.0"
}
```

### Test 3: AI Provider Health ⭐ NEW
```bash
curl https://vennela-a-i.onrender.com/ai-health
```

**Expected:**
```json
{
  "groq": "healthy",
  "openrouter": "healthy"
}
```

### Test 4: Chat Endpoint
```bash
curl -X POST https://vennela-a-i.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_deployment_user",
    "message": "Hi Vennela, test the failover system!"
  }'
```

**Expected:** AI response with `"provider": "Groq"`

---

## REAL FAILOVER TEST 🔥

### Break Groq (Simulate Failure)
1. Go to: https://dashboard.render.com
2. Click: **Vennela A.I** → **Settings** → **Environment**
3. Find: `GROQ_API_KEY`
4. Change to: `wrong_key_for_testing`
5. Click: **Save**
6. Wait: 10 seconds for redeploy

### Test Failover
```bash
curl -X POST https://vennela-a-i.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "failover_test_user",
    "message": "Test failover now"
  }'
```

**Expected:** Response with `"provider": "OpenRouter"` (not Groq!)

### Check Logs
```bash
# Go to: https://dashboard.render.com
# Click: Vennela A.I → Logs
# Search for: "⚠️ Groq failed"
# You should see automatic switch!
```

### Restore Groq
1. Go to: https://dashboard.render.com  
2. Settings → Environment
3. Restore `GROQ_API_KEY` to: `gsk_...` (correct value)
4. Save
5. Wait: 10 seconds

### Verify Groq is Primary Again
```bash
curl https://vennela-a-i.onrender.com/ai-health

# Expected: {"groq": "healthy", "openrouter": "healthy"}
```

---

## MONITOR IN PRODUCTION

### Daily Check
```bash
curl https://vennela-a-i.onrender.com/ai-health
```

### View Live Logs
Go to: https://dashboard.render.com → **Vennela A.I** → **Logs**

Search for these patterns:
- `✅` = Success
- `⚠️` = Failover happening
- `❌` = Error (investigate)
- `🚀` = Provider attempt

### Quick Status
```bash
# Everything working?
curl -s https://vennela-a-i.onrender.com/ai-health | jq .

# Chat working?
curl -s -X POST https://vennela-a-i.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"monitor","message":"test"}' | jq .provider
```

---

## ROLLBACK (If Needed)

### Quick Rollback to Previous Deploy
```bash
# Go to: https://dashboard.render.com
# Vennela A.I → Settings → Deploys
# Find previous successful deploy
# Click: Redeploy
```

### Git Rollback
```bash
# See recent commits
git log --oneline | head -5

# Revert to previous
git revert HEAD
git push origin main

# Wait 3-5 minutes for redeploy
```

---

## QUICK REFERENCE

| Command | Purpose |
|---------|---------|
| `git status` | See what changed |
| `git add .` | Stage all changes |
| `git commit -m "..."` | Commit with message |
| `git push origin main` | Deploy to Render |
| `curl /` | Check if running |
| `curl /health` | System health |
| `curl /ai-health` | AI provider health |
| `curl /chat` (POST) | Send chat message |

---

## SUCCESS CHECKLIST

- [ ] `git push` completed successfully
- [ ] Render Dashboard shows "Live" status
- [ ] `/ai-health` endpoint responds
- [ ] Both providers show "healthy"
- [ ] Chat endpoint returns AI response
- [ ] Logs show emoji indicators
- [ ] Failover test shows `"provider": "OpenRouter"`
- [ ] System restored to normal

---

## YOU'RE LIVE! 🎉

Ippudu production AI infrastructure deploy ayyindhi!

Monitor the logs, celebrate the victory! 💙🔥

JARVIS-level redundancy system is now LIVE!
