from flask import request
from flask import render_template, session
from datetime import datetime
from flask import jsonify
from firebase_admin import firestore
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash, make_response, Response
import firebase_admin
from firebase_admin import auth
from firebase_admin.exceptions import FirebaseError
import os
import json
import random
from databaseServices import get_all_letters, get_all_words, get_user_data, get_user_progress, get_words_by_letter, initialize_firebase, add_user_to_db, get_all_users, upload_file_to_storage, add_learned_word
from camera import generate_frames

app = Flask(__name__)  # Only this instance should exist

# Set the secret key for session management
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')

# Initialize Firebase
credentials_path = r'C:\Users\Daniel\Desktop\Flask Project\Abakada\abakada_flask\services\credentials.json'
firebase_url = 'https://abakada-flask-default-rtdb.firebaseio.com/'
storage_bucket = 'abakada-flask.appspot.com'
initialize_firebase(credentials_path, firebase_url, storage_bucket)

# Firestore client initialization
db = firestore.client()


@app.before_request
def check_authentication():
    public_routes = ['login', 'signup']
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
            user = auth.get_user_by_email(email)
            session['user_id'] = user.uid
            return redirect(url_for('learn'))
        except FirebaseError as e:
            flash(f'Invalid login credentials: {e}')
    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        first_name = request.form['firstName']
        last_name = request.form['lastName']
        email = request.form['email']
        age = request.form['age']
        password = request.form['password']

        try:
            if len(password) < 6:
                raise ValueError(
                    "Password must be at least 6 characters long.")

            user = auth.create_user(
                email=email,
                password=password,
                display_name=f"{first_name} {last_name}",
            )
            add_user_to_db(user.uid, first_name, last_name, email, age)
            session['user_id'] = user.uid
            return redirect(url_for('learn'))
        except ValueError as ve:
            flash(f'Error: {ve}')
        except FirebaseError as e:
            flash(f'Error creating user: {e}')
    return render_template('signup.html')


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        letter = request.form['letter']
        syllable = request.form['syllable']
        letter_type = request.form['type']
        words = request.form['words'].split(',')
        value = request.form['value']
        file = request.files['file']  # The uploaded file from the form

        # Call the function to upload file and save data
        # Pass all the necessary data
        result = upload_file_to_storage(
            file, letter,  syllable, letter_type, words, value)

        if result['status'] == 'success':
            flash(
                ('success', f"File uploaded successfully! URL: {result['file_url']}"))
        else:
            flash(('error', result['message']))

        return redirect(url_for('admin'))

    return render_template('admin.html')


@app.route('/main')
def main():
    return render_template('tabs/learn.html')


@app.route('/learn')
def learn():
    # Fetch the user_id from session or however you store the user's login information
    user_id = session.get('user_id')  # Adjust this based on your login system

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
    return render_template('tabs/learn.html', letters=all_letters, vowels=vowels, consonants=consonants, progress_data=progress_data)


@app.route('/m_learn/<letter>')
def m_learn(letter):
    # Fetch data from the 'words' collection
    letter_ref = db.collection('words').document(letter)
    letter_doc = letter_ref.get()

    if not letter_doc.exists:
        # If the document doesn't exist, return an empty template
        return render_template('tabs/m_learn.html', letter=letter, syllable_data={}, learned_words=set())

    letter_data = letter_doc.to_dict()
    syllables = letter_data.get('syllables', {})

    # Fetch the current user's learned words
    # Assuming you have user authentication and session management
    user_id = session.get('user_id')
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
    return render_template('tabs/m_learn.html', letter=letter, syllable_data=syllable_data)


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
    return render_template('tabs/quiz.html')


@app.route('/m_quiz/<int:index>', methods=['GET'])
@app.route('/m_quiz', methods=['GET'])
def m_quiz(index=None):
    user_id = session.get('user_id')

    if not user_id:
        return redirect(url_for('login'))

    # Retrieve quiz words from the session
    quiz_words = session.get('quiz_words')

    if not quiz_words:
        flash('No words available for the quiz. Please start a new quiz.')
        return redirect(url_for('quiz'))

    # Use session to store the current index if not provided
    if index is None:
        index = session.get('currentIndex', 0)
    else:
        session['currentIndex'] = index  # Update the session index

    # Ensure the index is valid
    if index < 0 or index >= len(quiz_words):
        flash('Invalid word index selected.')
        return redirect(url_for('quiz'))

    selected_word = quiz_words[index]
    return render_template(
        'tabs/m_quiz.html',
        word=selected_word,
        currentIndex=index,
        totalWords=len(quiz_words),
        all_words=json.dumps(quiz_words),  # Pass all words as JSON
        quizWords=json.dumps(quiz_words)
    )


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

    print("Hehe: ", quiz_words)
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

        # Get up to 10 random uncompleted words from the available words
        quiz_words = random.sample(available_words, 10) if len(
            available_words) >= 10 else available_words
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
    # Fetch the user_id from session or however you store the user's login information
    user_id = session.get('user_id')  # Adjust this based on your login system

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

        # Get the total words using wordCount from letter_data
        total_words = letter_data.get('wordCount', 0)

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
    return render_template('tabs/picker.html', all_letters=all_letters, vowels=vowels, consonants=consonants, userId=user_id)


@app.route('/collection')
def collection():
    user_id = session.get('user_id')  # Get the current user's ID

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
                    learned_words.update(words)

        # Fetch completed words
        completed_data = user_data.get('complete', {})
        for letter, syllables in completed_data.items():
            for syllable, words in syllables.items():
                if isinstance(words, list):
                    completed_words.update(words)

    # Structure the data for all letters and their syllables
    syllable_data = {}
    for letter_doc in words_docs:
        letter_data = letter_doc.to_dict()
        syllables = letter_data.get('syllables', {})

        # Organize the words in each syllable and check if they're learned or completed
        for syllable, words_list in syllables.items():
            words = [
                {
                    'text': word.get('text', ''),
                    'extension': word.get('extension', ''),
                    'value': word.get('value', ''),
                    'learned': word.get('text') in learned_words,
                    'completed': word.get('text') in completed_words
                }
                for word in words_list if word
            ]
            if syllable not in syllable_data:
                syllable_data[syllable] = words
            else:
                syllable_data[syllable].extend(words)

    # Pass the data to the template
    return render_template('tabs/collection.html', syllable_data=syllable_data)


# Initialize Firestore if not already initialized
# firebase_admin.initialize_app()
db = firestore.client()


@app.route('/profile')
def profile():
    # Fetch the user document (replace 'user_id' with the actual user ID or retrieve dynamically)
    user_id = session.get('user_id')
    user_doc = db.collection('users').document(user_id).get()

    if user_doc.exists:
        user_data = user_doc.to_dict()
        # Combine first and last name
        full_name = f"{user_data.get('firstName', '')} {user_data.get('lastName', '')}"

        # Format the birthday
        raw_birthday = user_data.get('birthday', '')
        try:
            # Convert Firestore timestamp to a Python datetime object
            if isinstance(raw_birthday, datetime):
                formatted_birthday = raw_birthday.strftime("%B %d, %Y")
            else:
                formatted_birthday = "Unknown Date"
        except ValueError:
            formatted_birthday = "Unknown Date"  # Handle the case where parsing fails

        # Pass the formatted data to the template
        return render_template('tabs/profile.html', full_name=full_name,
                               email=user_data.get('email', ''),
                               user_id=user_data.get('userID', ''),
                               age=user_data.get('age', ''),
                               birthday=formatted_birthday)
    else:
        return "User not found", 404


@app.route('/api/user/<user_id>')
def get_user_data(user_id):
    user_data = db.collection('users').document(
        user_id).get().to_dict() if user_id else {}
    return jsonify(user_data)


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    resp = make_response(redirect(url_for('login')))
    resp.headers['Cache-Control'] = 'no-store'
    resp.headers['Pragma'] = 'no-cache'
    return resp


@app.route('/data')
def get_data():
    users = get_all_users()
    return jsonify(users)


@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == '__main__':
    app.run(debug=True)
