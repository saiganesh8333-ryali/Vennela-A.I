"""
🔥 CLEANUP SCRIPT — Delete all old bad greeting messages from Firebase

This script:
1. Connects to Firebase
2. Deletes ALL chat history (old bad greetings)
3. Clears memory collections
4. Leaves user data intact

IMPORTANT: Run this ONCE before redeploying!
"""

import logging
import sys
from firebase_db import initialize_firebase, get_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================
# BAD PATTERNS TO IDENTIFY
# =========================
BAD_PATTERNS = [
    "system online",
    "listening",
    "how can i assist",
    "i'm ready to help",
    "hello i am vennela",
    "i am vennela",
    "i'm vennela",
]


def delete_all_chat_history():
    """Delete ALL chat history from Firestore to clear bad greetings."""
    try:
        db = get_db()
        if not db:
            logger.error("❌ Firebase not available")
            return False
        
        logger.info("🔥 Starting to delete chat history...")
        
        # Get all users from chat_memory collection
        users = db.collection("chat_memory").stream()
        deleted_count = 0
        
        for user_doc in users:
            user_id = user_doc.id
            logger.info(f"  📍 Processing user: {user_id}")
            
            # Get all messages for this user
            messages = db.collection("chat_memory") \
                .document(user_id) \
                .collection("messages") \
                .stream()
            
            for msg_doc in messages:
                msg_doc.reference.delete()
                deleted_count += 1
            
            logger.info(f"    ✅ Deleted {deleted_count} messages for {user_id}")
        
        logger.info(f"✅ TOTAL DELETED: {deleted_count} messages")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error deleting chat history: {e}")
        return False


def reset_memory_collections():
    """Reset memory collections but keep important user profile data."""
    try:
        db = get_db()
        if not db:
            logger.error("❌ Firebase not available")
            return False
        
        logger.info("🔥 Resetting memory collections...")
        
        memory_docs = db.collection("memory").stream()
        reset_count = 0
        
        for mem_doc in memory_docs:
            user_id = mem_doc.id
            
            # Reset to clean memory structure (keep profile)
            clean_memory = {
                "profile": mem_doc.to_dict().get("profile", {}),  # Keep user profile
                "short_term": [],
                "long_term": [],
                "emotions": {},
                "sentiments": {},
                "importance": [],
                "summary": "",
                "embeddings": []
            }
            
            db.collection("memory").document(user_id).set(clean_memory)
            reset_count += 1
            logger.info(f"  ✅ Reset memory for user: {user_id}")
        
        logger.info(f"✅ TOTAL RESET: {reset_count} memory records")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error resetting memory: {e}")
        return False


def main():
    """Main cleanup function."""
    logger.info("=" * 60)
    logger.info("🔥 VENNELA AI — HISTORY CLEANUP SCRIPT")
    logger.info("=" * 60)
    
    # Initialize Firebase
    if not initialize_firebase():
        logger.error("❌ Failed to initialize Firebase")
        sys.exit(1)
    
    logger.info("✅ Firebase connected")
    
    # Step 1: Delete chat history
    if not delete_all_chat_history():
        logger.error("❌ Failed to delete chat history")
        sys.exit(1)
    
    # Step 2: Reset memory
    if not reset_memory_collections():
        logger.error("❌ Failed to reset memory")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("✅ CLEANUP COMPLETE!")
    logger.info("=" * 60)
    logger.info("""
🚀 NEXT STEPS:
1. Push to Git: git add . && git commit -m "cleanup bad history"
2. Deploy to Render: Manual Deploy + Clear Build Cache & Deploy
3. Test the AI with: "what is programming"
4. Expected: Direct answer (NO greetings)
    """)


if __name__ == "__main__":
    main()
