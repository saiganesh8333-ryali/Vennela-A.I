import firebase_admin
from firebase_admin import credentials, firestore

# 🔐 Initialize Firebase only once
if not firebase_admin._apps:

    cred = credentials.Certificate("serviceAccount.json")
    firebase_admin.initialize_app(cred)

# ☁️ Firestore client
db = firestore.client()