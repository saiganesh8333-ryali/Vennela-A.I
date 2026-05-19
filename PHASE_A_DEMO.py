"""Phase A Implementation Demo & Integration Guide - Multi-LLM Router."""

import logging
from llm_router_gemini import get_multi_llm_router
from llm_intent_classifier import get_classifier
from llm_provider_manager import get_provider_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def demo_intent_classification():
    """Demo: Classify different query types."""
    print("\n" + "="*60)
    print("DEMO 1: Intent Classification")
    print("="*60)
    
    classifier = get_classifier()
    
    test_queries = [
        ("Hello, how are you?", "Simple greeting"),
        ("Explain quantum computing step by step", "Complex reasoning needed"),
        ("Call my mother", "Real-time voice action"),
        ("What's the weather?", "Lightweight query"),
        ("Write a poem about love", "Creative task"),
        ("Calculate 1234 * 5678", "Math calculation"),
    ]
    
    for query, description in test_queries:
        result = classifier.classify_query(query, conversation_length=0)
        print(f"\n📝 {description}")
        print(f"Query: {query}")
        print(f"Intent: {result['intent']}")
        print(f"Provider: {result['recommended_provider']}")
        print(f"Confidence: {result['confidence']:.2f}")
        print(f"Alternatives: {result['alternatives']}")


def demo_provider_manager():
    """Demo: Check provider availability and health."""
    print("\n" + "="*60)
    print("DEMO 2: Provider Manager & Health")
    print("="*60)
    
    manager = get_provider_manager()
    
    print(f"\n✓ Registered Providers: {len(manager.list_providers())}")
    for provider in manager.list_providers():
        print(f"  - {provider}")
    
    print(f"\n✓ Available Providers: {len(manager.get_available_providers())}")
    for provider in manager.get_available_providers():
        print(f"  - {provider}")
    
    health = manager.get_provider_health_summary()
    print(f"\n✓ Health Summary:")
    print(f"  Providers Online: {health['providers_online']}/{health['providers_total']}")
    for provider, status in health['health_status'].items():
        score = health['availability_scores'].get(provider, 0)
        print(f"  - {provider}: {status} (score: {score:.2f})")


def demo_llm_router():
    """Demo: Route queries to optimal LLM."""
    print("\n" + "="*60)
    print("DEMO 3: Multi-LLM Router")
    print("="*60)
    
    router = get_multi_llm_router()
    
    # Example 1: Simple query
    print("\n🔀 Example 1: Simple Query")
    result1 = router.route_and_call(
        query="What is Python?",
        conversation_length=0
    )
    print(f"Query: What is Python?")
    print(f"Provider: {result1.get('provider')}")
    print(f"Success: {result1.get('success')}")
    if result1.get('success'):
        print(f"Response: {result1.get('response', '')[:100]}...")
        print(f"Tokens: {result1.get('tokens_used')}")
        print(f"Cost: ${result1.get('cost', 0):.6f}")
        print(f"Latency: {result1.get('latency_ms')}ms")
    
    # Example 2: Complex reasoning
    print("\n🔀 Example 2: Complex Reasoning")
    result2 = router.route_and_call(
        query="Explain the implications of quantum entanglement "
              "for future computing systems and cryptography.",
        conversation_length=0
    )
    print(f"Query: [complex reasoning question]")
    print(f"Provider: {result2.get('provider')}")
    print(f"Success: {result2.get('success')}")
    if result2.get('success'):
        print(f"Tokens: {result2.get('tokens_used')}")
        print(f"Latency: {result2.get('latency_ms')}ms")
    
    # Example 3: Conversation context
    print("\n🔀 Example 3: With Conversation History")
    messages = [
        {"role": "user", "content": "What is machine learning?"},
        {"role": "assistant", "content": "ML is a subset of AI..."},
        {"role": "user", "content": "Can you give examples?"},
    ]
    result3 = router.route_and_call(
        query="How is it different from deep learning?",
        messages=messages,
        conversation_length=3
    )
    print(f"Query: How is it different from deep learning?")
    print(f"Provider: {result3.get('provider')}")
    print(f"Success: {result3.get('success')}")


def demo_cost_tracking():
    """Demo: Cost tracking and projections."""
    print("\n" + "="*60)
    print("DEMO 4: Cost Tracking")
    print("="*60)
    
    from llm_cost_tracker import get_cost_tracker
    
    tracker = get_cost_tracker()
    
    # Record some sample calls
    print("\n📊 Recording Sample API Calls...")
    
    tracker.record_call(
        provider="gemini",
        model="gemini-3.5-flash",
        input_tokens=50,
        output_tokens=150,
        latency_ms=250,
        success=True,
        query_preview="What is Python?"
    )
    
    tracker.record_call(
        provider="groq",
        model="llama-3.3-70b-versatile",
        input_tokens=100,
        output_tokens=300,
        latency_ms=180,
        success=True,
        query_preview="Explain quantum computing..."
    )
    
    # Get summaries
    print("\n📈 Session Summary:")
    summary = tracker.get_session_summary()
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")
    
    print("\n📊 Provider Breakdown:")
    provider_summary = tracker.get_provider_summary()
    for provider, stats in provider_summary.items():
        print(f"  {provider}:")
        for stat, value in stats.items():
            if isinstance(value, float):
                print(f"    {stat}: {value:.4f}")
            else:
                print(f"    {stat}: {value}")
    
    print("\n⚡ Model Breakdown:")
    model_summary = tracker.get_model_summary()
    for model, stats in model_summary.items():
        print(f"  {model}:")
        print(f"    calls: {stats['calls']}")
        print(f"    cost: ${stats['cost']:.6f}")
        print(f"    avg_latency: {stats['avg_latency_ms']:.0f}ms")
        print(f"    success_rate: {stats['success_rate']:.1%}")
    
    print("\n💰 Cost Projection:")
    projection = tracker.get_cost_projection()
    print(f"  Daily: ${projection['daily_projection']:.4f}")
    print(f"  Monthly: ${projection['monthly_projection']:.2f}")
    print(f"  Confidence: {projection['confidence']}")
    
    print("\n⭐ Efficiency Score:")
    efficiency = tracker.get_efficiency_score()
    print(f"  Score: {efficiency['score']:.1f}/100")
    print(f"  Rating: {efficiency['rating']}")
    print(f"  Success Rate: {efficiency['success_rate']:.1%}")
    print(f"  Tokens/Dollar: {efficiency['tokens_per_dollar']:.0f}")
    print(f"  Avg Latency: {efficiency['avg_latency_ms']:.0f}ms")


def demo_routing_stats():
    """Demo: Routing statistics."""
    print("\n" + "="*60)
    print("DEMO 5: Routing Statistics")
    print("="*60)
    
    router = get_multi_llm_router()
    
    stats = router.get_routing_stats()
    print(f"\n📊 Total Routes: {stats.get('total_routes', 0)}")
    
    if stats.get('providers'):
        print("\n🔀 Provider Stats:")
        for provider, pstats in stats['providers'].items():
            success_rate = (
                pstats['successful'] / pstats['count']
                if pstats['count'] > 0 else 0
            )
            print(f"\n  {provider}:")
            print(f"    Routes: {pstats['count']}")
            print(f"    Successful: {pstats['successful']}")
            print(f"    Success Rate: {success_rate:.1%}")
            print(f"    Avg Latency: {pstats['avg_latency']:.0f}ms")


# ============================================================================
# INTEGRATION GUIDE
# ============================================================================

INTEGRATION_GUIDE = """
╔════════════════════════════════════════════════════════════════════════════╗
║                         PHASE A INTEGRATION GUIDE                         ║
║                      Multi-LLM Router for Vennela AI                       ║
╚════════════════════════════════════════════════════════════════════════════╝

QUICK START (5 minutes)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Install Dependencies:
   pip install google-generativeai

2. Set API Keys in .env:
   GEMINI_API_KEY=your_key_here
   GROQ_API_KEY=your_key_here (optional, fallback)
   OPENROUTER_API_KEY=your_key_here (optional, fallback)

3. Basic Usage:
   
   from llm_router_gemini import get_multi_llm_router
   
   router = get_multi_llm_router()
   result = router.route_and_call(
       query="Hello, how are you?",
       messages=[],  # Optional chat history
       conversation_length=0
   )
   
   if result["success"]:
       print(result["response"])
       print(f"Cost: ${result['cost']:.6f}")


INTEGRATION INTO EXISTING CODE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Before (using existing ai_router.py):
   from ai.ai_router import get_ai_response
   response_dict = get_ai_response(messages)
   ai_reply = response_dict["response"]

After (using new Multi-LLM Router):
   from llm_router_gemini import get_multi_llm_router
   from llm_cost_tracker import get_cost_tracker
   
   router = get_multi_llm_router()
   tracker = get_cost_tracker()
   
   result = router.route_and_call(
       query=user_message,
       messages=conversation_history,
       conversation_length=len(conversation_history)
   )
   
   if result["success"]:
       ai_reply = result["response"]
       
       # Track costs
       tracker.record_call(
           provider=result["provider"],
           model=result["model"],
           input_tokens=len(user_message.split()),
           output_tokens=len(result["response"].split()),
           latency_ms=result["latency_ms"],
           success=True,
           query_preview=user_message[:100]
       )


KEY COMPONENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. llm_intent_classifier.py
   ├─ Classifies queries: reasoning, realtime, lightweight, creative, math
   ├─ Determines optimal provider
   └─ Estimates token usage

2. llm_provider_manager.py
   ├─ Unified provider interface
   ├─ Health tracking
   ├─ Availability checking
   └─ Provider statistics

3. llm_router_gemini.py
   ├─ Main router orchestrator
   ├─ Gemini API integration
   ├─ Groq fallback
   ├─ OpenRouter fallback
   ├─ Intelligent retry logic
   └─ Routing decision tracking

4. llm_cost_tracker.py
   ├─ Records every API call
   ├─ Calculates costs
   ├─ Projects future costs
   ├─ Generates efficiency reports
   └─ Tracks expensive & slow queries


ROUTING DECISION TREE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Query Analysis
    ↓
Intent Classification
    ├─ Reasoning? → gemini-2.5-pro-reasoning
    ├─ Voice/Real-time? → gemini-live
    ├─ Simple/Lightweight? → gemini-3.5-flash
    ├─ Creative? → gemini-2.0-flash
    ├─ Math? → gemini-2.0-flash
    └─ Default? → gemini-2.0-flash or groq (fastest available)
    ↓
Provider Health Check
    ├─ Primary available? → Use it
    └─ Primary down? → Try alternatives
    ↓
API Call
    ├─ Success? → Return response + metadata
    ├─ Failure? → Try fallback provider
    └─ All failed? → Return error (graceful degradation)


MONITORING & OBSERVABILITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Check Provider Health:
   manager = get_provider_manager()
   health = manager.get_provider_health_summary()
   print(f"Providers online: {health['providers_online']}/{health['providers_total']}")

Get Routing Statistics:
   router = get_multi_llm_router()
   stats = router.get_routing_stats()
   print(f"Total routes: {stats['total_routes']}")
   for provider, pstats in stats['providers'].items():
       print(f"{provider}: {pstats['count']} calls, "
             f"{pstats['avg_latency']:.0f}ms avg latency")

Get Cost Information:
   tracker = get_cost_tracker()
   summary = tracker.get_session_summary()
   print(f"Total cost: ${summary['total_cost']:.4f}")
   print(f"Total tokens: {summary['total_tokens']}")
   
   projection = tracker.get_cost_projection()
   print(f"Daily projection: ${projection['daily_projection']:.2f}")


ADVANCED FEATURES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Force Specific Provider:
   result = router.route_and_call(
       query="...",
       force_provider="groq"  # Force Groq, bypass routing
   )

2. Get Efficiency Score:
   tracker = get_cost_tracker()
   efficiency = tracker.get_efficiency_score()
   # Returns: score (0-100), rating (excellent/good/fair/poor),
   #          success_rate, tokens_per_dollar, avg_latency_ms

3. Find Expensive Queries:
   expensive = tracker.get_expensive_queries(limit=10)
   for q in expensive:
       print(f"{q['provider']}: ${q['cost']:.6f}")

4. Find Slow Queries:
   slow = tracker.get_slow_queries(limit=10)
   for q in slow:
       print(f"{q['provider']}: {q['latency_ms']}ms")

5. Export Records:
   records = tracker.export_records(limit=100)
   # Returns list of dicts with all call details


ERROR HANDLING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

result = router.route_and_call(query="...")

if result["success"]:
    response = result["response"]
else:
    error = result["error"]
    provider = result["provider"]
    print(f"Failed on {provider}: {error}")
    # Fallback to stored responses or retry


COST MANAGEMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Best Practices:
1. Use Flash Lite for simple queries (cheapest + fastest)
2. Use Reasoning model only when needed (complex logic)
3. Monitor cost projections regularly
4. Set up alerts for unusual costs
5. Use caching for repeated queries (implement in next phase)
6. Batch similar queries to Groq (cheaper for large batches)


NEXT PHASES (Coming Soon)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Phase B: Event Bus Architecture
   - Decouple modules with pub/sub
   - Enable async processing
   - Better observability

Phase C: Memory Reflection Cycle
   - Dream cycle for consolidation
   - Pattern extraction
   - Behavioral predictions

Phase D: Voice Pipeline
   - STT/TTS integration
   - Gemini Live streaming
   - Real-time conversation

Phase E: Wakeword Detection
   - OpenWakeWord integration
   - Custom training
   - Offline detection


═════════════════════════════════════════════════════════════════════════════

Ready to evolve Vennela with intelligent LLM routing! 🚀

Questions? Check individual module docstrings for detailed documentation.
"""


def main():
    """Run all demos."""
    print(INTEGRATION_GUIDE)
    
    try:
        demo_intent_classification()
    except Exception as e:
        print(f"\n❌ Intent Classification Demo Error: {e}")
    
    try:
        demo_provider_manager()
    except Exception as e:
        print(f"\n❌ Provider Manager Demo Error: {e}")
    
    try:
        demo_cost_tracking()
    except Exception as e:
        print(f"\n❌ Cost Tracking Demo Error: {e}")
    
    try:
        demo_routing_stats()
    except Exception as e:
        print(f"\n❌ Routing Stats Demo Error: {e}")
    
    # Skip LLM router demo as it needs real API keys
    print("\n⏭️  Skipping Multi-LLM Router demo (requires valid API keys)")
    
    print("\n" + "="*60)
    print("✅ Phase A (Multi-LLM Router) Implementation Complete!")
    print("="*60)
    print("\nNext: Integrate into adaptive_ai_main.py orchestrator")


if __name__ == "__main__":
    main()
