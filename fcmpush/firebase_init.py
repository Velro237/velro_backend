import os
from firebase_admin import credentials, initialize_app

def init_firebase():
    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
    if not cred_path or not os.path.exists(cred_path):
        print("⚠️ Firebase credential file not found, skipping init.")
        return
    cred = credentials.Certificate(cred_path)
    initialize_app(cred)
    print("✅ Firebase initialized successfully.")
