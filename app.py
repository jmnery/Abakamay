
from requests.exceptions import HTTPError
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask import request
from flask import render_template, session
from datetime import datetime
from flask import jsonify
from firebase_admin import firestore
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash, make_response, Response
import firebase_admin
import pyrebase
from firebase_admin import auth
from firebase_admin.exceptions import FirebaseError
import os
import json
import random
import slr
from databaseServices import addBadgesToComplete, addToHistory, get_all_letters, get_all_words, get_user_data_by_id, get_user_progress, get_words_by_letter, getHistory, initialize_firebase, add_user_to_db, get_all_users, markAsComplete, upload_file_to_storage, add_learned_word
from camera import generate_frames
from socketioInstance import socketio
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)  # Only this instance should exist
socketio.init_app(app)
# Set the secret key for session management
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')

# Initialize Firebase
credentials_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
firebase_url = os.getenv('FIREBASE_DATABASE_URL',
                         'https://abakada-flask-default-rtdb.firebaseio.com/')
storage_bucket = os.getenv('FIREBASE_STORAGE_BUCKET',
                           'abakada-flask.appspot.com')
config = {
    "apiKey": os.getenv('FIREBASE_API_KEY'),
    "authDomain": os.getenv('FIREBASE_AUTH_DOMAIN'),
    "databaseURL": firebase_url,
    "projectId": os.getenv('FIREBASE_PROJECT_ID'),
    "storageBucket": storage_bucket,
    "messagingSenderId": os.getenv('FIREBASE_MESSAGING_SENDER_ID'),
    "appId": os.getenv('FIREBASE_APP_ID')
}
initialize_firebase(credentials_path, firebase_url, storage_bucket)

# Firestore client initialization
db = firestore.client()
firebase = pyrebase.initialize_app(config)
firebaseAuth = firebase.auth()


@app.before_request
def check_authentication():
    public_routes = ['login', 'signup', 'forgotPassword']
    if request.endpoint in public_routes and 'user_id' in session:
        return redirect(url_for('main'))

    if request.endpoint not in public_routes and 'user_id' not in session:
        return redirect(url_for('login'))


@app.after_request
def add_cache_control(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    return response


@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('learn'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            user = firebaseAuth.sign_in_with_email_and_password(
                email, password)
            user_id = user['localId']
            # Fetch user data (including firstName) from your database
            user_data = get_user_data_by_id(user_id)

            # Clear the session before setting new session variables for the new user
            session.clear()  # This removes all session data

            # Store firstName in the session
            session['user_id'] = user_id
            session['first_name'] = user_data.get('firstName', '')
            session['avatar'] = user_data.get('avatar', '')
            session['new_user'] = False
            return redirect(url_for('learn'))
        except (HTTPError, FirebaseError) as e:
            # Capture error messages from Firebase
            if isinstance(e, HTTPError):
                error_message = f'HTTP error occurred: {str(e)}'
                print("HTTPError:", error_message)
                flash('Invalid login credentials. Please check your email and password.')
            elif isinstance(e, FirebaseError):
                error_message = f'Firebase error occurred: {str(e)}'
                print("FirebaseError:", error_message)
                flash('Invalid login credentials. Please try again.')
            else:
                error_message = f'An unexpected error occurred: {str(e)}'
                print("Unexpected error:", error_message)
                flash('An error occurred. Please try again.')
    return render_template('login.html')


@ app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        first_name = request.form['firstName']
        last_name = request.form['lastName']
        email = request.form['email']
        age = request.form['age']
        password = request.form['password']
        birthday = request.form['birthday']
        avatar = request.form['avatar']

        try:
            if len(password) < 6:
                raise ValueError(
                    "Password must be at least 6 characters long.")

            user = auth.create_user(
                email=email,
                password=password,
                display_name=f"{first_name} {last_name}",
            )
            add_user_to_db(user.uid, first_name,
                           last_name, email, age, birthday, avatar)

            # Clear the session before setting new session variables for the new user
            session.clear()  # This removes all session data

            session['user_id'] = user.uid
            session['first_name'] = first_name
            session['avatar'] = avatar
            session['new_user'] = True
            return redirect(url_for('learn', show_summary_modal=True))
        except ValueError as ve:
            flash(f'Error: {ve}')
        except FirebaseError as e:
            flash(f'Error creating user: {e}')
    return render_template('signup.html')


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        # Safely retrieve form data with defaults
        letter = request.form.get('letter', '').strip()
        syllable = request.form.get('syllable', '').strip()
        # Use default '' if 'type' is missing
        letter_type = request.form.get('type', '').strip()
        value = request.form.get('value', '').strip()
        file = request.files.get('file')  # Safely retrieve the uploaded file

        # Ensure all required fields are present
        if not letter or not syllable or not value or not file:
            return "Missing required fields", 400

        # Call the function to upload the file and save data
        result = upload_file_to_storage(
            file, letter, syllable, letter_type, value)

        if result['status'] == 'success':
            return redirect(url_for('admin'))
        else:
            return f"Error: {result['message']}", 500

    return render_template('admin.html')


@app.route('/main')
def main():
    return render_template('tabs/learn.html')


@app.route('/learn')
def learn():

    # Check if the user is new and hasn't seen the tour yet
    new_user = session.get('new_user')

    if new_user:
        # Check if the 'learn_tour_shown' key is in session, and if not, mark it as False
        if 'learn_tour_shown' not in session:
            session['learn_tour_shown'] = False

        # Show tour if it hasn't been shown yet
        # True if tour hasn't been shown yet
        show_tour = not session['learn_tour_shown']

        # Mark tour as shown for future visits
        if show_tour:
            session['learn_tour_shown'] = True  # Mark as shown

    else:
        show_tour = False  # If not a new user, do not show the tour

    show_summary_modal = request.args.get(
        'show_summary_modal', 'false').lower() == 'true'
    # Fetch the user_id from session or however you store the user's login information
    user_id = session.get('user_id')
    user_fName = session.get('first_name')
    avatar = session.get('avatar')

    letters_ref = db.collection('words')
    docs = letters_ref.stream()

    vowels = []
    consonants = []
    progress_data = {}

    learned_data = {}

    # Fetch the learned data for the user in one go
    user_ref = db.collection('users').document(user_id)
    user_doc = user_ref.get()

    if user_doc.exists:
        learned_data = user_doc.to_dict().get('learned', {})

    # Process each letter
    for doc in docs:
        letter = doc.id
        letter_data = doc.to_dict()
        letter_type = letter_data.get('type', '')

        if letter_type == 'vowel':
            vowels.append(letter)
        elif letter_type == 'consonant':
            consonants.append(letter)

        # Get the total words using wordCount and learned words directly from learned_data
        total_words = letter_data.get('wordCount', 0)
        # learned_words = len(learned_data.get(letter, {}).get('syllable', []))
        learned_words = learned_data.get(letter, {}).get('wordCount', 0)

        # Store progress data for each letter
        progress_data[letter] = {
            'total_words': total_words,
            'learned_words': learned_words
        }

    # Combine both for displaying 'all' or filter as needed
    all_letters = vowels + consonants

    # Define the custom order
    custom_order = ['A', 'B', 'K', 'D', 'E', 'G', 'H', 'I', 'L',
                    'M', 'N', 'Ng', 'O', 'P', 'R', 'S', 'T', 'U', 'W', 'Y']

    # Sort all_letters based on the custom order
    all_letters.sort(key=lambda letter: custom_order.index(letter))
    return render_template('tabs/learn.html', letters=all_letters, vowels=vowels, consonants=consonants, progress_data=progress_data, firstName=user_fName, avatar=avatar, show_summary_modal=show_summary_modal, show_tour=show_tour)


@app.route('/learnOptions/<letter>')
def learnOptions(letter):
    # Check if the user is new and hasn't seen the tour yet
    new_user = session.get('new_user')

    if new_user:
        # Check if the key is in session, and if not, mark it as False
        if 'learn_options_tour_shown' not in session:
            session['learn_options_tour_shown'] = False

        # Show tour if it hasn't been shown yet
        # True if tour hasn't been shown yet
        show_tour = not session['learn_options_tour_shown']

        # Mark tour as shown for future visits
        if show_tour:
            session['learn_options_tour_shown'] = True  # Mark as shown

    else:
        show_tour = False  # If not a new user, do not show the tour
    avatar = session.get('avatar')
    return render_template('tabs/learnOptions.html', avatar=avatar, letter=letter, show_tour=show_tour)


@app.route('/lettersSyllables/<letter>')
def lettersSyllables(letter):
    # Check if the user is new and hasn't seen the tour yet
    new_user = session.get('new_user')

    if new_user:
        # Check if the key is in session, and if not, mark it as False
        if 'lettersSyllables_tour_shown' not in session:
            session['lettersSyllables_tour_shown'] = False

        # Show tour if it hasn't been shown yet
        # True if tour hasn't been shown yet
        show_tour = not session['lettersSyllables_tour_shown']

        # Mark tour as shown for future visits
        if show_tour:
            session['lettersSyllables_tour_shown'] = True  # Mark as shown

    else:
        show_tour = False  # If not a new user, do not show the tour

    user_id = session.get('user_id')
    avatar = session.get('avatar')
    # List of available letters
    letters = ['A', 'B', 'K', 'D', 'E', 'G', 'H', 'I', 'L',
               'M', 'N', 'Ng', 'O', 'P', 'R', 'S', 'T', 'U', 'W', 'Y']

    # Find the index of the current letter
    letter_index = letters.index(letter)

    # Get the previous and next letters
    previous_letter = letters[letter_index -
                              1] if letter_index > 0 else letters[-1]
    next_letter = letters[letter_index +
                          1] if letter_index < len(letters) - 1 else letters[0]
    return render_template('tabs/lettersSyllables.html', avatar=avatar, letter=letter,  previous_letter=previous_letter, next_letter=next_letter,
                           letter_options=letters, user_id=user_id, firebase_config=config, show_tour=show_tour)


@app.route('/m_learn/<letter>')
def m_learn(letter):

    # Check if the user is new and hasn't seen the tour yet
    new_user = session.get('new_user')

    if new_user:
        # Check if the key is in session, and if not, mark it as False
        if 'm_learn_tour_shown' not in session:
            session['m_learn_tour_shown'] = False

        # Show tour if it hasn't been shown yet
        # True if tour hasn't been shown yet
        show_tour = not session['m_learn_tour_shown']

        # Mark tour as shown for future visits
        if show_tour:
            session['m_learn_tour_shown'] = True  # Mark as shown

    else:
        show_tour = False  # If not a new user, do not show the tour

    # List of available letters
    letters = ['A', 'B', 'K', 'D', 'E', 'G', 'H', 'I', 'L',
               'M', 'N', 'Ng', 'O', 'P', 'R', 'S', 'T', 'U', 'W', 'Y']

    # Find the index of the current letter
    letter_index = letters.index(letter)

    # Get the previous and next letters
    previous_letter = letters[letter_index -
                              1] if letter_index > 0 else letters[-1]
    next_letter = letters[letter_index +
                          1] if letter_index < len(letters) - 1 else letters[0]

    # Fetch data from the 'words' collection
    letter_ref = db.collection('words').document(letter)
    letter_doc = letter_ref.get()

    if not letter_doc.exists:
        # If the document doesn't exist, return an empty template
        return render_template('tabs/m_learn.html', letter=letter, syllable_data={}, learned_words=set(), show_tour=show_tour)

    letter_data = letter_doc.to_dict()
    syllables = letter_data.get('syllables', {})

    # Fetch the current user's learned words
    # Assuming you have user authentication and session management
    user_id = session.get('user_id')
    avatar = session.get('avatar')
    user_ref = db.collection('users').document(user_id)
    user_doc = user_ref.get()

    learned_words = set()
    completed_words = set()  # Initialize completed words set

    if user_doc.exists:
        learned_data = user_doc.to_dict()
        completed_data = user_doc.to_dict()

        # Check if learned words for the specific letter exist
        learned_letter_data = learned_data.get('learned', {}).get(letter, {})

        # Extract syllable arrays and combine them into the learned words set
        for syllable, words in learned_letter_data.items():
            if isinstance(words, list):  # Ensure that it's a list
                learned_words.update(words)  # Add learned words to the set

        completed_letter_data = completed_data.get(
            'complete', {}).get(letter, {})

        for syllable, words in completed_letter_data.items():
            if isinstance(words, list):
                completed_words.update(words)

    sorted_syllables = dict(sorted(syllables.items()))
    syllable_data = {}
    for syllable, words_list in sorted_syllables.items():
        # Remove any empty entries and structure data
        words = [
            {
                'text': word.get('text', ''),
                'extension': word.get('extension', ''),
                'value': word.get('value', ''),
                # Add learned status
                'learned': word.get('text') in learned_words,
                # Add completed status
                'completed': word.get('text') in completed_words
            }
            for word in words_list if word
        ]
        syllable_data[syllable] = words

    print('syllable: ', syllable_data)
    return render_template('tabs/m_learn.html', letter=letter, syllable_data=syllable_data, avatar=avatar, letter_options=letters, previous_letter=previous_letter, next_letter=next_letter, show_tour=show_tour)


@app.route('/mark_as_learned', methods=['POST'])
def mark_as_learned():
    user_id = session.get('user_id')

    # Check if user_id exists
    if not user_id:
        return jsonify({"message": "User not logged in."}), 401

    data = request.get_json()
    letter = data.get('letter')
    syllable = data.get('syllable')
    word = data.get('word')

    print(f"data: {letter}: {syllable}: {word}")

    # Call the function to add the learned word to Firestore
    try:
        add_learned_word(user_id, letter, syllable, word)
        return jsonify({"message": "Word marked as learned!"}), 200
    except Exception as e:
        return jsonify({"message": "Error marking word as learned.", "error": str(e)}), 500


@app.route('/quiz')
def quiz():
    # Check if the user is new and hasn't seen the tour yet
    new_user = session.get('new_user')

    if new_user:
        # Check if the  key is in session, and if not, mark it as False
        if 'quiz_tour_shown' not in session:
            session['quiz_tour_shown'] = False

        # Show tour if it hasn't been shown yet
        # True if tour hasn't been shown yet
        show_tour = not session['quiz_tour_shown']

        # Mark tour as shown for future visits
        if show_tour:
            session['quiz_tour_shown'] = True  # Mark as shown

    else:
        show_tour = False  # If not a new user, do not show the tour
    avatar = session.get('avatar')
    return render_template('tabs/quiz.html', avatar=avatar, show_tour=show_tour)


@app.route('/m_quiz/<int:index>', methods=['GET'])
@app.route('/m_quiz', methods=['GET'])
def m_quiz(index=None):
    # Check if the user is new and hasn't seen the tour yet
    new_user = session.get('new_user')

    if new_user:
        # Check if the key is in session, and if not, mark it as False
        if 'm_quiz_tour_shown' not in session:
            session['m_quiz_tour_shown'] = False

        # Show tour if it hasn't been shown yet
        # True if tour hasn't been shown yet
        show_tour = not session['m_quiz_tour_shown']

        # Mark tour as shown for future visits
        if show_tour:
            session['m_quiz_tour_shown'] = True  # Mark as shown

    else:
        show_tour = False  # If not a new user, do not show the tour

    user_id = session.get('user_id')
    avatar = session.get('avatar')

    if not user_id:
        return redirect(url_for('login'))

    # Retrieve quiz words from the session
    quiz_words = session.get('quiz_words')

    if not quiz_words:
        # print('No words available for the quiz. Please start a new quiz.')
        return redirect(url_for('quiz'))

    # Use session to store the current index if not provided
    if index is None:
        index = session.get('currentIndex', 0)
    else:
        session['currentIndex'] = index  # Update the session index

    # Ensure the index is valid
    if index < 0 or index >= len(quiz_words):
        # print('Invalid word index selected.')
        return redirect(url_for('quiz'))

    selected_word = quiz_words[index]
    # print("quiz_words: ", quiz_words)
    return render_template(
        'tabs/m_quiz.html',
        word=selected_word,
        currentIndex=index,
        totalWords=len(quiz_words),
        all_words=json.dumps(quiz_words),  # Pass all words as JSON
        quizWords=json.dumps(quiz_words),
        avatar=avatar, show_tour=show_tour
    )


@app.route('/retakeQuiz', methods=['POST'])
def retakeQuiz():
    # Retrieve quiz_words from the form data
    quiz_words = request.form.get('quiz_words')

    # Convert JSON string to a dictionary or list, if necessary
    if quiz_words:
        import json
        quiz_words = json.loads(quiz_words)

    # Store in session and reset currentIndex
    session['quiz_words'] = quiz_words
    session['currentIndex'] = 0

    # Redirect to the quiz route
    return redirect(url_for('m_quiz', index=0))


@app.route('/randomizeAll')
def randomizeAll():
    user_id = session.get('user_id')

    all_words = get_all_words()
    completed_words = get_user_progress(user_id)

    available_words = [
        word for word in all_words if word['text'] not in completed_words]

    # Get 10 random words or fewer if not enough available
    quiz_words = random.sample(available_words, 10) if len(
        available_words) >= 10 else available_words

    # Store quiz words in the session
    session['quiz_words'] = quiz_words
    session['currentIndex'] = 0  # Reset current index to the first word

    print("Quiz Words: ", quiz_words)
    print("Completed: ", completed_words)
    # Redirect to m_quiz with index 0
    return redirect(url_for('m_quiz', index=0))


@app.route('/randomizeCategory/<letter>')  # Added mode parameter
def randomizeCategory(letter):
    user_id = session.get('user_id')

    completed_words = get_user_progress(user_id)

    if request.args.get('action') == 'proceed':
        # Retrieve all words for the specific letter
        all_words = get_words_by_letter(letter)

        # Filter words to only those that have not been completed
        available_words = [
            word for word in all_words if word['text'] not in completed_words]

        # Shuffle the available words and take all of them
        random.shuffle(available_words)
        quiz_words = available_words  # Use all remaining words (randomized)
    elif request.args.get('action') == 'retry':
        # Retrieve all words for the specific letter
        all_words = get_words_by_letter(letter)
        # Get up to 10 random uncompleted words from the available words
        quiz_words = random.sample(all_words, 10) if len(
            all_words) >= 10 else all_words
    elif request.args.get('action') == 'add':
        all_words = get_all_words()  # Get all words from Firestore
        # Filter words by letter and those that have not been completed
        available_words = [
            word for word in all_words if word['text'] not in completed_words and letter in word['text'].upper()]
        # First, get up to 10 uncompleted words from the available words
        quiz_words = random.sample(available_words, 10) if len(
            available_words) >= 10 else available_words

        # Then, if less than 10, fill in from other letters
        if len(quiz_words) < 10:
            additional_words = []  # Initialize list for additional words

            # Filter available words to find those from other letters
            for word in all_words:
                if word['text'] not in completed_words and letter not in word['text'].upper():
                    additional_words.append(word)

            # Randomly select the required number of additional words
            additional_choices = random.sample(additional_words, 10 - len(quiz_words)) if len(
                additional_words) >= (10 - len(quiz_words)) else additional_words

            # Add additional words to make a total of 10
            quiz_words.extend(additional_choices)

    # Store quiz words in the session
    session['quiz_words'] = quiz_words
    session['currentIndex'] = 0  # Reset current index to the first word

    # Redirect to m_quiz with index 0
    return redirect(url_for('m_quiz', index=0))


@app.route('/picker')
def picker():

    # Check if the user is new and hasn't seen the tour yet
    new_user = session.get('new_user')

    if new_user:
        # Check if the key is in session, and if not, mark it as False
        if 'picker_tour_shown' not in session:
            session['picker_tour_shown'] = False

        # Show tour if it hasn't been shown yet
        # True if tour hasn't been shown yet
        show_tour = not session['picker_tour_shown']

        # Mark tour as shown for future visits
        if show_tour:
            session['picker_tour_shown'] = True  # Mark as shown

    else:
        show_tour = False  # If not a new user, do not show the tour

    # Fetch the user_id from session or however you store the user's login information
    user_id = session.get('user_id')  # Adjust this based on your login system
    avatar = session.get('avatar')

    letters_ref = db.collection('words')
    docs = letters_ref.stream()

    vowels = []
    consonants = []
    all_letters = []  # List to store letter and total words as dictionaries

    # Process each letter
    for doc in docs:
        letter = doc.id
        letter_data = doc.to_dict()
        letter_type = letter_data.get('type', '')

        # Calculate the total words from syllables map
        syllables = letter_data.get('syllables', {})
        total_words = sum(len(words)
                          for words in syllables.values() if isinstance(words, list))

        # Create a dictionary for each letter
        letter_info = {
            'letter': letter,
            'totalWords': total_words
        }

        all_letters.append(letter_info)  # Append to the all_letters list

        # Classify letters into vowels and consonants
        if letter_type == 'vowel':
            vowels.append(letter_info)  # Append letter info to vowels
        elif letter_type == 'consonant':
            consonants.append(letter_info)  # Append letter info to consonants

    # Define the custom order
    custom_order = ['A', 'B', 'K', 'D', 'E', 'G', 'H', 'I', 'L',
                    'M', 'N', 'Ng', 'O', 'P', 'R', 'S', 'T', 'U', 'W', 'Y']

    # Sort all_letters based on the custom order
    all_letters.sort(key=lambda x: custom_order.index(x['letter']))
    return render_template('tabs/picker.html', all_letters=all_letters, vowels=vowels, consonants=consonants, userId=user_id, avatar=avatar, show_tour=show_tour)


@app.route('/collection')
def collection():
    # Check if the user is new and hasn't seen the tour yet
    new_user = session.get('new_user')

    if new_user:
        # Check if the key is in session, and if not, mark it as False
        if 'collection_tour_shown' not in session:
            session['collection_tour_shown'] = False

        # Show tour if it hasn't been shown yet
        # True if tour hasn't been shown yet
        show_tour = not session['collection_tour_shown']

        # Mark tour as shown for future visits
        if show_tour:
            session['collection_tour_shown'] = True  # Mark as shown

    else:
        show_tour = False  # If not a new user, do not show the tour

    user_id = session.get('user_id')  # Get the current user's ID
    avatar = session.get('avatar')

    if not user_id:
        return redirect(url_for('login'))

    # Fetch all the letters from the 'words' collection
    words_ref = db.collection('words')
    words_docs = words_ref.stream()

    # Fetch the current user's learned and completed words
    user_ref = db.collection('users').document(user_id)
    user_doc = user_ref.get()

    learned_words = set()
    completed_words = set()

    if user_doc.exists:
        user_data = user_doc.to_dict()

       # Fetch learned words
        learned_data = user_data.get('learned', {})
        for letter, syllables in learned_data.items():
            for syllable, words in syllables.items():
                if isinstance(words, list):
                    for word in words:
                        # Store as a tuple (letter, syllable, word)
                        learned_words.add((letter, syllable, word))

        # Fetch completed words
        completed_data = user_data.get('complete', {})
        for letter, syllables in completed_data.items():
            for syllable, words in syllables.items():
                if isinstance(words, list):
                    for word in words:
                        # Store as a tuple (letter, syllable, word)
                        completed_words.add((letter, syllable, word))

    # Structure the data for all letters and their syllables
    syllable_data = {}
    for letter_doc in words_docs:
        letter_data = letter_doc.to_dict()
        letter = letter_doc.id
        syllables = letter_data.get('syllables', {})

        # Organize the words in each syllable and check if they're learned or completed
        for syllable, words_list in syllables.items():
            words = [
                {
                    'text': word.get('text', ''),
                    'extension': word.get('extension', ''),
                    'value': word.get('value', ''),
                    'learned': (letter, syllable, word.get('text', '')) in learned_words,
                    'completed': (letter, syllable, word.get('text', '')) in completed_words,
                    'letter': letter
                }
                for word in words_list if word
            ]
            if syllable not in syllable_data:
                syllable_data[syllable] = words
            else:
                syllable_data[syllable].extend(words)

    print("syllable_data: ", syllable_data)
    # print("syllable data: ", syllable_data)
    return render_template('tabs/collection.html', syllable_data=syllable_data, avatar=avatar, show_tour=show_tour)

# POST route to handle quiz submission


@app.route('/results', methods=['POST', 'GET'])
def results():
    avatar = session.get('avatar')
    if request.method == 'POST':
        # Get the user answers, quiz words, quizId, and timestamp from the request body
        data = request.get_json()
        print("data: ", data)
        user_answers = data.get('userAnswers', [])
        quiz_words = data.get('quizWords', [])
        user_id = session.get('user_id')
        quiz_id = data.get('quizId', None)
        timestamp = data.get('timestamp', "")
        if timestamp:
            try:
                date_time = datetime.fromtimestamp(timestamp / 1000)
                formatted_timestamp = {
                    # Format just the date
                    "date": date_time.strftime('%B %d, %Y'),
                    # Format just the time
                    "time": date_time.strftime('%I:%M %p')
                }
            except Exception as e:
                print(f"Error in timestamp conversion: {e}")
                formatted_timestamp = {"date": "Invalid", "time": "Invalid"}
        else:
            formatted_timestamp = {"date": "No date", "time": "No time"}
        # Process the results (e.g., grade the quiz)
        correct_answers = 0
        results_with_correctness = []  # List to hold user answers with correctness
        completed_data = {}  # To track completed words by letter

        for i, word in enumerate(quiz_words):
            correct_answer = word['value'].strip().lower()
            user_answer = user_answers[i].strip().lower()
            is_correct = correct_answer == user_answer

            # Increment the correct answer count if the answer is correct
            if is_correct:
                correct_answers += 1

                # Prepare completed data
                letter = word['letter']  # Get the letter for the current word
                # Get the syllable for the current word
                syllable = word['syllable']
                word_text = word['text']  # The word itself

                # Initialize completed_data for this letter if it doesn't exist
                if letter not in completed_data:
                    completed_data[letter] = {
                        'wordCount': 0,  # Initialize word count
                    }

                # Initialize syllable data for this letter if it doesn't exist
                if syllable not in completed_data[letter]:
                    # Initialize as a list for syllables
                    completed_data[letter][syllable] = []

                # Append the word to the syllable's list and increment the word count
                completed_data[letter][syllable].append(word_text)
                # Increment total word count for the letter
                completed_data[letter]['wordCount'] += 1

            # Append the user answer and correctness to the results list
            results_with_correctness.append({
                "user_answer": user_answers[i],
                "correct": is_correct,
                "word": word  # Include the word object for rendering
            })

        total_questions = len(quiz_words)
        score = (correct_answers / total_questions) * 100

        # Prepare data to pass to the results page
        result_data = {
            "correct_answers": correct_answers,
            "total_questions": total_questions,
            "score": score,
            "user_answers": results_with_correctness,
            "quiz_words": quiz_words,
            "timestamp": formatted_timestamp,
            "quiz_ID": quiz_id
        }

        # Store the result data in the session
        session['result_data'] = result_data

        print("Completed_data :", completed_data)
        # Mark correct words as complete and add to history
        if user_id:
            markAsComplete(user_id, completed_data)
            addBadgesToComplete(user_id, results_with_correctness)
            addToHistory(user_id, quiz_id, timestamp, score,
                         correct_answers, total_questions, results_with_correctness)

        # Redirect to the GET route to display the results
        return redirect(url_for('results', avatar=avatar))

    elif request.method == 'GET':
        # Retrieve the result data from the session
        result_data = session.get('result_data', {})

        # Render the results page with the result data
        return render_template('results.html', result_data=result_data, avatar=avatar)


@app.route('/history')
def history():
    user_id = session.get('user_id')  # Replace with actual user ID logic
    avatar = session.get('avatar')
    history_records = getHistory(user_id)

    # Format the timestamps for each record
    for record in history_records:
        if 'timestamp' in record:
            timestamp = record['timestamp']
            formatted_date = datetime.fromtimestamp(
                timestamp / 1000).strftime('%B %d, %Y')
            formatted_time = datetime.fromtimestamp(
                timestamp / 1000).strftime('%I:%M %p')
            record['timestamp'] = {
                'date': formatted_date,
                'time': formatted_time,
                'original': timestamp  # Keep the original timestamp for sorting
            }

    # Sort history records by the original timestamp in descending order
    sorted_history_records = sorted(
        history_records, key=lambda x: x['timestamp']['original'], reverse=True)

    print("Sorted history records:", sorted_history_records)

    return render_template('history.html', history_data=sorted_history_records, avatar=avatar)


@app.route('/profile')
def profile():
    # Check if the user is new and hasn't seen the tour yet
    new_user = session.get('new_user')

    if new_user:
        # Check if the key is in session, and if not, mark it as False
        if 'profile_tour_shown' not in session:
            session['profile_tour_shown'] = False

        # Show tour if it hasn't been shown yet
        # True if tour hasn't been shown yet
        show_tour = not session['profile_tour_shown']

        # Mark tour as shown for future visits
        if show_tour:
            session['profile_tour_shown'] = True  # Mark as shown

    else:
        show_tour = False  # If not a new user, do not show the tour

    # Fetch the user document (replace 'user_id' with the actual user ID or retrieve dynamically)
    user_id = session.get('user_id')
    user_doc = db.collection('users').document(user_id).get()
    avatar = session.get('avatar')

    if user_doc.exists:
        user_data = user_doc.to_dict()
        # Combine first and last name
        full_name = f"{user_data.get('firstName', '')} {user_data.get('lastName', '')}"

        # Assuming user_data is your dictionary containing the user's data
        raw_birthday = user_data.get('birthday', '')

        # Initialize formatted_birthday with a default value
        formatted_birthday = "Unknown Date"
        try:
            # Check if raw_birthday is a non-empty string
            if isinstance(raw_birthday, str) and raw_birthday:
                # Parse the string into a datetime object
                birthday_datetime = datetime.strptime(raw_birthday, "%Y-%m-%d")
                # Format the datetime object to the desired string format
                formatted_birthday = birthday_datetime.strftime("%B %d, %Y")
        except ValueError:
            formatted_birthday = "Unknown Date"  # Handle the case where parsing fails

        badges = user_data.get('badges', {})

        # Pass the formatted data to the template
        return render_template('tabs/profile.html', full_name=full_name,
                               email=user_data.get('email', ''),
                               user_id=user_id,
                               age=user_data.get('age', ''),
                               birthday=formatted_birthday,
                               avatar=avatar, badges=badges, show_tour=show_tour)
    else:
        return "User not found", 404


@app.route('/api/user/<user_id>')
def get_user_data(user_id):
    user_data = db.collection('users').document(
        user_id).get().to_dict() if user_id else {}
    # print("user_data: ", user_data)
    return jsonify(user_data)


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    resp = make_response(redirect(url_for('login')))
    resp.headers['Cache-Control'] = 'no-store'
    resp.headers['Pragma'] = 'no-cache'
    return resp


@app.route('/help/learn')
def learn_help():
    return render_template('help/learnHelp.html')


@app.route('/data')
def get_data():
    users = get_all_users()
    return jsonify(users)


@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


def process_frame(image):
    global recognized_letter
    recognized_letter = slr.process_frame(
        image)  # Update the recognized letter
    return recognized_letter


@app.route('/forgotPassword', methods=['GET', 'POST'])
def forgotPassword():
    if request.method == 'POST':
        email = request.form['email']
        try:
            # Send password reset email
            firebaseAuth.send_password_reset_email(email)
            flash('Password reset email sent. Please check your inbox.', 'success')
            # Redirect to login page after sending the email
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Error sending password reset email: {str(e)}', 'danger')
    return render_template('forgotPassword.html')


@socketio.on('connect')
def handle_connect():
    print("Client connected")


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
