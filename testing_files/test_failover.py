#!/usr/bin/env python3
"""
Quick test script for the application health endpoints.
Uses the actual app entrypoint rather than a fake compatibility symbol.
"""

import json
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_health_endpoint():
    """Test basic health endpoint"""
    print("\n📊 Testing /health endpoint...")
    response = client.get("/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    print("✅ /health endpoint working")


def test_status_endpoint():
    """Test the real application status endpoint."""
    print("\n🏥 Testing /status endpoint...")
    response = client.get("/status")
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    assert response.status_code == 200
    assert data["status"] == "running"
    print("✅ /status endpoint working")


def test_root():
    """Test root endpoint"""
    print("\n🌍 Testing root endpoint...")
    response = client.get("/")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    print("✅ Root endpoint working")


if __name__ == "__main__":
    print("=" * 60)
    print("🔥 Vennela AI - Application Health Test Suite")
    print("=" * 60)

    try:
        test_root()
        test_health_endpoint()
        test_status_endpoint()

        print("\n" + "=" * 60)
        print("✅ All tests passed! System is ready for production")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
