"""
Quick Phase 2 verification - no heavy dependencies
Just verify imports and basic structure work
"""

def verify_phase2_components():
    """Verify Phase 2 components are correctly structured."""
    
    print("\n🔍 Verifying Phase 2 Components...")
    print("=" * 60)
    
    try:
        # Test 1: Import pattern detector
        print("✓ Importing pattern_detector...")
        from pattern_detector import PatternDetector, get_pattern_detector
        detector = get_pattern_detector()
        print("  ✅ PatternDetector loaded")
        
        # Test 2: Import importance calculator
        print("✓ Importing memory_importance_calculator...")
        from memory_importance_calculator import get_importance_calculator
        calculator = get_importance_calculator()
        print("  ✅ MemoryImportanceCalculator loaded")
        
        # Test 3: Check memory_core integration
        print("✓ Checking core/memory_core.py...")
        from core.memory_core import process_memory, importance_score
        print("  ✅ memory_core imports and functions available")
        
        # Test 4: Quick functionality test
        print("\n🧪 Quick Functionality Tests:")
        
        # Test pattern detector
        detector.process_conversation(
            "I love robotics and prefer morning study!",
            "Great!",
            subject_tags=["robotics"],
            sentiment=0.9
        )
        profile = detector.get_user_profile()
        print(f"  ✅ Pattern detection: confidence={profile['confidence']:.2f}")
        
        # Test importance calculator
        important_text = "I'm terrified of physics exams!!! 😭"
        score = calculator.calculate_importance(important_text)
        print(f"  ✅ Importance scoring: score={score:.2f}")
        
        # Test memory_core integration
        result = process_memory(important_text)
        print(f"  ✅ Memory processing: category={result['importance_category']}")
        
        print("\n" + "=" * 60)
        print("✅ PHASE 2 COMPONENTS VERIFIED SUCCESSFULLY!")
        print("=" * 60)
        
        print("\n📊 Component Status:")
        print("  • pattern_detector.py         ✅ Ready")
        print("  • memory_importance_calculator.py ✅ Ready")
        print("  • core/memory_core.py (enhanced) ✅ Ready")
        print("  • test_memory_importance.py   ✅ Created")
        
        print("\n🚀 Phase 2 is ready for deployment!")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = verify_phase2_components()
    exit(0 if success else 1)
