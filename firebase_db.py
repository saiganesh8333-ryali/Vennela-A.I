"""Firebase database initialization for local development and cloud deploys."""
import base64
import json
import logging
import os
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore

logger = logging.getLogger(__name__)

db: Optional[firestore.Client] = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_KEY_PATH = os.path.join(BASE_DIR, "vennela-firebase-key.json")


def _load_credentials():
    """Load Firebase credentials from env JSON/base64 or a local key file."""
    credentials_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
    if credentials_json:
        return credentials.Certificate(json.loads(credentials_json))

    credentials_base64 = os.getenv("FIREBASE_CREDENTIALS_BASE64")
    if credentials_base64:
        decoded = base64.b64decode(credentials_base64).decode("utf-8")
        return credentials.Certificate(json.loads(decoded))

    credential_path = (
        os.getenv("FIREBASE_CREDENTIALS")
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        or DEFAULT_KEY_PATH
    )

    if not os.path.isabs(credential_path):
        credential_path = os.path.join(BASE_DIR, credential_path)

    if not os.path.exists(credential_path):
        raise FileNotFoundError(f"Firebase credentials not found: {credential_path}")

    return credentials.Certificate(credential_path)


def initialize_firebase() -> bool:
    """Initialize Firebase connection once."""
    global db

    try:
        if firebase_admin._apps:
            db = firestore.client()
            logger.info("Using existing Firebase app instance")
            return True

        firebase_admin.initialize_app(_load_credentials())
        db = firestore.client()
        logger.info("Firebase initialized successfully")
        return True
    except Exception as exc:
        logger.error("Failed to initialize Firebase: %s", exc)
        db = None
        return False


def get_db() -> Optional[firestore.Client]:
    """Get Firestore client, initializing Firebase if needed."""
    global db

    if db is None and not initialize_firebase():
        return None

    return db
