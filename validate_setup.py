#!/usr/bin/env python3
"""Validate Vennela AI setup before running."""
import os
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'


def check_python_version():
    """Check Python version."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        logger.error(f"❌ Python 3.8+ required, found {version.major}.{version.minor}")
        return False
    logger.info(f"✅ Python version: {version.major}.{version.minor}")
    return True


def check_dependencies():
    """Check if all dependencies are installed."""
    dependencies = [
        'fastapi', 'uvicorn', 'pydantic', 'openai', 'groq',
        'transformers', 'sentence_transformers', 'firebase_admin'
    ]
    
    all_ok = True
    for dep in dependencies:
        try:
            __import__(dep.replace('-', '_'))
            logger.info(f"✅ {dep}")
        except ImportError:
            logger.error(f"❌ {dep} (run: pip install -r requirements.txt)")
            all_ok = False
    
    return all_ok


def check_environment():
    """Check .env file and keys."""
    env_file = Path('.env')
    
    if not env_file.exists():
        logger.warning(f"⚠️  .env file not found. Copy from .env.example and fill in your keys")
        return False
    
    logger.info("✅ .env file exists")
    
    # Load env
    from dotenv import load_dotenv
    load_dotenv()
    
    # Check required keys
    required_keys = ['GROQ_API_KEY', 'OPENROUTER_API_KEY', 'VENNELA_PROMPT']
    missing = []
    
    for key in required_keys:
        value = os.getenv(key)
        if not value or value.startswith('your_'):
            missing.append(key)
    
    if missing:
        logger.warning(f"⚠️  Missing or invalid keys in .env: {', '.join(missing)}")
        return False
    
    logger.info(f"✅ All required environment variables set")
    return True


def check_firebase():
    """Check Firebase credentials."""
    cred_path = os.getenv("FIREBASE_CREDENTIALS", "serviceAccount.json")
    if not os.path.exists(cred_path):
        cred_path = "vennela-firebase-key.json"
    
    if not os.path.exists(cred_path):
        logger.warning(f"⚠️  Firebase credentials not found at {cred_path}")
        logger.info("     Download from Firebase Console → Project Settings → Service Accounts")
        return False
    
    logger.info(f"✅ Firebase credentials: {cred_path}")
    return True


def check_files():
    """Check if required files exist."""
    required_files = [
        'main.py',
        'ai_router.py',
        'smart_memory.py',
        'nlp_engine.py',
        'embedding_engine.py',
        'retrieval.py',
        'firebase_db.py',
        'requirements.txt'
    ]
    
    all_ok = True
    for file in required_files:
        if not Path(file).exists():
            logger.error(f"❌ {file} not found")
            all_ok = False
        else:
            logger.info(f"✅ {file}")
    
    return all_ok


def main():
    """Run all checks."""
    print(f"\n{GREEN}🧠 VENNELA AI - Setup Validation{RESET}\n")
    
    checks = [
        ("Python Version", check_python_version),
        ("Project Files", check_files),
        ("Dependencies", check_dependencies),
        ("Environment Variables", check_environment),
        ("Firebase Credentials", check_firebase),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n{YELLOW}Checking: {name}{RESET}")
        try:
            result = check_func()
            results.append(result)
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            results.append(False)
    
    # Summary
    print(f"\n{GREEN}{'='*50}{RESET}")
    passed = sum(results)
    total = len(results)
    
    if all(results):
        print(f"{GREEN}✅ All checks passed! Ready to run.{RESET}")
        print(f"\n{YELLOW}Start server with:{RESET}")
        print(f"  uvicorn main:app --reload")
        return 0
    else:
        print(f"{RED}❌ {total - passed} check(s) failed.{RESET}")
        print(f"\nFix the issues above and run this script again.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
