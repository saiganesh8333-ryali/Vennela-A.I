# ✅ AI Provider Failover System - Deployment Checklist

## Pre-Deployment

- [ ] **Verify API Keys Exist**
  ```bash
  # In your terminal
  echo $GROQ_API_KEY
  echo $OPENROUTER_API_KEY
  ```
  Both should output non-empty strings

- [ ] **Code Review**
  - [ ] Check `main.py` `/ai-health` endpoint
  - [ ] Check `ai_router.py` failover logic
  - [ ] Review error handling

- [ ] **Local Testing** (Optional)
  ```bash
  cd "d:\Vennela A.I"
  python -m pytest test_failover.py -v
  # OR
  python test_failover.py
  ```

---

## Render Dashboard Configuration

### Step 1: Verify Environment Variables

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Select your **Vennela A.I** service
3. Click **Settings** → **Environment**
4. Confirm these variables exist:
   - [ ] `GROQ_API_KEY` = `gsk_...`
   - [ ] `OPENROUTER_API_KEY` = `sk-or-v1-...`
5. If missing, add them and click **Save**

### Step 2: Check Deployment Settings

1. In Settings tab, scroll to **Build & Deploy**
2. Confirm Auto-deploy from GitHub is enabled
3. Note your service URL (e.g., `https://vennela-a-i.onrender.com`)

---

## Deployment Steps

### Option A: Automatic Deploy (via GitHub)

```bash
# From your local repo
git add ai_router.py main.py FAILOVER_SYSTEM.md test_failover.py
git commit -m "feat: Add JARVIS-style AI provider failover system

- Add /ai-health health check endpoint
- Enhance logging with emoji indicators
- Implement production-level failover logic
- Add comprehensive documentation

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

git push origin main
```

Then:
- [ ] Wait 2-3 minutes for Render to detect and deploy
- [ ] Go to Render Dashboard and verify deployment in progress
- [ ] Check logs for successful deployment

### Option B: Manual Deploy

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Select **Vennela A.I** service
3. Click **Manual Deploy** button
4. [ ] Wait for deployment to complete (watch logs)

---

## Post-Deployment Verification

### Step 1: Check Service Status

```bash
# Should show "Vennela AI Running 🚀"
curl https://vennela-a-i.onrender.com/

# Expected output:
# {"message":"Vennela AI Running 🚀"}
```

[ ] Service is running

### Step 2: Test General Health

```bash
curl https://vennela-a-i.onrender.com/health

# Expected output:
# {
#   "status": "ok",
#   "firebase": "connected",
#   "version": "2.0.0"
# }
```

[ ] General health endpoint working

### Step 3: Test AI Provider Health

```bash
curl https://vennela-a-i.onrender.com/ai-health

# Expected output:
# {
#   "groq": "healthy",
#   "openrouter": "healthy"
# }
# OR at minimum, one should be "healthy"
```

Possible outputs:
- [ ] Both providers healthy: `{"groq": "healthy", "openrouter": "healthy"}`
- [ ] One provider down: `{"groq": "failed: ...", "openrouter": "healthy"}`
- [ ] Keys not configured: `{"groq": "not_configured", "openrouter": "not_configured"}`

### Step 4: Test Chat Endpoint (Failover in Action)

```bash
curl -X POST https://vennela-a-i.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_failover_user",
    "message": "Hi Vennela! Test the failover system for me"
  }'

# Expected: AI response with provider info
# {
#   "reply": "...",
#   "provider": "Groq",
#   "latency_ms": 450,
#   "error": null
# }
```

[ ] Chat endpoint working

### Step 5: Monitor Logs

1. Go to Render Dashboard → **Vennela A.I** → **Logs**
2. Look for these messages:
   ```
   🚀 Attempting to use Groq provider...
   ✅ Successfully using Groq
   ✅ Groq response received from llama-3.3-70b-versatile in X.XXs
   ```

[ ] Logs show successful provider usage

---

## Testing Failover Behavior

### Test 1: Verify Groq is Primary

The `/ai-health` should show Groq as `"healthy"` if keys are valid.

[ ] Groq is working as primary provider

### Test 2: Simulate Groq Failure (Optional - Advanced)

⚠️ **Only do this if you want to test the fallback!**

1. Temporarily set `GROQ_API_KEY` to an invalid value in Render Dashboard
2. Save and redeploy
3. Test `/ai-health` - should show Groq failed
4. Test `/chat` - should still work but use OpenRouter
5. Check logs for: `⚠️ Groq failed, switching to OpenRouter fallback...`
6. Restore the correct `GROQ_API_KEY` and redeploy

- [ ] Failover to OpenRouter works correctly
- [ ] Restore original API key and redeploy

---

## Monitoring & Maintenance

### Daily Checks

- [ ] Service is up: `curl https://vennela-a-i.onrender.com/`
- [ ] AI health is good: `curl https://vennela-a-i.onrender.com/ai-health`
- [ ] Check Render logs for any errors or warnings

### Weekly Checks

- [ ] Review Render logs for patterns
- [ ] Check provider status pages:
  - [ ] [Groq Status](https://status.groq.com)
  - [ ] [OpenRouter Status](https://status.openrouter.ai) (if available)
- [ ] Monitor API usage and costs

### Monthly Checks

- [ ] Review failover frequency
- [ ] Update documentation if needed
- [ ] Test failover scenario (see Test 2 above)

---

## Troubleshooting

### Issue: `/ai-health` shows both as "not_configured"

**Steps:**
1. Verify env vars in Render Dashboard Settings → Environment
2. Ensure keys are copy-pasted correctly (no extra spaces)
3. Redeploy
4. Check again in 2-3 minutes

### Issue: Persistent Groq failures

**Check:**
1. Is Groq API key still valid? Try in [Groq Console](https://console.groq.com)
2. Check Groq service status
3. Check rate limits on your Groq account
4. Review Render logs for detailed error messages

### Issue: All requests falling back to OpenRouter

**Steps:**
1. Check `/ai-health` to see which provider is down
2. Review logs in Render Dashboard for error patterns
3. Check provider-specific status pages
4. Contact provider support if issues persist

### Issue: 500 Errors in Chat Endpoint

**Debug:**
1. Check Render logs for full error stack trace
2. Verify Firebase is configured
3. Check that both AI providers are working via `/ai-health`
4. Look for rate limit errors

---

## Rollback Plan

If deployment causes issues:

### Quick Rollback

1. Go to Render Dashboard
2. Click **Settings** → **Deploys**
3. Find previous successful deploy
4. Click "Redeploy" on that version
5. Verify service recovers

### Git Rollback

If you need to revert code changes:

```bash
# See recent commits
git log --oneline | head -5

# Revert to previous version
git revert HEAD
git push origin main

# Or reset to specific commit
git reset --hard <commit_sha>
git push origin main --force
```

---

## Success Criteria ✅

Deployment is successful when:

- [ ] Service status: "UP"
- [ ] `/health` responds with status: "ok"
- [ ] `/ai-health` shows at least one provider as "healthy"
- [ ] `/chat` endpoint works and returns AI responses
- [ ] Logs show `✅ Successfully using Groq` or similar
- [ ] No critical errors in Render logs
- [ ] Response latency is <3 seconds

---

## Documentation

- 📚 Full system documentation: [FAILOVER_SYSTEM.md](./FAILOVER_SYSTEM.md)
- 🧪 Test script: `test_failover.py`
- 📝 API endpoints:
  - `GET /` - Status check
  - `GET /health` - System health
  - `GET /ai-health` - AI providers health
  - `POST /chat` - Chat with AI

---

## Sign-Off

- **Deployer:** _______________
- **Date:** _______________
- **Status:** [ ] Ready for Production

---

**Questions?** Check [FAILOVER_SYSTEM.md](./FAILOVER_SYSTEM.md) for detailed documentation.
