import firebase_admin
from firebase_admin import credentials, firestore

import os
from firebase_admin import credentials, firestore, initialize_app

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_PATH = os.path.join(BASE_DIR, "firebase_key.json")

cred = credentials.Certificate(KEY_PATH)
initialize_app(cred)

db = firestore.client()

