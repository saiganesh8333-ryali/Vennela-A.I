# 🔥 MINIMAL TEST ENDPOINT — DEBUG RESPONSE HIJACKING

## ✅ WHAT WAS ADDED?

New minimal endpoint: `/chat-minimal`

This endpoint:
- Takes user message ONLY
- Sends to Groq with NEW system prompt
- Returns raw response (NO post-processing)
- NO memory, NO intent, NO filtering

---

## 🚀 HOW TO USE

**Test URL:**
```
https://your-app.onrender.com/docs
POST /chat-minimal
```

**Request:**
```json
{
  "user_id": "test_minimal",
  "message": "what is programming"
}
```

**Expected Response:**
```json
{
  "reply": "Programming is the process of writing instructions...",
  "provider": "Groq",
  "test": "minimal"
}
```

---

## 🔍 WHAT THIS TELLS US

### If `/chat-minimal` works ✅
```
reply: "Natural answer about programming..."
```
→ Groq + new prompt are FINE
→ Issue is in the complex `/chat` logic
→ Something in memory/intent/filtering is hijacking response

### If `/chat-minimal` still broken ❌
```
reply: "I'm ready to engage and provide information..."
```
→ Groq is NOT using new prompt
→ Either:
   - Environment variable on Render is still old
   - System prompt not being passed correctly
   - Groq is doing something weird

---

## 📋 NEXT STEPS

1. Deploy this change
2. Test `/chat-minimal` in Swagger
3. Check response

### If Minimal Works:
- Focus on `/chat` endpoint complex logic
- Remove memory/intent one by one
- Find what's replacing response

### If Minimal Broken:
- Check Render environment variables
- Verify VENNELA_PROMPT in Render config
- Check Groq API key

---

## 🎯 THIS IS SMART DEBUGGING

Instead of guessing where response is hijacked, we:
1. Create minimal path (user → Groq → response)
2. Test it
3. If works: problem is in complex logic
4. If broken: problem is in Groq/prompt setup

---

## 💙 DEPLOYMENT

```bash
git add main.py
git commit -m "Add minimal test endpoint for debugging"
git push
```

Then deploy to Render + test!

