#!/usr/bin/env python3
"""
Render Deployment Quick Setup Guide
Follow these steps to deploy Vennela A.I on Render.com
"""

# ============================================================================
# STEP 1: Get Your API Keys
# ============================================================================

STEP_1 = """
1️⃣ GEMINI API KEY (Required)
   Go to: https://aistudio.google.com/app/apikey
   - Click "Create API key"
   - Copy the key
   - Save it somewhere safe
   
   Result: AIza_xxxxxxxxxxxxxxxxxxx

2️⃣ GROQ API KEY (Optional but Recommended)
   Go to: https://console.groq.com
   - Create account/login
   - Go to API keys
   - Copy your key
   
   Result: gsk_xxxxxxxxxxxxxxxxxxxxx

3️⃣ OPENROUTER API KEY (Optional Fallback)
   Go to: https://openrouter.ai
   - Create account/login
   - Get API key
   - Copy it
   
   Result: sk-or-xxxxxxxxxxxxxxxxxx
"""

# ============================================================================
# STEP 2: Deploy to Render
# ============================================================================

STEP_2 = """
1️⃣ Push Updated Code to Git
   git add .
   git commit -m "Update render.yaml with Vennela A.I config"
   git push origin main

2️⃣ Go to Render Dashboard
   https://dashboard.render.com
   - Login with your account
   - Click on "vennela-ai" service

3️⃣ Add Environment Variables
   Click: Settings → Environment → Add Environment Variable
   
   Add these one by one:
   ┌────────────────────────┐
   │ GEMINI_API_KEY         │
   │ [paste your key here]  │
   └────────────────────────┘
   
   ┌────────────────────────┐
   │ GROQ_API_KEY           │
   │ [paste your key here]  │
   └────────────────────────┘
   
   ┌────────────────────────┐
   │ OPENROUTER_API_KEY     │
   │ [paste your key here]  │
   └────────────────────────┘

4️⃣ Click "Deploy latest"
   - Service will restart
   - All 7 phases will be enabled
   - Check logs for success
"""

# ============================================================================
# STEP 3: Verify Deployment
# ============================================================================

STEP_3 = """
1️⃣ Check Logs
   In Render Dashboard → Logs
   
   Look for:
   ✅ "All environment variables loaded successfully"
   ✅ "Multi-LLM router initialized"
   ✅ "Event bus started"
   ✅ "Memory reflection enabled"
   ✅ "Voice pipeline ready"
   
2️⃣ Test the Service
   curl https://your-vennela-ai.onrender.com/health
   
   Expected response:
   {
     "status": "ok",
     "service": "vennela-ai",
     "phases": {
       "router": "enabled",
       "event_bus": "enabled",
       "memory": "enabled"
     }
   }
"""

# ============================================================================
# CONFIGURATION SUMMARY
# ============================================================================

CONFIG_SUMMARY = """
✅ render.yaml has been updated with:

PHASE A (Multi-LLM Router):
  ✓ GEMINI_API_KEY          (required)
  ✓ GROQ_API_KEY            (fallback)
  ✓ OPENROUTER_API_KEY      (final fallback)
  ✓ LLM_ROUTER_ENABLED      = true
  ✓ COST_TRACKING_ENABLED   = true

PHASE B (Event Bus):
  ✓ EVENT_BUS_ENABLED       = true
  ✓ EVENT_HISTORY_MAX_SIZE  = 1000

PHASE C (Memory Reflection):
  ✓ MEMORY_REFLECTION_ENABLED  = true
  ✓ CONSOLIDATION_INTERVAL    = 5 minutes

PHASE D (Voice Pipeline):
  ✓ VOICE_PIPELINE_ENABLED  = true
  ✓ WAKEWORD_DETECTION      = true

PHASE E (Learning):
  ✓ LEARNING_LOOP_ENABLED   = true

PHASE F (Personality):
  ✓ PERSONALITY_ADAPTATION  = true
  ✓ MOOD_DETECTION          = true

PHASE G (Intent Prediction):
  ✓ INTENT_PREDICTION       = true
"""

# ============================================================================
# QUICK START
# ============================================================================

def main():
    print("=" * 70)
    print("VENNELA A.I - RENDER DEPLOYMENT SETUP")
    print("=" * 70)
    print()
    
    print(STEP_1)
    print()
    print("=" * 70)
    print()
    
    print(STEP_2)
    print()
    print("=" * 70)
    print()
    
    print(STEP_3)
    print()
    print("=" * 70)
    print()
    
    print(CONFIG_SUMMARY)
    print()
    print("=" * 70)
    print("✅ Ready to Deploy!")
    print("=" * 70)

if __name__ == "__main__":
    main()
