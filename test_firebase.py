#!/usr/bin/env python3
"""Quick Firebase connection test."""
import os
import sys

print("=" * 60)
print("🔥 FIREBASE DIAGNOSTIC TEST")
print("=" * 60)

# Test 1: Check working directory
print(f"\n1️⃣ Working Directory:")
print(f"   Current: {os.getcwd()}")
print(f"   Expected: d:\\Vennela A.I")

# Test 2: Check Firebase key file
print(f"\n2️⃣ Firebase Key File:")
key_file = "vennela-firebase-key.json"
key_exists = os.path.exists(key_file)
print(f"   Path: {os.path.abspath(key_file)}")
print(f"   Exists: {'✅ YES' if key_exists else '❌ NO'}")

if not key_exists:
    print("\n   ⚠️ Firebase key file is missing!")
    print("   Get it from: Firebase Console → Project Settings → Service Account → Generate New Key")
    sys.exit(1)

# Test 3: Try to initialize Firebase
print(f"\n3️⃣ Firebase Initialization:")
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    
    print("   ✅ Firebase libraries imported")
    
    cred = credentials.Certificate(key_file)
    print("   ✅ Credentials loaded")
    
    if firebase_admin._apps:
        print("   ℹ️ Firebase app already initialized")
        db = firestore.client()
    else:
        firebase_admin.initialize_app(cred)
        print("   ✅ Firebase app initialized")
        db = firestore.client()
    
    print("   ✅ Firestore client created")
    
    # Test 4: Try a simple query
    print(f"\n4️⃣ Firestore Connection Test:")
    collections = db.collections()
    collection_list = [c.id for c in collections]
    print(f"   Collections found: {collection_list or 'None yet'}")
    print(f"   ✅ Firestore is working!")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED - FIREBASE IS READY")
    print("=" * 60)
    
except FileNotFoundError as e:
    print(f"   ❌ File not found: {e}")
    sys.exit(1)
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
