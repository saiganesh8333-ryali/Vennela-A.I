# 🧠 VENNELA AI v2.0 - Self-Learning AI Assistant

**Production-Grade AI Assistant with Semantic Memory, Emotion Detection & Intelligent Retrieval**

## ✨ Features

### 🤖 Core AI
- **Dual AI Provider Architecture**: Groq (primary) + OpenRouter (fallback) for reliability
- **Error Recovery**: Automatic fallback when providers fail
- **Performance Tracking**: Built-in latency metrics

### 🧠 Smart Memory System
- **Short-term Memory**: Last 30 messages for context
- **Long-term Memory**: Important user facts (goals, preferences, name)
- **Semantic Embeddings**: Vector-based memory retrieval using MiniLM
- **Emotional Awareness**: Emotion & sentiment tracking per conversation

### 🎯 User Understanding
- **Emotion Detection**: HuggingFace-based emotion classification (joy, sadness, anger, fear, surprise, neutral)
- **Sentiment Analysis**: Positive/Negative/Neutral sentiment tracking
- **Profile Learning**: Auto-extracts user name and preferences
- **Importance Scoring**: Intelligent filtering of what to remember

### 🔍 Retrieval System
- **Semantic Search**: Cosine similarity-based memory retrieval
- **Smart Thresholding**: Only retrieves relevant memories (>0.25 similarity)
- **Caching**: In-memory embedding cache for performance

### ☁️ Storage
- **Firestore Integration**: Persistent memory across sessions
- **Automatic Normalization**: Handles legacy data formats
- **Efficient Updates**: Merge-based writes for concurrency

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                   FastAPI Server                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌────────────────────────────────────────────┐    │
│  │           /chat Endpoint                   │    │
│  │  (Rate Limited + Input Validated)          │    │
│  └────────────────────────────────────────────┘    │
│                      │                             │
│        ┌─────────────┼─────────────┐               │
│        ▼             ▼             ▼               │
│   ┌─────────┐  ┌──────────┐  ┌──────────┐         │
│   │ Memory  │  │Retrieval │  │    NLP   │         │
│   │ Engine  │  │  Engine  │  │  Engine  │         │
│   └────┬────┘  └─────┬────┘  └────┬─────┘         │
│        │             │             │               │
│        └─────────────┼─────────────┘               │
│                      ▼                             │
│          ┌──────────────────────┐                 │
│          │  Embedding Engine    │                 │
│          │ (Cached + Fallback)  │                 │
│          └──────────────────────┘                 │
│                      │                             │
│        ┌─────────────┼─────────────┐               │
│        ▼             ▼             ▼               │
│   ┌─────────┐  ┌──────────┐  ┌──────────┐         │
│   │ Groq    │  │OpenRouter│  │Firestore │         │
│   │   AI    │  │   AI     │  │Database  │         │
│   └─────────┘  └──────────┘  └──────────┘         │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
vennela-ai/
├── main.py                      # FastAPI app + endpoints
├── ai_router.py                 # AI provider routing + failover
├── smart_memory.py              # Memory management + learning
├── nlp_engine.py                # Emotion/sentiment detection
├── embedding_engine.py          # Semantic embeddings + caching
├── retrieval.py                 # Memory retrieval logic
├── firebase_db.py               # Firestore client initialization
├── requirements.txt             # Python dependencies
├── .env.example                 # Configuration template
├── vennela-firebase-key.json    # Firebase credentials (create this)
└── README.md                    # This file
```

---

## 🚀 Setup & Installation

### 1. Prerequisites
- Python 3.8+
- Groq API key (free tier available)
- OpenRouter API key (fallback provider)
- Firebase Firestore database
- ~4GB RAM (for transformers models)

### 2. Installation

```bash
# Clone repository
cd vennela-ai

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download models (one-time, ~800MB)
python -c "from transformers import pipeline; pipeline('text-classification', model='j-hartmann/emotion-english-distilroberta-base'); pipeline('sentiment-analysis')"
```

### 3. Configuration

```bash
# Copy example config
cp .env.example .env

# Edit .env with your keys:
# - GROQ_API_KEY (from https://console.groq.com)
# - OPENROUTER_API_KEY (from https://openrouter.ai)
# - FIREBASE_CREDENTIALS path

# Place Firebase credentials
cp /path/to/serviceAccount.json ./vennela-firebase-key.json
```

### 4. Run Server

```bash
# Development (with auto-reload)
uvicorn main:app --reload

# Production (recommended)
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

Server will be available at `http://localhost:8000`

---

## 📡 API Reference

### Health Check
```bash
GET /health
```
**Response:**
```json
{
  "status": "ok",
  "firebase": "connected",
  "version": "2.0.0"
}
```

### Chat (Main Endpoint)
```bash
POST /chat
Content-Type: application/json

{
  "user_id": "user123",
  "message": "Hello, I want to build an AI project"
}
```

**Response:**
```json
{
  "reply": "That sounds exciting! I'd love to help you build an AI project...",
  "provider": "Groq",
  "relevant_memory": "User wants to build an AI project",
  "memory_summary": "User name: John | Main emotional trend: joy | ...",
  "latency_ms": 1234
}
```

**Error Responses:**
- `400`: Invalid input (empty message, invalid user_id)
- `429`: Rate limit exceeded (100 requests per minute per user)
- `500`: Server error

### Get User Memory
```bash
GET /memory/{user_id}
```

**Response:**
```json
{
  "profile": {
    "name": "John",
    "preferred_name": "Johnny"
  },
  "summary": "User name: John | Main emotional trend: joy | ...",
  "emotions": {"joy": 5, "sadness": 1},
  "sentiments": {"POSITIVE": 8, "NEUTRAL": 2},
  "long_term_count": 15,
  "embeddings_count": 23
}
```

---

## 🧪 Testing

### Manual Testing
```bash
# Test health
curl http://localhost:8000/health

# Test chat
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"user1","message":"Hi, my name is Alice"}'

# Test memory retrieval
curl http://localhost:8000/memory/user1
```

### Rate Limiting Test
```bash
# Send 101 requests (should fail on 101st)
for i in {1..101}; do
  curl -X POST http://localhost:8000/chat \
    -H "Content-Type: application/json" \
    -d '{"user_id":"ratelimit_user","message":"test"}'
done
```

---

## ⚙️ Configuration Options

All options configurable via `.env`:

```env
# API Provider
GROQ_API_KEY=<your-key>              # Primary AI provider
OPENROUTER_API_KEY=<your-key>        # Fallback provider

# Firebase
FIREBASE_CREDENTIALS=vennela-firebase-key.json

# Memory Management
RECENT_CHAT_LIMIT=20                 # Recent messages to include
MAX_MESSAGE_LENGTH=5000              # Max message size

# Rate Limiting
RATE_LIMIT_REQUESTS=100              # Max requests per window
RATE_LIMIT_WINDOW_MINUTES=1          # Window duration

# Server
PORT=8000
LOG_LEVEL=INFO
```

---

## 🔍 How It Works

### 1. **Message Reception**
- User sends message via `/chat` endpoint
- Input is validated (length, format, user_id)
- Rate limit is checked (100 req/min per user)

### 2. **Memory Retrieval**
- User's memory is loaded from Firestore
- Semantic search finds relevant past context
- Last 20 chat messages are fetched

### 3. **Emotion/Sentiment Analysis**
- HuggingFace emotion model analyzes sentiment
- Trends tracked for user profile

### 4. **AI Response Generation**
- Messages are sent to Groq (primary)
- If Groq fails, fallback to OpenRouter
- Response is streamed with latency tracking

### 5. **Memory Update**
- Message importance is scored (keyword-based)
- Important messages go to long-term memory
- Embeddings generated for semantic search
- User profile updated (name extraction)
- All data persisted to Firestore

### 6. **Response Return**
- AI reply + metadata sent to client
- Includes provider info, relevant memory, latency

---

## 📊 Performance Metrics

### Expected Performance
- **Chat Response**: 1-3 seconds (Groq), 2-5 seconds (OpenRouter)
- **Memory Retrieval**: <100ms (cached)
- **Embedding Generation**: 50-200ms (first run), <10ms (cached)
- **Rate Limit**: 100 requests per minute per user
- **Storage**: ~1KB per memory item, ~100KB per user

### Optimization Tips
- Increase `RATE_LIMIT_REQUESTS` for high-traffic apps
- Reduce `RECENT_CHAT_LIMIT` if response time is slow
- Use `MAX_MESSAGE_LENGTH` to prevent abuse
- Enable production mode with multiple workers

---

## 🛡️ Security Features

✅ **Input Validation**
- User ID format validation
- Message length limits
- Alphanumeric user_id enforcement

✅ **Rate Limiting**
- Per-user request limiting
- Prevents abuse and cost overruns
- Configurable windows

✅ **Error Handling**
- Graceful degradation on failures
- No sensitive data in error messages
- Comprehensive logging

✅ **Database Security**
- Firebase rules configured (separate)
- Server-side timestamp validation
- Merge-based writes for safety

---

## 🐛 Troubleshooting

### "GROQ_API_KEY not found"
- Ensure `.env` file exists in project root
- Check key is correctly set: `GROQ_API_KEY=sk-xxxx`
- Verify no spaces around `=`

### "Firebase credentials not found"
- Download from Firebase Console → Project Settings → Service Accounts
- Save as `vennela-firebase-key.json` in project root
- Or set `FIREBASE_CREDENTIALS=path/to/key.json` in `.env`

### "Rate limit exceeded"
- Waiting 1 minute or increase `RATE_LIMIT_REQUESTS` in `.env`
- Different `user_id` values have separate limits

### "Both AI providers failed"
- Check API keys in `.env`
- Verify internet connection
- Check API provider status page
- See logs: `tail -f ~/.copilot/session-state/*/debug-logs/*`

### Slow Response Times
- May be downloading transformer models (first run only)
- Check network speed to Groq/OpenRouter
- Reduce `RECENT_CHAT_LIMIT` or `MAX_EMBEDDINGS`
- Run with multiple workers: `--workers 4`

---

## 📚 Memory System Details

### Importance Scoring
Messages scored 0-10 based on keywords:
- `my name` / `call me`: +10
- `i want` / `i need`: +4
- `project` / `goal`: +4
- `learn`: +3
- `remember`: +5
- Long messages (>50 chars): +1

Score > 5 → Long-term memory
Score ≤ 5 → Short-term memory

### Emotion Detection
Detects: `joy`, `sadness`, `anger`, `fear`, `surprise`, `neutral`

Uses HuggingFace model: `j-hartmann/emotion-english-distilroberta-base`
Fallback: Keyword matching

### Sentiment Analysis
Classifies: `POSITIVE`, `NEGATIVE`, `NEUTRAL`

Uses HuggingFace model: default sentiment-analysis
Fallback: Keyword matching

### Embeddings
- Model: `all-MiniLM-L6-v2` (384-dim vectors)
- Cached in-memory for performance
- Similarity threshold: 0.25 (configurable)
- Stored with: text, vector, importance, emotion, sentiment

---

## 🚀 Deployment

### Docker (Recommended)
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t vennela-ai .
docker run -p 8000:8000 -e GROQ_API_KEY=xxx vennela-ai
```

### AWS Lambda
- Use Mangum for ASGI → Lambda adapter
- Upload models to S3 or Lambda layers
- Set timeouts to 30s+

### Heroku
```bash
heroku create vennela-ai
git push heroku main
heroku config:set GROQ_API_KEY=xxx
```

### Google Cloud Run
```bash
gcloud run deploy vennela-ai \
  --source . \
  --platform managed \
  --set-env-vars GROQ_API_KEY=xxx
```

---

## 📈 Future Enhancements

🔧 Planned Features:
- [ ] Vector DB upgrade (Pinecone/Weaviate for >1M embeddings)
- [ ] Async Firestore operations
- [ ] WebSocket support for real-time memory
- [ ] Voice input/output integration
- [ ] Multi-language support
- [ ] Personality evolution system
- [ ] Offline mode with local embedding
- [ ] Advanced memory search (temporal, category-based)
- [ ] Personality traits inference
- [ ] Conversation style learning

---

## 📝 License

MIT License - Feel free to use, modify, and distribute

---

## 🤝 Contributing

Found a bug? Have a feature idea?

1. Test thoroughly
2. Create clear, minimal reproduction
3. Document expected vs actual behavior
4. Submit with logs/traces

---

## 💡 Need Help?

- Check `README.md` (this file)
- Review logs in server output
- Test endpoints with `curl` or Postman
- Check `.env` configuration
- Verify API keys are active

---

**Built with ❤️ using FastAPI, HuggingFace, and Firebase**

*Version: 2.0.0 (Production-Ready)*
