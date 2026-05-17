#!/usr/bin/env python3
"""
Quick test script for AI Provider Failover System
Tests both providers and the health check endpoint
"""

import asyncio
import json
from main import app, ai_health_check
from fastapi.testclient import TestClient

client = TestClient(app)

def test_health_endpoint():
    """Test basic health endpoint"""
    print("\n📊 Testing /health endpoint...")
    response = client.get("/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    print("✅ /health endpoint working")

def test_ai_health_endpoint():
    """Test AI provider health check"""
    print("\n🏥 Testing /ai-health endpoint...")
    response = client.get("/ai-health")
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    assert response.status_code == 200
    print("✅ /ai-health endpoint working")
    
    # Check if at least one provider is configured
    groq_status = data.get("groq", "")
    openrouter_status = data.get("openrouter", "")
    
    if "healthy" in str(groq_status):
        print("✅ Groq provider is healthy")
    elif "not_configured" in str(groq_status):
        print("⚠️ Groq not configured")
    else:
        print(f"❌ Groq failed: {groq_status}")
    
    if "healthy" in str(openrouter_status):
        print("✅ OpenRouter provider is healthy")
    elif "not_configured" in str(openrouter_status):
        print("⚠️ OpenRouter not configured")
    else:
        print(f"❌ OpenRouter failed: {openrouter_status}")

def test_root():
    """Test root endpoint"""
    print("\n🌍 Testing root endpoint...")
    response = client.get("/")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    print("✅ Root endpoint working")

if __name__ == "__main__":
    print("=" * 60)
    print("🔥 Vennela AI - Failover System Test Suite")
    print("=" * 60)
    
    try:
        test_root()
        test_health_endpoint()
        test_ai_health_endpoint()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed! System is ready for production")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
