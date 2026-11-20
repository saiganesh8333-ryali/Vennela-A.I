# ⚡ Quick Start Guide - Vennela AI v2.0

Get Vennela AI running in **5 minutes** 🚀

---

## 🎯 Prerequisites Check

```bash
# Python 3.8+
python --version

# Git
git --version
```

---

## 📦 Step 1: Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt

# Download ML models (~800MB, one-time)
python -c "
from transformers import pipeline
print('Downloading emotion model...')
pipeline('text-classification', model='j-hartmann/emotion-english-distilroberta-base')
print('Downloading sentiment model...')
pipeline('sentiment-analysis')
print('✅ Models ready!')
"
```

**⏱️ Time: 2-3 minutes**

---

## 🔑 Step 2: Setup Environment

```bash
# Copy config template
cp .env.example .env

# Edit .env with your keys
# Windows: notepad .env
# Mac/Linux: nano .env
```

**Required keys to add:**
```env
GROQ_API_KEY=sk-xxxx-from-https-console-groq-com
OPENROUTER_API_KEY=sk-xxxx-from-https-openrouter-ai
```

Get API keys:
- **Groq**: https://console.groq.com (free $5/month)
- **OpenRouter**: https://openrouter.ai (free tier available)

---

## 🔐 Step 3: Firebase Setup

```bash
# Download Firebase service account JSON from:
# Firebase Console → Project Settings → Service Accounts → Generate New Private Key

# Save it in project folder:
# Windows: Place serviceAccount.json in project root
# Mac/Linux: Same location

# Alternative: Set in .env
FIREBASE_CREDENTIALS=/path/to/serviceAccount.json
```

---

## ✅ Step 4: Validate Setup

```bash
python validate_setup.py
```

**Expected output:**
```
🧠 VENNELA AI - Setup Validation

Checking: Python Version
✅ Python version: 3.10

Checking: Project Files
✅ main.py
✅ ai_router.py
...

Checking: Dependencies
✅ fastapi
✅ uvicorn
...

Checking: Environment Variables
✅ All required environment variables set

Checking: Firebase Credentials
✅ Firebase credentials: vennela-firebase-key.json

==================================================
✅ All checks passed! Ready to run.

Start server with:
  uvicorn main:app --reload
```

---

## 🚀 Step 5: Run the Server

```bash
# Development mode (auto-reload)
uvicorn main:app --reload

# Production mode (4 workers)
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

**You should see:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Starting Vennela AI...
INFO:     Using existing Firebase app instance
INFO:     Vennela AI startup complete
```

---

## 💬 Step 6: Test the API

Open another terminal and test:

```bash
# Health check
curl http://localhost:8000/health

# Send a message
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user1",
    "message": "Hi, my name is Alice and I want to learn AI"
  }'

# Get user memory
curl http://localhost:8000/memory/user1
```

**Expected response:**
```json
{
  "reply": "That's wonderful, Alice! I'd love to help you learn AI...",
  "provider": "Groq",
  "relevant_memory": null,
  "memory_summary": "User name: Alice | ...",
  "latency_ms": 2345
}
```

---

## 🎉 Success!

Your Vennela AI is running! 

**Next steps:**
- Read full docs: `README.md`
- See setup details: `PRODUCTION_UPGRADE_SUMMARY.md`
- Check API reference: `README.md` → API Reference section

---

## ⚠️ Troubleshooting

### Issue: "GROQ_API_KEY not found"
**Solution:**
- Make sure `.env` exists in project root
- Check key is set: `GROQ_API_KEY=sk-xxxx` (no spaces)

### Issue: "Firebase credentials not found"
**Solution:**
- Download from Firebase Console
- Save as `vennela-firebase-key.json`
- Or set path in `.env`: `FIREBASE_CREDENTIALS=/path/to/key.json`

### Issue: "Models downloading takes too long"
**Solution:**
- This is normal on first run (~2-3 minutes)
- Models cache in `~/.cache/huggingface/`
- Subsequent runs will be fast

### Issue: "Port 8000 already in use"
**Solution:**
```bash
# Use different port
uvicorn main:app --port 8001
```

### Issue: "Out of memory" when downloading models
**Solution:**
- Need ~4GB RAM
- Close other applications
- Or wait for models to cache

---

## 📊 Performance Expectations

| Operation | Time |
|-----------|------|
| Health check | <100ms |
| First message (model load) | 1-3 sec |
| Subsequent messages (cached) | 1-3 sec |
| Memory retrieval | <100ms |
| Rate limit (per user) | 100 req/min |

---

## 🔗 Useful Links

- **Groq API**: https://console.groq.com
- **OpenRouter**: https://openrouter.ai
- **Firebase Console**: https://console.firebase.google.com
- **FastAPI Docs**: http://localhost:8000/docs (when running)
- **Full README**: `README.md` (this repo)

---

## 🛠️ Useful Commands

```bash
# Run with debug logging
LOG_LEVEL=DEBUG uvicorn main:app --reload

# Run in background (Linux/Mac)
nohup uvicorn main:app &

# Stop server (Ctrl+C in terminal)

# Install specific versions
pip install -r requirements.txt --no-cache-dir

# Check what's running on port 8000
lsof -i :8000  # Mac/Linux
netstat -ano | findstr :8000  # Windows

# Clear cache
python -c "from embedding_engine import clear_embedding_cache; clear_embedding_cache()"
```

---

## 🎯 What's Included

✅ AI Router (Groq + OpenRouter fallback)  
✅ Smart Memory (short + long term)  
✅ Emotion Detection (HuggingFace)  
✅ Semantic Search (embeddings + caching)  
✅ Firestore Integration  
✅ Rate Limiting  
✅ Input Validation  
✅ Error Handling  
✅ Comprehensive Logging  
✅ Production Ready  

---

## 📞 Need Help?

1. Run `python validate_setup.py` to identify issues
2. Check `.env.example` for configuration
3. Read `README.md` for detailed docs
4. Check server logs for error messages
5. Increase `LOG_LEVEL=DEBUG` in `.env` for verbose output

---

**Happy coding! 🚀**

*Vennela AI v2.0 - Self-learning AI with semantic memory*
