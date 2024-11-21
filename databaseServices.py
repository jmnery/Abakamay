# databaseServices.py
from google.cloud import firestore
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


def add_user_to_db(user_id, first_name, last_name, email, age, birthday, avatar):
    db = get_firestore_client()
    db.collection('users').document(user_id).set({
        'userId': user_id,
        'firstName': first_name,
        'lastName': last_name,
        'email': email,
        'age': age,
        "complete": {},
        'birthday': birthday,
        'avatar': avatar,
        'badges': {
            'A': False,
            'B': False,
            'K': False,
            'D': False,
            'E': False,
            'G': False,
            'H': False,
            'I': False,
            'L': False,
            'M': False,
            'N': False,
            'NG': False,
            'O': False,
            'P': False,
            'R': False,
            'S': False,
            'T': False,
            'U': False,
            'W': False,
            'Y': False
        }
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


def upload_file_to_storage(file, letter, syllable, letterType, value):
    try:
        # Ensure the letter is uppercase
        letter = letter.upper()

        # Ensure the first letter of the syllable is capitalized
        syllable = syllable.capitalize()
        # Extract the file name (without extension) and the file extension
        file_name = os.path.splitext(file.filename)[0].lower()
        file_extension = os.path.splitext(file.filename)[1]

        # Define the path for storing the file in Firebase Storage
        file_path = file.filename.lower()

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

        # Prepare the word entry for the syllable
        new_word = {
            'text': file_name,
            'extension': file_extension,
            'value': value,
            'wordID': str(uuid.uuid4())
        }

        if letter_doc.exists:
            # Get the existing data
            letter_data = letter_doc.to_dict()
            syllables = letter_data.get('syllables', {})

            # Append the new word to the existing ones for the syllable
            if syllable in syllables:
                syllables[syllable].append(new_word)
            else:
                syllables[syllable] = [new_word]

            # Check if letterType is provided; otherwise, keep the existing one
            if not letterType:
                letterType = letter_data.get('type', '')

            # Update the Firestore document, including the letterType
            letter_ref.update({
                'syllables': syllables,
                'wordCount': firestore.Increment(1)  # Increment the wordCount
            })
        else:
            # Create a new document if it doesn't exist
            syllables = {syllable: [new_word]}
            letter_ref.set({
                'syllables': syllables,
                'type': letterType if letterType else '',
                'wordCount': 1
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


def get_all_letters():
    db = get_firestore_client()
    """Retrieve all letters in the words collection."""
    letters_ref = db.collection('words').stream()
    return [letter.id for letter in letters_ref]


def get_all_words():
    db = get_firestore_client()
    # Adjust this to match your Firestore structure
    words_ref = db.collection('words')
    words = []

    # Fetch only the necessary fields from each document to avoid excessive loading time
    docs = words_ref.stream()
    for doc in docs:
        letter = doc.id
        word_data = doc.to_dict()
        for syllable, syllable_data in word_data.get('syllables', {}).items():
            for word_info in syllable_data:
                # Assuming you store the word text
                word = {
                    'text': word_info.get('text', ''),         # Word text
                    # Word extension (e.g., .jpg, .png)
                    'extension': word_info.get('extension', ''),
                    'value': word_info.get('value', ''),
                    'syllable': syllable,
                    'letter': letter
                }
                words.append(word)

    return words


def get_words_by_letter(letter):
    db = get_firestore_client()
    words_ref = db.collection('words').document(letter)
    words = []

    # Fetch the document for the specific letter
    doc = words_ref.get()
    if doc.exists:
        word_data = doc.to_dict()
        # Iterate over syllables for the given letter
        for syllable, syllable_data in word_data.get('syllables', {}).items():
            for word_info in syllable_data:
                word = {
                    'text': word_info.get('text', ''),        # Word text
                    # Word extension
                    'extension': word_info.get('extension', ''),
                    'value': word_info.get('value', ''),
                    'syllable': syllable,
                    'letter': letter
                }
                words.append(word)

    return words


def get_user_progress(user_id):
    db = get_firestore_client()
    # Reference the user document
    user_ref = db.collection('users').document(user_id)
    user_doc = user_ref.get()

    # Initialize an empty list for completed words
    completed_words = []

    if user_doc.exists:
        user_data = user_doc.to_dict()

        # Fetch completed words, assuming they're stored under 'complete' for letters
        completed_data = user_data.get('complete', {})

        # Iterate over the completed words structure
        for letter, syllables in completed_data.items():
            for syllable, words in syllables.items():
                if isinstance(words, list):  # Ensure words is a list
                    # Add completed words to the list
                    completed_words.extend(words)

    return completed_words


def get_user_data_by_id(user_id):
    db = get_firestore_client()
    try:
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            print("user data: ", user_data)
            return user_data
        else:
            print("No such user!")
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def markAsComplete(user_id, completed_data):
    db = get_firestore_client()
    user_ref = db.collection('users').document(user_id)
    print("completed_data: ", completed_data)
    for letter, syllable_data in completed_data.items():
        # Create a field path for the specific letter
        letter_path = f'complete.{letter}'

        # Update the completed words in Firestore
        for syllable, words in syllable_data.items():
            if syllable != 'wordCount':  # Avoid processing wordCount here
                # Update the learned field with the syllable
                user_ref.set({
                    'complete': {
                        letter: {
                            # Use ArrayUnion to add words
                            syllable: firestore.ArrayUnion(words)
                        }
                    }
                }, merge=True)


def addToHistory(user_id, quiz_id, timestamp, score, correct_answers, total_questions, user_answers):
    db = get_firestore_client()
    history_ref = db.collection('users').document(
        user_id).collection('history').document(quiz_id)

    history_ref.set({
        "quiz_id": quiz_id,  # Use the quiz_id from the request
        "timestamp": timestamp,  # Use the timestamp from the request
        "score": score,
        "correct_answers": correct_answers,
        "total_questions": total_questions,
        "user_answers": user_answers,
    })


def addBadgesToComplete(user_id, user_answers):

    db = get_firestore_client()

    # Filter user_answers for correct entries and extract their letters
    correct_letters = [
        answer['word']['letter']
        for answer in user_answers
        if answer.get('correct') == True
    ]

    # Create a dictionary to store results
    results = {}

    for letter in set(correct_letters):  # Use set to avoid duplicate processing
        # Get user's completion data for the letter
        user_complete_ref = db.collection('users').document(user_id)
        user_complete_data = user_complete_ref.get().to_dict().get('complete', {})
        letter_complete_data = user_complete_data.get(letter, {})

        # Calculate the total number of completed words for this letter
        completed_word_count = sum(len(words)
                                   for words in letter_complete_data.values())

        # Get total word count for this letter from the words collection
        words_ref = db.collection('words').document(letter)
        words_data = words_ref.get().to_dict()
        total_word_count = words_data.get('wordCount', 0)

        # Check if all words are completed
        if completed_word_count == total_word_count and total_word_count > 0:
            # Update badges map in Firestore
            user_badges_ref = db.collection('users').document(user_id)
            user_badges_ref.update({f'badges.{letter}': True})

        # Add data to results
        results[letter] = {
            "completed_word_count": completed_word_count,
            "total_word_count": total_word_count,
            "badge_updated": completed_word_count == total_word_count
        }

    print("Badges: ", results)


def getHistory(user_id):
    history_data = []

    try:
        # Reference to user's history in Firestore
        db = get_firestore_client()
        user_history_ref = db.collection('users').document(
            user_id).collection('history')

        # Fetch history documents
        docs = user_history_ref.stream()

        # Loop through documents and format data
        for doc in docs:
            history_record = doc.to_dict()
            history_data.append(history_record)

        print("records: ", history_record)

    except Exception as e:
        print(f"Error fetching quiz history for user {user_id}: {e}")

    return history_data
