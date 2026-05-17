#!/usr/bin/env python3
"""Quick Firebase connection test."""
import sys

from dotenv import load_dotenv

from firebase_db import get_db, initialize_firebase


def main() -> int:
    """Initialize Firebase from env vars and verify Firestore responds."""
    load_dotenv()

    print("=" * 60)
    print("FIREBASE DIAGNOSTIC TEST")
    print("=" * 60)

    print("\n1. Firebase initialization:")
    if not initialize_firebase():
        print("   FAILED: Firebase could not be initialized.")
        print("   Set FIREBASE_CREDENTIALS_JSON or the individual FIREBASE_* environment variables.")
        return 1

    db = get_db()
    if db is None:
        print("   FAILED: Firestore client is unavailable.")
        return 1

    print("   OK: Firestore client created")

    print("\n2. Firestore connection test:")
    collections = db.collections()
    collection_list = [collection.id for collection in collections]
    print(f"   Collections found: {collection_list or 'None yet'}")
    print("   OK: Firestore is working")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED - FIREBASE IS READY")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
