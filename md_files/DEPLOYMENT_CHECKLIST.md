# ✅ Vennela AI - Pre-Deployment Checklist

Use this checklist before deploying to production.

---

## 🔍 Pre-Deployment Verification

### Environment Setup
- [ ] Python 3.8+ installed (`python --version`)
- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] ML models downloaded (run setup script)
- [ ] `.env` file exists in project root
- [ ] `.env` has valid `GROQ_API_KEY`
- [ ] `.env` has valid `OPENROUTER_API_KEY`
- [ ] Firebase credentials file exists
- [ ] Firebase credentials path correct in `.env`

### Code Validation
- [ ] All 7 core modules present:
  - [ ] `main.py`
  - [ ] `ai_router.py`
  - [ ] `smart_memory.py`
  - [ ] `nlp_engine.py`
  - [ ] `embedding_engine.py`
  - [ ] `retrieval.py`
  - [ ] `firebase_db.py`

- [ ] Run `python validate_setup.py` - all checks pass ✅

### Configuration Verification
- [ ] `GROQ_API_KEY` is set (not "your_groq_api_key_here")
- [ ] `OPENROUTER_API_KEY` is set (not "your_openrouter_api_key_here")
- [ ] `VENNELA_PROMPT` is customized (optional)
- [ ] `PORT` is set (default 8000)
- [ ] `LOG_LEVEL` is appropriate (INFO for production, DEBUG for troubleshooting)
- [ ] `RATE_LIMIT_REQUESTS` is reasonable (100 default)
- [ ] `RATE_LIMIT_WINDOW_MINUTES` is set (1 default)

---

## 🧪 Functional Testing

### Health Checks
- [ ] Server starts without errors: `uvicorn main:app --reload`
- [ ] Health endpoint works: `curl http://localhost:8000/health`
- [ ] Response includes firebase status
- [ ] Response includes version

### API Testing
- [ ] Chat endpoint accepts valid requests
- [ ] Chat returns successful response
- [ ] Response includes: reply, provider, memory_summary, latency_ms
- [ ] Memory endpoint returns user profile
- [ ] Memory endpoint returns emotion/sentiment trends

### Error Handling
- [ ] Invalid user_id rejected (400)
- [ ] Empty message rejected (400)
- [ ] Message too long rejected (400)
- [ ] Rate limit exceeded returns 429
- [ ] Server errors return 500 with details

### Edge Cases
- [ ] Handles special characters in message
- [ ] Handles very long messages (5000+ chars)
- [ ] Handles rapid requests (rate limiting)
- [ ] Handles offline Firestore gracefully
- [ ] Handles offline AI providers gracefully

---

## 📊 Performance Testing

### Response Times
- [ ] Health check: <200ms
- [ ] Chat (Groq): 1-5 sec
- [ ] Memory retrieval: <100ms
- [ ] Cached embedding: <10ms

### Load Testing
- [ ] Handles 10 concurrent requests
- [ ] Handles 100 requests per minute (total)
- [ ] Memory usage stable (no leaks)
- [ ] No crashes under load

### Rate Limiting
- [ ] User can send 100 requests per minute
- [ ] 101st request is rejected
- [ ] Different users have separate limits
- [ ] Limit resets after window expires

---

## 🛡️ Security Verification

### Input Validation
- [ ] user_id format enforced (alphanumeric + underscore/hyphen)
- [ ] Message length limits enforced (1-5000 chars)
- [ ] No SQL injection possible (Firestore/Pydantic)
- [ ] Special characters handled safely

### Rate Limiting
- [ ] Per-user rate limiting active
- [ ] Prevents request flooding
- [ ] Returns clear error message when exceeded

### Error Handling
- [ ] No sensitive data in error messages
- [ ] Stack traces only in logs
- [ ] API keys not exposed
- [ ] Firestore paths not exposed

### Logging
- [ ] All errors logged with timestamps
- [ ] No sensitive data in logs
- [ ] Log levels appropriate
- [ ] Logs rotated/managed

---

## 📚 Documentation Verification

- [ ] `README.md` exists and is up-to-date
- [ ] `QUICKSTART.md` is accurate
- [ ] `PRODUCTION_UPGRADE_SUMMARY.md` is complete
- [ ] `.env.example` includes all settings
- [ ] All functions have docstrings
- [ ] API reference is accurate

---

## 🚀 Deployment Configuration

### Local Development
- [ ] Works with `uvicorn main:app --reload`
- [ ] Auto-reload on code changes works

### Production Mode
- [ ] Works with `uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4`
- [ ] Multiple workers don't cause issues
- [ ] Memory sharing between workers works

### Docker
- [ ] Dockerfile created (if using Docker)
- [ ] Docker build succeeds
- [ ] Docker container starts without errors
- [ ] Docker container responds to health check

### Cloud Deployment (if applicable)
- [ ] Environment variables configured
- [ ] Credentials securely stored (not in code)
- [ ] Port configuration correct
- [ ] Domain/URL configured

---

## 🔧 Database Verification

### Firestore
- [ ] Firebase project initialized
- [ ] Service account JSON valid
- [ ] Firestore collections created:
  - [ ] `memory`
  - [ ] `chat_memory`
- [ ] Write permissions work
- [ ] Read permissions work
- [ ] Merge operations work

### Data Integrity
- [ ] Memory saves correctly
- [ ] Memory loads correctly
- [ ] No data corruption on errors
- [ ] Timestamps are server-side

---

## 📈 Monitoring Setup

### Logging
- [ ] Log output captured/stored
- [ ] Error logs reviewed
- [ ] Performance logs available
- [ ] Log rotation configured (if applicable)

### Metrics
- [ ] Response times tracked
- [ ] Error rates tracked
- [ ] Request counts tracked
- [ ] Memory usage tracked

### Alerts (if applicable)
- [ ] Alert on high error rate
- [ ] Alert on slow responses
- [ ] Alert on API provider failures
- [ ] Alert on rate limit abuse

---

## 🧹 Cleanup & Optimization

### Code
- [ ] Remove debug print statements
- [ ] Remove commented-out code
- [ ] Consistent formatting
- [ ] No warnings on import

### Dependencies
- [ ] Only required packages in requirements.txt
- [ ] Version numbers pinned
- [ ] No unused dependencies
- [ ] torch/transformers are heavy but necessary

### Secrets
- [ ] No API keys in code
- [ ] No credentials in git
- [ ] `.gitignore` includes `.env`
- [ ] `.gitignore` includes `vennela-firebase-key.json`

### Performance
- [ ] Embedding cache enabled
- [ ] Model lazy-loading works
- [ ] No unnecessary calls to expensive operations
- [ ] Database queries are efficient

---

## ✅ Final Checklist

### Before Going Live
- [ ] All code checks pass
- [ ] All functional tests pass
- [ ] Performance tests acceptable
- [ ] Security review complete
- [ ] Documentation reviewed
- [ ] Team trained on system
- [ ] Backup plan in place
- [ ] Rollback plan documented

### Day 1 Production
- [ ] Monitor logs for errors
- [ ] Check response times
- [ ] Verify rate limiting works
- [ ] Confirm memory persistence
- [ ] Test with real users (limited)
- [ ] Document any issues
- [ ] Be ready to rollback

### Week 1 Production
- [ ] Monitor for any patterns in errors
- [ ] Check Firebase costs (unexpected spikes)
- [ ] Review AI provider costs
- [ ] Collect user feedback
- [ ] Plan for optimizations

---

## 🎯 Sign-Off

- [ ] Project Lead: _________________ Date: _______
- [ ] Technical Lead: _________________ Date: _______
- [ ] DevOps: _________________ Date: _______

---

## 📞 Escalation Path

If issues arise:

1. **First Response**: Check logs, verify configuration
2. **Investigation**: Run `validate_setup.py`, test API manually
3. **Emergency Rollback**: Redeploy previous version if needed
4. **Root Cause**: Review logs, identify failure point
5. **Fix & Test**: Fix locally, run full test suite
6. **Re-deploy**: Deploy with monitoring

---

## 🚀 Deployment Readiness Score

Score each section 1-5 (5 = fully ready):

| Section | Score | Notes |
|---------|-------|-------|
| Environment Setup | ___ | |
| Code Validation | ___ | |
| Configuration | ___ | |
| Functional Testing | ___ | |
| Performance | ___ | |
| Security | ___ | |
| Documentation | ___ | |
| Database | ___ | |
| Monitoring | ___ | |
| **Total Average** | ___ | Must be 4.5+ |

**Deployment Approved**: ☐ YES ☐ NO

---

**Last Updated**: 2026-05-14  
**Version**: 2.0.0

🚀 Ready for deployment when all items are checked!
