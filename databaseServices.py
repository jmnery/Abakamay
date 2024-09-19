# databaseServices.py
import firebase_admin
from firebase_admin import credentials, firestore

# Firebase credentials and initialization


def initialize_firebase(credentials_path, database_url):
    try:
        cred = credentials.Certificate(credentials_path)
        firebase_admin.initialize_app(
            cred, {"databaseURL": database_url})
        print("Firebase initialized successfully.")
    except Exception as e:
        print(f"Error initializing Firebase: {e}")

# Get Firestore client


def get_firestore_client():
    return firestore.client()

# Function to add a user to Firestore


def add_user_to_db(user_id, first_name, last_name, email, age):
    db = get_firestore_client()
    db.collection('users').document(user_id).set({
        'firstName': first_name,
        'lastName': last_name,
        'email': email,
        'age': age,
        "completedWords": 0
    })

# Function to get all users from Firestore


def get_all_users():
    db = get_firestore_client()
    users_ref = db.collection('users')
    docs = users_ref.stream()

    users = {}
    for doc in docs:
        users[doc.id] = doc.to_dict()
    return users
