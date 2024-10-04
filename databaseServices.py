# databaseServices.py
import firebase_admin
from firebase_admin import credentials, firestore, storage
import os
from werkzeug.utils import secure_filename
import uuid

# Firebase credentials and initialization


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
                        wordID = word_info.get('wordID', '')
                        words.append({
                            'text': text,
                            'extension': extension,
                            'value': value,
                            'wordID': wordID
                        })

        letter_words[letter] = words

    return letter_words, completed_words


def upload_file_to_storage(file, letter, syllable, letterType, words, value):
    try:
        # Extract the file extension
        file_extension = os.path.splitext(file.filename)[1]

        # Define the path for storing the file in Firebase Storage
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

        # Firestore client initialization
        db = firestore.client()

        # Retrieve the Firestore document for the letter
        letter_ref = db.collection('words').document(letter)
        letter_doc = letter_ref.get()

        # Prepare new word entries for the syllable
        new_words = [{'text': word.lower(), 'extension': file_extension, 'value': value, 'wordID': str(uuid.uuid4())}
                     for word in words]

        if letter_doc.exists:
            # Get the existing data
            letter_data = letter_doc.to_dict()
            syllables = letter_data.get('syllables', {})

            # Append the new words to the existing ones for the syllable
            if syllable in syllables:
                syllables[syllable].extend(new_words)
            else:
                syllables[syllable] = new_words

            # Check if letterType is provided; otherwise, keep the existing one
            if not letterType:
                # Default to empty if no existing type
                letterType = letter_data.get('type', '')

            # Update the Firestore document, including the letterType
            letter_ref.update({
                'syllables': syllables,
                'type': letterType  # Use the existing or provided letterType
            })
        else:
            # Create a new document if it doesn't exist
            syllables = {syllable: new_words}
            letter_ref.set({
                'syllables': syllables,
                # Add letterType or set as empty if not provided
                'type': letterType if letterType else ''
            })

        return {'status': 'success', 'file_url': file_url}

    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def add_learned_word(user_id, letter, syllable, word):
    db = get_firestore_client()
    # Reference to the user's document in Firestore
    user_ref = db.collection('users').document(user_id)

    # Update the learned field
    user_ref.set({
        'learned': {
            letter: {
                syllable: firestore.ArrayUnion([word])
            }
        }
    }, merge=True)

    # Increment the wordCount for the letter in the learned document
    user_ref.update({
        # Increment wordCount by 1
        f'learned.{letter}.wordCount': firestore.Increment(1)
    })

    print(
        f"Added word '{word}' for user '{user_id}' under letter '{letter}' and syllable '{syllable}'.")


def get_all_words():
    db = get_firestore_client()
    # Adjust this to match your Firestore structure
    words_ref = db.collection('words')
    words = []

    # Fetch only the necessary fields from each document to avoid excessive loading time
    docs = words_ref.stream()
    for doc in docs:
        word_data = doc.to_dict()
        for syllable, syllable_data in word_data.get('syllables', {}).items():
            for word_info in syllable_data:
                # Assuming you store the word text
                word = {
                    'text': word_info.get('text', ''),         # Word text
                    # Word extension (e.g., .jpg, .png)
                    'extension': word_info.get('extension', '')
                }
                words.append(word)

    return words


def get_user_progress(user_id):
    db = get_firestore_client()
    user_ref = db.collection('users').document(user_id)
    user_data = user_ref.get().to_dict()

    if not user_data:  # Check if user_data is None
        return []

    completed_words = []

    learned = user_data.get('learned', {})
    for letter, syllables in learned.items():
        for syllable, words in syllables.items():
            if isinstance(words, list):  # Ensure words is a list
                completed_words.extend(words)

    return completed_words


# # Function to get the total number of words for a given letter


# def getTotalWordNum(letter):
#     db = get_firestore_client()
#     words_ref = db.collection('words').document(letter)
#     words_doc = words_ref.get()

#     if words_doc.exists:
#         return words_doc.to_dict().get('wordCount', 0)
#     return 0


# # Function to get the total number of learned words for a given user and letter


# def getTotalLearnedNum(user_id, letter):
#     db = get_firestore_client()
#     user_ref = db.collection('users').document(user_id)
#     user_doc = user_ref.get()

#     if user_doc.exists:
#         learned_data = user_doc.to_dict().get('learned', {})
#         letter_data = learned_data.get(letter, {})

#         # Use wordCount directly if it exists, else calculate learned_word_count
#         learned_word_count = letter_data.get('wordCount', 0)

#         return learned_word_count

#     return 0
