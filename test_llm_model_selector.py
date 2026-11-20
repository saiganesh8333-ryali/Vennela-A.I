"""
Test script for LLM Model Selector
Demonstrates intelligent routing based on query complexity
"""

from llm_model_selector import get_model_selector, ModelTier

def test_model_selector():
    """Test the intelligent model selector."""
    selector = get_model_selector()
    
    test_queries = [
        ("Hi, how are you?", "simple_greeting"),
        ("What's the weather?", "simple_query"),
        ("Explain quantum mechanics in detail", "complex_reasoning"),
        ("How do I solve this differential equation: d²x/dt² + 2x = 0", "deep_math"),
        ("Compare machine learning vs deep learning", "analytical"),
        ("I need help with my physics homework on thermodynamics", "medium_academic"),
    ]
    
    print("🔥 LLM Model Selector - Demo\n")
    print("=" * 80)
    
    for query, description in test_queries:
        model, metadata = selector.select_model(
            query,
            conversation_length=0
        )
        
        print(f"\n📝 Query ({description})")
        print(f"   {query}")
        print(f"\n🧠 Selected: {model.value.upper()}")
        print(f"   Complexity: {metadata['complexity']:.2f}")
        print(f"   Cost Est: ${metadata['cost_estimate']:.4f}")
        print(f"   Reason: {list(metadata['scores'].values())[0]['reason']}")
        print(f"   Scores: {metadata['scores']}")
        print("-" * 80)
    
    # Test voice mode
    print(f"\n🎤 Voice Query Test")
    model, metadata = selector.select_model(
        "What's the weather today?",
        is_voice=True
    )
    print(f"   Selected: {model.value.upper()}")
    print(f"   Reason: {metadata['reason']}")
    
    # Simulate recording latency and checking health
    print(f"\n📊 Health Tracking Demo")
    selector.record_usage(ModelTier.LITE, 250, success=True)
    selector.record_usage(ModelTier.STANDARD, 900, success=True)
    print(f"   LITE health: {selector.model_health[ModelTier.LITE]:.2f}")
    print(f"   STANDARD health: {selector.model_health[ModelTier.STANDARD]:.2f}")

if __name__ == "__main__":
    test_model_selector()
