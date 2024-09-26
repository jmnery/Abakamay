# databaseServices.py
import firebase_admin
from firebase_admin import credentials, firestore, storage
import os
from werkzeug.utils import secure_filename

# Firebase credentials and initialization


import firebase_admin
from firebase_admin import credentials, firestore, storage


def initialize_firebase(credentials_path, database_url, storage_bucket):
    try:
        # Initialize Firebase with provided credentials and services
        cred = credentials.Certificate(credentials_path)
        firebase_admin.initialize_app(cred, {
            'databaseURL': database_url,
            'storageBucket': storage_bucket  # Ensure storageBucket is set here
        })
        print("Firebase Initialized successfully.")
    except Exception as e:
        print(f"Error initializing Firebase: {e}")


# Get Firestore client


def get_firestore_client():
    return firestore.client()

# Function to add a user to Firestore


def add_user_to_db(user_id, first_name, last_name, email, age):
    db = get_firestore_client()
    db.collection('users').document(user_id).set({
        'userId': user_id,
        'firstName': first_name,
        'lastName': last_name,
        'email': email,
        'age': age,
        "completedWords": 0,
        "completed": {}
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

# Function to add letter, syllable, and words to Firestore


def add_letter_syllable_words(letter, syllable, words):
    letter = letter.upper()
    syllable = syllable.upper()
    # Split words by comma and strip whitespace
    words = [word.strip() for word in words.split(',')]

    db = get_firestore_client()
    letter_ref = db.collection('letters').document(letter)
    letter_doc = letter_ref.get()

    try:
        if letter_doc.exists:
            # Update the existing document by adding words to the syllable
            letter_ref.update(
                {f'syllables.{syllable}': firestore.ArrayUnion(words)})
        else:
            # Create a new document if it doesn't exist
            letter_ref.set({
                'syllables': {
                    syllable: words
                }
            })
        print(
            f"Successfully added/updated letter {letter}, syllable {syllable}, and words: {words}")
    except Exception as e:
        print(f"Error adding to Firestore: {e}")


def get_letter_words_and_completed(user_id):
    db = get_firestore_client()
    """
    Fetches letter words and completed words for a user.
    Returns a tuple (letter_words, completed_words).
    """
    completed_words = {}
    letter_words = {}

    # Fetch completed words
    user_ref = db.collection('users').document(user_id)
    user_doc = user_ref.get()

    if user_doc.exists:
        completed_data = user_doc.to_dict().get('completed', {})
        for letter, words in completed_data.items():
            if isinstance(words, list):
                completed_words[letter] = set(
                    word for word in words if isinstance(word, str))

    # Fetch letter words
    letters_ref = db.collection('letters')
    docs = letters_ref.stream()

    for doc in docs:
        letter = doc.id
        letter_data = doc.to_dict()
        syllables = letter_data.get('syllables', {})

        words = []
        for syllable, words_list in syllables.items():
            if isinstance(words_list, list):
                words.extend(
                    word for word in words_list if isinstance(word, str))

        letter_words[letter] = words

    return letter_words, completed_words


def get_letter_words(user_id):
    db = get_firestore_client()
    letters_ref = db.collection('letters')
    all_letters = letters_ref.stream()

    # Dictionary to store all the syllables and words for each letter
    letter_words = {}

    for letter_doc in all_letters:
        letter = letter_doc.id  # Letter name, e.g., "B"
        syllables = letter_doc.to_dict().get('syllables', {})

        # Flatten syllables and words into a single list for each letter
        words = []
        for syllable, word_list in syllables.items():
            words.extend(word_list)

        letter_words[letter] = words

    return letter_words


def get_letter_words_and_completed_with_images(user_id):
    db = get_firestore_client()
    """
    Fetches letter words with images and completed words for a user.
    Returns a tuple (letter_words, completed_words).
    """
    completed_words = {}
    letter_words = {}

    # Fetch completed words
    user_ref = db.collection('users').document(user_id)
    user_doc = user_ref.get()

    if user_doc.exists:
        completed_data = user_doc.to_dict().get('completed', {})
        for letter, words in completed_data.items():
            if isinstance(words, list):
                completed_words[letter] = set(
                    word for word in words if isinstance(word, str))

    # Fetch letter words
    letters_ref = db.collection('words')
    docs = letters_ref.stream()

    for doc in docs:
        letter = doc.id
        letter_data = doc.to_dict()
        syllables = letter_data.get('syllables', {})

        words = []
        for syllable, word_list in syllables.items():
            if isinstance(word_list, list):
                for word_info in word_list:
                    if isinstance(word_info, dict):
                        text = word_info.get('text', '')
                        extension = word_info.get('extension', 'jpg')
                        value = word_info.get('value', '')
                        words.append({
                            'text': text,
                            'extension': extension,
                            'value': value
                        })

        letter_words[letter] = words

    return letter_words, completed_words


def upload_file_to_storage(file, letter, syllable, words):
    try:
        # Extract the file extension
        file_extension = os.path.splitext(file.filename)[1]

        # Define the path for storing the file in Firebase Storage
        # Organize based on letter and syllable
        file_path = f'{file.filename}'

        # Get a reference to the Firebase Storage bucket
        bucket = storage.bucket()

        # Create a new blob (file) in the storage
        blob = bucket.blob(file_path)

        # Upload the file to the storage bucket
        blob.upload_from_file(file)

        # Make the file publicly accessible
        blob.make_public()

        # Get the public URL of the uploaded file
        file_url = blob.public_url

        # Add or update Firestore document for the letter with syllable and words info
        db = firestore.client()
        letter_ref = db.collection('words').document(letter)
        letter_doc = letter_ref.get()

        if letter_doc.exists:
            letter_data = letter_doc.to_dict()
            syllables = letter_data.get('syllables', {})
            syllables[syllable] = [
                {'text': word.lower(), 'extension': file_extension} for word in words]
            letter_ref.update({'syllables': syllables})
        else:
            syllables = {syllable: [
                {'text': word.lower(), 'extension': file_extension} for word in words]}
            letter_ref.set({'syllables': syllables})

        return {'status': 'success', 'file_url': file_url}

    except Exception as e:
        return {'status': 'error', 'message': str(e)}
