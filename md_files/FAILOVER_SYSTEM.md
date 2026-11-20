# 🚀 AI Provider Failover System - JARVIS-Style Redundancy

## Overview

This document describes the production-level AI provider failover system implemented in Vennela A.I. The system ensures maximum uptime and reliability by automatically switching between multiple AI providers.

---

## Architecture 🏗️

### Providers

```
PRIMARY: Groq (llama-3.3-70b-versatile)
         ↓
         If fails...
         ↓
FALLBACK: OpenRouter (openai/gpt-4o-mini)
```

### Production Flow

```
User sends message
    ↓
Check rate limits
    ↓
Load user memory & context
    ↓
Try GROQ
    ├─ Success? → Return response (provider: "Groq")
    └─ Failed? → Continue
        ↓
        Try OPENROUTER
        ├─ Success? → Return response (provider: "OpenRouter")
        └─ Failed? → Return friendly error
```

---

## Health Check Endpoint 🏥

### Request

```bash
GET https://vennela-a-i.onrender.com/ai-health
```

### Response - Both Healthy

```json
{
  "groq": "healthy",
  "openrouter": "healthy"
}
```

### Response - Groq Down

```json
{
  "groq": "failed: Connection timeout",
  "openrouter": "healthy"
}
```

### Response - Not Configured

```json
{
  "groq": "not_configured",
  "openrouter": "not_configured"
}
```

---

## Logging & Monitoring 📊

All failover events are logged with emojis for easy identification:

### Success Indicators ✅

```
✅ Groq provider is healthy
✅ Successfully using Groq
✅ Successfully switched to OpenRouter
✅ Groq response received from llama-3.3-70b-versatile in 0.45s
✅ OpenRouter response received in 0.82s (FALLBACK SUCCESS)
```

### Warning/Error Indicators ⚠️

```
⚠️ Groq health check failed: Connection error
⚠️ Groq client not initialized - API key missing or invalid
🚀 Attempting to use Groq provider...
⚠️ Groq failed, switching to OpenRouter fallback...
📤 Sending request to Groq model llama-3.1-8b-instant...
🔌 Groq connection error: Timeout
⏱️ Groq rate limit hit
❌ CRITICAL: Both Groq and OpenRouter failed - no AI providers available
```

### View Logs

In Render Dashboard:
1. Go to your service
2. Click "Logs" tab
3. Search for these emoji patterns to track failover events in real-time

---

## Environment Variables 🔑

Required in Render Dashboard or `.env`:

```bash
GROQ_API_KEY=gsk_...
OPENROUTER_API_KEY=sk-or-v1-...
```

Optional (defaults provided):

```bash
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_FALLBACK_MODEL=llama-3.1-8b-instant
OPENROUTER_MODEL=openai/gpt-4o-mini
AI_TEMPERATURE=0.7
AI_TIMEOUT_SECONDS=30
```

---

## Testing the System 🧪

### 1. Health Check

```bash
curl https://vennela-a-i.onrender.com/ai-health
```

### 2. Chat with Primary Provider (Groq)

```bash
curl -X POST https://vennela-a-i.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user_1",
    "message": "Hi Vennela, how are you?"
  }'
```

Watch logs in Render Dashboard - you should see:
```
🚀 Attempting to use Groq provider...
📤 Sending request to Groq model llama-3.3-70b-versatile...
✅ Successfully using Groq
```

### 3. Force Failover Testing

Temporarily disable Groq API key in Render Dashboard, then test chat. You should see:
```
🚀 Attempting to use Groq provider...
⚠️ Groq failed, switching to OpenRouter fallback...
✅ Successfully switched to OpenRouter
```

---

## Implementation Details 💻

### Files Modified

1. **main.py**
   - Added `/ai-health` endpoint for provider health monitoring
   - Health check tests both providers with minimal requests
   - Returns clear status for each provider

2. **ai_router.py**
   - Enhanced logging with emojis for better visibility
   - Clear failover flow documentation
   - Individual try-catch blocks for each provider

### Key Functions

#### `get_ai_response(messages: list)`

Main entry point - orchestrates the failover logic:
- Tries Groq first
- Falls back to OpenRouter if Groq fails
- Returns appropriate response with provider info
- Logs all transitions with emoji indicators

#### `_try_groq(messages: list)`

Attempts Groq with:
- Primary model (llama-3.3-70b-versatile)
- Fallback model (llama-3.1-8b-instant) if primary fails
- Detailed error logging for debugging

#### `_try_openrouter(messages: list)`

Fallback provider implementation with:
- Graceful error handling
- Clear logging indicating fallback success
- Same interface as Groq for consistency

---

## Response Format 📝

### Chat Response Structure

```python
{
  "reply": "Response text from AI",
  "provider": "Groq" | "OpenRouter" | "error" | "none",
  "relevant_memory": "Previous context about user",
  "memory_summary": "Updated user profile",
  "latency_ms": 450,
  "error": null | "error_message"
}
```

### Provider Values

- `"Groq"` - Primary provider succeeded
- `"OpenRouter"` - Fallback provider used successfully
- `"error"` - Unexpected error occurred
- `"none"` - Both providers unavailable

---

## Deployment 🚀

### Step 1: Push Changes

```bash
git add ai_router.py main.py
git commit -m "feat: Add JARVIS-style AI provider failover system"
git push origin main
```

### Step 2: Deploy to Render

Option A - Automatic (if webhook configured):
- Push automatically triggers deploy

Option B - Manual:
1. Go to [Render Dashboard](https://dashboard.render.com)
2. Select your service
3. Click "Manual Deploy"

### Step 3: Verify Deployment

```bash
# Check service is running
curl https://vennela-a-i.onrender.com/health

# Test AI health
curl https://vennela-a-i.onrender.com/ai-health

# Test chat endpoint
curl -X POST https://vennela-a-i.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "message": "hello"}'
```

---

## Troubleshooting 🔧

### Issue: `/ai-health` shows both providers as "not_configured"

**Solution**: Verify environment variables in Render Dashboard:
1. Go to Settings → Environment
2. Confirm `GROQ_API_KEY` is set
3. Confirm `OPENROUTER_API_KEY` is set
4. Redeploy service

### Issue: Always falling back to OpenRouter

**Possible causes**:
- Groq API key expired/revoked
- Groq service experiencing outages
- Rate limit exceeded

**Check logs**:
1. View Render logs
2. Search for "Groq API error" to see specific error
3. Check API dashboards at groq.com and openrouter.ai

### Issue: Both providers fail

**Actions**:
1. Check `/ai-health` endpoint response
2. Verify API keys are still valid
3. Check Render service logs for connection errors
4. Review API provider status pages
5. Consider implementing circuit breaker pattern for future enhancements

---

## Performance Metrics ⚡

### Expected Response Times

- **Groq**: 0.3-1.5 seconds (very fast)
- **OpenRouter**: 0.5-2.0 seconds (good fallback)
- **Failover Detection**: <100ms
- **Total max latency**: ~2.5 seconds for user-visible response

### Rate Limits

- **Groq**: Check your plan at groq.com
- **OpenRouter**: Check your plan at openrouter.ai
- **Vennela Rate Limit**: 100 requests per minute per user (configurable)

---

## Future Enhancements 🔮

1. **Circuit Breaker Pattern**
   - Temporarily disable failing provider
   - Prevent cascading failures
   - Automatic recovery checks

2. **Weighted Routing**
   - Route based on provider health scores
   - Cost optimization
   - Load balancing

3. **Provider Metrics Dashboard**
   - Track success rates
   - Monitor latency trends
   - Cost tracking

4. **More Providers**
   - Azure OpenAI
   - Anthropic Claude
   - Cohere
   - Local LLM fallback

---

## References 📚

- [Groq API Docs](https://console.groq.com/docs)
- [OpenRouter Docs](https://openrouter.ai/docs)
- [FastAPI Error Handling](https://fastapi.tiangolo.com/tutorial/handling-errors/)
- [Python Logging Best Practices](https://docs.python.org/3/howto/logging.html)

---

**Status**: ✅ Production Ready

Last Updated: 2026-05-15
