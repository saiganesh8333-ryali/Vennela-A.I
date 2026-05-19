from firebase.firebase_db import db
from datetime import datetime

# ---------------- USER ---------------- #
def get_user_data(user_id):
    doc = db.collection("users").document(user_id).get()
    return doc.to_dict() if doc.exists else {}


# ---------------- MEMORY ---------------- #
def get_memory(user_id):
    doc = db.collection("memory").document(user_id).get()

    if doc.exists:
        return doc.to_dict()
    else:
        return {
            "chat_history": [],
            "preferences": {},
            "notes": ""
        }


# ---------------- SAVE MEMORY ---------------- #
def save_memory(user_id, data):
    db.collection("memory").document(user_id).set(data, merge=True)


# ---------------- ADD CHAT ENTRY ---------------- #
def add_chat(user_id, role, message, reinforcement_score=0.0, metadata=None):
    doc_ref = db.collection("memory").document(user_id)

    doc = doc_ref.get()

    if doc.exists:
        data = doc.to_dict()
        chat_history = data.get("chat_history", [])
    else:
        chat_history = []

    entry = {
        "role": role,
        "message": message,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "reinforcement_score": reinforcement_score,
        "metadata": metadata or {}
    }

    chat_history.append(entry)

    doc_ref.set({
        "chat_history": chat_history
    }, merge=True)

    return entry