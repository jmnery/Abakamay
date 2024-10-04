from flask import jsonify
from firebase_admin import firestore
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash, make_response, Response
import firebase_admin
from firebase_admin import auth
from firebase_admin.exceptions import FirebaseError
import os
import json
import random
from databaseServices import initialize_firebase, add_user_to_db, get_all_users,   get_letter_words_and_completed, get_letter_words_and_completed_with_images, upload_file_to_storage, add_learned_word
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
        return render_template('tabs/m_learn.html', letter=letter, syllable_data={})

    letter_data = letter_doc.to_dict()
    syllables = letter_data.get('syllables', {})

    sorted_syllables = dict(sorted(syllables.items()))
    syllable_data = {}
    for syllable, words_list in sorted_syllables.items():
        # Remove any empty entries and structure data
        words = [{'text': word.get('text', ''), 'extension': word.get(
            'extension', ''), 'value': word.get('value', '')} for word in words_list if word]
        syllable_data[syllable] = words

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


@app.route('/m_quiz/<wordID>', methods=['GET'])
@app.route('/m_quiz', methods=['GET'])
def m_quiz(wordID=None):
    user_id = session.get('user_id')

    if not user_id:
        return redirect(url_for('login'))

    letter_words, completed_words = get_letter_words_and_completed_with_images(
        user_id)

    all_words = []
    for words in letter_words.values():
        all_words.extend(words)

    if not all_words:
        flash('No words available for the quiz.')
        return redirect(url_for('quiz'))

    all_words = [word for word in all_words if isinstance(word, dict)]

    if not all_words:
        flash('No valid words available.')
        return redirect(url_for('quiz'))

    # Use session to store currentIndex
    if 'currentIndex' in session:
        currentIndex = session['currentIndex']
    else:
        currentIndex = 0  # Default to the first word

    # If no wordID is provided, pick a random word
    if not wordID:
        random_word = random.choice(all_words)
        wordID = random_word.get('wordID')
        session['currentIndex'] = all_words.index(random_word)
        return redirect(url_for('m_quiz', wordID=wordID))

    selected_word = next((word for word in all_words if str(
        word.get('wordID')) == str(wordID)), None)
    if not selected_word:
        flash('Invalid word selected.')
        return redirect(url_for('quiz'))

    currentIndex = all_words.index(selected_word)
    session['currentIndex'] = currentIndex  # Update the session index

    all_words_json = json.dumps(all_words)

    return render_template(
        'tabs/m_quiz.html',
        word=selected_word,
        currentIndex=currentIndex,
        totalWords=len(all_words),
        all_words=all_words_json
    )


@app.route('/picker')
def picker():
    user_id = session.get('user_id')  # Get the current user's ID

    if not user_id:
        return redirect(url_for('login'))

    # Fetch the letter words and completed words (assume you have a helper function for this)
    letter_words, completed_words = get_letter_words_and_completed_with_images(
        user_id)

    return render_template('tabs/picker.html', letter_words=letter_words, completed_words=completed_words)


@app.route('/collection')
def collection():
    user_id = session.get('user_id')  # Get the current user's ID

    if not user_id:
        return redirect(url_for('login'))

    # Fetch the letter words and completed words (assume you have a helper function for this)
    letter_words, completed_words = get_letter_words_and_completed_with_images(
        user_id)

    return render_template('tabs/collection.html', letter_words=letter_words, completed_words=completed_words)


@app.route('/profile')
def profile():
    return render_template('tabs/profile.html')


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
