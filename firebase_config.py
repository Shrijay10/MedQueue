import firebase_admin
from firebase_admin import credentials, firestore
import json
import os

# 🔥 Get firebase key from environment variable
firebase_json = os.environ.get("FIREBASE_KEY")

if not firebase_json:
    raise ValueError("FIREBASE_KEY not found in environment variables")

cred = credentials.Certificate(json.loads(firebase_json))

# Initialize only once
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()