#fire_base.py
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
_firebase_init_attempted = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _firebase_enabled() -> bool:
    """Check Firebase toggle at runtime so .env values are respected."""
    return os.getenv("FIREBASE_ENABLED", "true").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _env_value(*names: str) -> Optional[str]:
    """Return the first non-empty environment variable from a list."""
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _load_credentials_from_fields():
    """Build Firebase credentials from individual Render environment variables."""
    project_id = _env_value("FIREBASE_PROJECT_ID", "project_id")
    private_key = _env_value("FIREBASE_PRIVATE_KEY", "private_key")
    client_email = _env_value("FIREBASE_CLIENT_EMAIL", "client_email")

    if not all([project_id, private_key, client_email]):
        return None

    return credentials.Certificate(
        {
            "type": _env_value("FIREBASE_TYPE", "type") or "service_account",
            "project_id": project_id,
            "private_key_id": _env_value("FIREBASE_PRIVATE_KEY_ID", "private_key_id"),
            "private_key": private_key.replace("\\n", "\n"),
            "client_email": client_email,
            "client_id": _env_value("FIREBASE_CLIENT_ID", "client_id"),
            "auth_uri": _env_value("FIREBASE_AUTH_URI", "auth_uri")
            or "https://accounts.google.com/o/oauth2/auth",
            "token_uri": _env_value("FIREBASE_TOKEN_URI", "token_uri")
            or "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": _env_value(
                "FIREBASE_AUTH_PROVIDER_X509_CERT_URL",
                "auth_provider_x509_cert_url",
            )
            or "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": _env_value(
                "FIREBASE_CLIENT_X509_CERT_URL",
                "client_x509_cert_url",
            ),
            "universe_domain": _env_value("FIREBASE_UNIVERSE_DOMAIN", "universe_domain")
            or "googleapis.com",
        }
    )


def _load_credentials_from_json(credentials_json: str):
    """Load Firebase credentials from a JSON environment variable."""
    data = json.loads(credentials_json)
    if "private_key" in data and isinstance(data["private_key"], str):
        data["private_key"] = data["private_key"].replace("\\n", "\n")
    return credentials.Certificate(data)


def _load_credentials():
    """Load Firebase credentials from environment variables."""
    credentials_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
    if credentials_json:
        return _load_credentials_from_json(credentials_json)

    credentials_value = os.getenv("FIREBASE_CREDENTIALS")
    if credentials_value and credentials_value.strip().startswith("{"):
        return _load_credentials_from_json(credentials_value)

    credentials_base64 = os.getenv("FIREBASE_CREDENTIALS_BASE64")
    if credentials_base64:
        decoded = base64.b64decode(credentials_base64).decode("utf-8")
        return _load_credentials_from_json(decoded)

    field_credentials = _load_credentials_from_fields()
    if field_credentials:
        return field_credentials

    credential_path = credentials_value or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if not credential_path:
        raise RuntimeError(
            "Firebase credentials are not configured. Set FIREBASE_CREDENTIALS_JSON, "
            "FIREBASE_CREDENTIALS_BASE64, the individual FIREBASE_* variables, or "
            "FIREBASE_CREDENTIALS/GOOGLE_APPLICATION_CREDENTIALS to an explicit file path."
        )

    if not os.path.isabs(credential_path):
        credential_path = os.path.join(BASE_DIR, credential_path)

    if not os.path.exists(credential_path):
        raise FileNotFoundError(f"Firebase credentials not found: {credential_path}")

    return credentials.Certificate(credential_path)


def initialize_firebase() -> bool:
    """Initialize Firebase connection once."""
    global db, _firebase_init_attempted

    if not _firebase_enabled():
        logger.warning("Firebase is disabled by FIREBASE_ENABLED=false")
        db = None
        return False

    try:
        if _firebase_init_attempted and db is None:
            return False

        if firebase_admin._apps:
            db = firestore.client()
            logger.info("Using existing Firebase app instance")
            return True

        _firebase_init_attempted = True
        firebase_admin.initialize_app(_load_credentials())
        db = firestore.client()
        logger.info("Firebase initialized successfully")
        return True
    except Exception as exc:
        logger.warning("Firebase unavailable, continuing without database: %s", exc)
        db = None
        return False


def get_db() -> Optional[firestore.Client]:
    """Get Firestore client, initializing Firebase if needed."""
    global db

    if db is None and not initialize_firebase():
        return None

    return db
