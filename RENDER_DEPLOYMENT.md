# 🚀 Vennela AI - Deployment Guide for Render

## Quick Start (Local Development)

### 1. **Setup Local Environment**

```bash
# Clone/extract the project
cd "d:\Vennela A.I"

# Create virtual environment (optional but recommended)
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. **Configure Environment**

```bash
# Copy example env file
copy .env.example .env

# Edit .env and add your keys:
# - GROQ_API_KEY (from https://console.groq.com)
# - OPENROUTER_API_KEY (from https://openrouter.ai)
```

### 3. **Add Firebase Credentials**

- Download your Firebase service account JSON from: Firebase Console → Project Settings → Service Account → Generate Key
- Save it as `vennela-firebase-key.json` in the project root
- ⚠️ **NEVER commit this file** — it's in `.gitignore`

### 4. **Run Locally**

```bash
python main.py
```

Server runs on `http://localhost:8000`

### 5. **Test the API**

```bash
# Health check
curl http://localhost:8000/health

# Send a message
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "message": "Hello Vennela!"
  }'
```

---

## 🌐 Deploy to Render

### Prerequisites
- GitHub account (code already pushed)
- Render account (https://render.com)
- Firebase service account key

### Step 1: Create `.env.example` (Already Done ✅)

This documents required environment variables without exposing secrets.

### Step 2: Push to GitHub

```bash
git add .gitignore requirements.txt render.yaml .env.example firebase_db.py main.py
git commit -m "Prepare for Render deployment with improved Firebase handling"
git push origin main
```

### Step 3: Deploy on Render

1. Go to https://dashboard.render.com
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Fill in deployment settings:

   ```
   Name: vennela-ai
   Environment: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn -w 4 -b 0.0.0.0:$PORT main:app
   ```

5. Add Environment Variables (**click "Advanced"**):

   | Key | Value | Type |
   |-----|-------|------|
   | `GROQ_API_KEY` | Your key | Secret |
   | `OPENROUTER_API_KEY` | Your key | Secret |
   | `FIREBASE_CREDENTIALS` | (see below) | Secret |
   | `VENNELA_PROMPT` | Your prompt | Env |
   | `PYTHON_VERSION` | 3.11 | Env |

6. **For Firebase Credentials on Render:**
   - Open your `vennela-firebase-key.json` file locally
   - Copy the entire JSON content
   - Paste into `FIREBASE_CREDENTIALS` secret variable

7. Click **"Create Web Service"**

### Step 4: Verify Deployment

Once deployed, test your endpoints:

```bash
# Replace YOUR_RENDER_URL with your actual Render URL
curl https://YOUR_RENDER_URL/health

curl -X POST https://YOUR_RENDER_URL/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "render_test",
    "message": "Hello from Render!"
  }'
```

---

## ⚠️ Troubleshooting

### "Failed to load chat context" Error

**Cause:** Firebase not connecting

**Solution:**
1. Verify `FIREBASE_CREDENTIALS` is set correctly on Render
2. Check your Firebase project has Firestore enabled
3. Verify service account has Firestore permissions

### "No response from AI provider"

**Cause:** Missing API keys

**Solution:**
1. Ensure `GROQ_API_KEY` or `OPENROUTER_API_KEY` is set
2. Keys should be marked as "Secret" in Render

### Build fails with dependency errors

**Solution:**
1. Update `requirements.txt`: `pip freeze > requirements.txt`
2. Commit and push
3. Redeploy on Render

---

## 📊 Project Structure

```
vennela-ai/
├── main.py                      # FastAPI app & chat endpoint
├── firebase_db.py               # Firebase initialization
├── smart_memory.py              # Memory & embedding engine
├── ai_router.py                 # AI provider routing (Groq, etc.)
├── retrieval.py                 # Semantic memory retrieval
├── nlp_engine.py                # Emotion & sentiment detection
├── embedding_engine.py          # Vector embeddings
├── requirements.txt             # Python dependencies
├── render.yaml                  # Render config (optional)
├── Procfile                     # Alternative server config
├── .gitignore                   # Git exclusions (CRITICAL!)
├── .env.example                 # Environment template
└── vennela-firebase-key.json   # Firebase credentials (NOT in git!)
```

---

## 🔐 Security Checklist

- [ ] Firebase key file is in `.gitignore`
- [ ] API keys are marked as "Secret" in Render
- [ ] Never commit `.env` files
- [ ] Only `vennela-firebase-key.json` is loaded from env var on Render
- [ ] Firestore rules restrict public access
- [ ] Rate limiting enabled (default: 100 req/min per user)

---

## 📈 Performance Tips

1. **Reduce chat history:** Lower `RECENT_CHAT_LIMIT` to speed up queries
2. **Use Render paid tier:** Free tier restarts after 15 mins of inactivity
3. **Cache embeddings:** Memory embeddings are auto-cached
4. **Monitor logs:** Use Render's built-in logs to find bottlenecks

---

## 🆘 Getting Help

- Check Render logs: Dashboard → Your Service → Logs
- Check local logs: Run `python main.py` and watch console output
- Verify Firebase: Use Firebase Console to check collections
- Test locally first before deploying

