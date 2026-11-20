# 🚀 Render Deployment Guide - Vennela A.I

## Updated Configuration

`render.yaml` has been updated with all necessary environment variables for Vennela A.I Evolution framework.

---

## 📋 Required Environment Variables to Set in Render

Add these in **Render Dashboard → Your Service → Environment**:

### 1. **Gemini API (Required)**
```
GEMINI_API_KEY = your_actual_gemini_api_key_here
```
- Get from: https://aistudio.google.com/app/apikey
- This is your PRIMARY LLM provider

### 2. **Groq API (Fallback)**
```
GROQ_API_KEY = your_groq_api_key_here
```
- Get from: https://console.groq.com
- Used as fallback when Gemini unavailable

### 3. **OpenRouter API (Final Fallback)**
```
OPENROUTER_API_KEY = your_openrouter_api_key_here
```
- Get from: https://openrouter.ai
- Used as final fallback

### 4. **Vennela Prompt (Optional)**
```
VENNELA_PROMPT = your_custom_system_prompt_here
```
- Default: Professional AI assistant prompt

### 5. **Firebase (Optional)**
```
FIREBASE_CREDENTIALS_JSON = your_firebase_json_here
```
- Only if using Firebase for data storage

---

## 🔧 How to Set Variables in Render

### Method 1: Dashboard UI (Easiest)

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Select your **vennela-ai** service
3. Click **Settings** tab
4. Scroll to **Environment**
5. Click **Add Environment Variable**
6. Add one by one:
   - Key: `GEMINI_API_KEY`
   - Value: `AIza_xxxxx...` (your actual key)
7. Click **Save** for each
8. Service auto-restarts

### Method 2: CLI (Advanced)

```bash
# If using Render CLI
render env set GEMINI_API_KEY "your_key_here"
render env set GROQ_API_KEY "your_key_here"
render env set OPENROUTER_API_KEY "your_key_here"
```

---

## ✅ render.yaml Configuration

The file now includes:

### **Phase A: Multi-LLM Router**
```yaml
LLM_ROUTER_ENABLED: "true"
COST_TRACKING_ENABLED: "true"
HEALTH_CHECK_INTERVAL_SECONDS: "300"
```

### **Phase B: Event Bus**
```yaml
EVENT_BUS_ENABLED: "true"
EVENT_HISTORY_MAX_SIZE: "1000"
EVENT_QUEUE_MAX_SIZE: "10000"
```

### **Phase C: Memory Reflection**
```yaml
MEMORY_REFLECTION_ENABLED: "true"
CONSOLIDATION_INTERVAL_MINUTES: "5"
IMPORTANCE_THRESHOLD: "0.3"
```

### **Phase D: Voice Pipeline**
```yaml
VOICE_PIPELINE_ENABLED: "true"
WAKEWORD_DETECTION_ENABLED: "true"
WAKEWORD_THRESHOLD: "0.85"
```

### **Phase E: Learning**
```yaml
LEARNING_LOOP_ENABLED: "true"
REINFORCEMENT_ENABLED: "true"
```

### **Phase F: Personality**
```yaml
PERSONALITY_ADAPTATION_ENABLED: "true"
MOOD_DETECTION_ENABLED: "true"
```

### **Phase G: Intent Prediction**
```yaml
INTENT_PREDICTION_ENABLED: "true"
PATTERN_DETECTION_ENABLED: "true"
```

---

## 🚀 Deployment Steps

1. **Push to Git:**
   ```bash
   git add render.yaml
   git commit -m "Update render.yaml with all environment variables"
   git push origin main
   ```

2. **Add API Keys in Render Dashboard:**
   - Go to Render Dashboard
   - Select vennela-ai service
   - Settings → Environment
   - Add each key manually

3. **Deploy:**
   - Click **Deploy latest**
   - Service starts with new configuration
   - All 7 phases automatically enabled

4. **Verify:**
   - Check logs for successful startup
   - Look for "All environment variables loaded" message

---

## 🔐 Security Notes

### ✅ What's Safe
- Configuration values (like thresholds, intervals)
- Public API endpoints
- Default model names

### ❌ What's NOT Safe
- API keys in `.env` files
- Credentials in source code
- Secrets in git history

### ✅ Render Best Practices
- Use Render Dashboard for sensitive values
- Never commit API keys to git
- Use `sync: false` for secrets in render.yaml
- Rotate keys regularly

---

## 📝 Minimal Setup Example

If you want to start with just the basics:

```yaml
envVars:
  # REQUIRED
  - key: GEMINI_API_KEY
    sync: false
  
  # RECOMMENDED
  - key: GROQ_API_KEY
    sync: false
  
  # OPTIONAL BACKUPS
  - key: OPENROUTER_API_KEY
    sync: false
  
  # ALL OTHER CONFIGS (can keep defaults)
```

---

## 🧪 Test After Deployment

After deployment, verify everything works:

```bash
# Check logs in Render dashboard
# Look for:
# ✅ "All environment variables loaded"
# ✅ "Multi-LLM router initialized"
# ✅ "Event bus started"
# ✅ "Memory reflection enabled"
```

Or test via API:

```bash
curl https://vennela-ai.onrender.com/health
```

Expected response:
```json
{
  "status": "ok",
  "phases": {
    "router": "enabled",
    "event_bus": "enabled",
    "memory": "enabled",
    "voice": "enabled"
  }
}
```

---

## 🆘 Troubleshooting

| Problem | Solution |
|---------|----------|
| "API key not found" | Check Render Dashboard, add GEMINI_API_KEY |
| "Service crashes on start" | Check logs, verify all keys are set correctly |
| "Router not working" | Ensure GEMINI_API_KEY is valid and active |
| "Events not processing" | Check EVENT_BUS_ENABLED is "true" |

---

## 📊 render.yaml Structure

```
services:
  - type: web
    name: vennela-ai
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: python main.py
    
    envVars:
      # API Keys (sync: false = manual input)
      - key: GEMINI_API_KEY
        sync: false
      
      # Configuration (values or sync: false)
      - key: LLM_ROUTER_ENABLED
        value: "true"
      
      # Firebase (optional)
      - key: FIREBASE_ENABLED
        value: "false"
```

---

## ✅ Deployment Checklist

- [ ] `render.yaml` updated with all environment variables
- [ ] Git push done (git add, commit, push)
- [ ] GEMINI_API_KEY added in Render Dashboard
- [ ] GROQ_API_KEY added in Render Dashboard (optional)
- [ ] Service deployed
- [ ] Logs show "started successfully"
- [ ] All 7 phases enabled and working

---

## 📚 Related Documentation

- **[FINAL_COMPLETION_REPORT.txt](FINAL_COMPLETION_REPORT.txt)** - Overview
- **[IMPLEMENTATION_COMPLETE.md](IMPLEMENTATION_COMPLETE.md)** - Full guide
- **[PHASE_A_IMPLEMENTATION.md](PHASE_A_IMPLEMENTATION.md)** - LLM routing details

---

## 🎯 Summary

✅ render.yaml updated with all environment variables
✅ Ready for Render deployment
✅ All 7 phases configured
✅ Just add your API keys in Render Dashboard

**Next Steps:**
1. Get your Gemini API key from https://aistudio.google.com/app/apikey
2. Go to Render Dashboard and add it as environment variable
3. Deploy and monitor logs

**Status: Ready for Production Deployment** 🚀
