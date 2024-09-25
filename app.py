from firebase_admin import firestore
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash, make_response, Response
import firebase_admin
from firebase_admin import auth
from firebase_admin.exceptions import FirebaseError
import os
from databaseServices import initialize_firebase, add_user_to_db, get_all_users, add_letter_syllable_words, get_firestore_client, get_letter_words_and_completed, get_letter_words
from camera import generate_frames

app = Flask(__name__)  # Only this instance should exist

# Set the secret key for session management
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')

# Initialize Firebase
credentials_path = r'C:\Users\Daniel\Desktop\Flask Project\Abakada\abakada_flask\services\credentials.json'
firebase_url = 'https://abakada-flask-default-rtdb.firebaseio.com/'
initialize_firebase(credentials_path, firebase_url)

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
        return redirect(url_for('main'))
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
            return redirect(url_for('main'))
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
        words = request.form['words']  # Comma-separated words input

        try:
            add_letter_syllable_words(letter, syllable, words)
            flash(
                f"Successfully added letter: {letter}, syllable: {syllable}, and words: {words}", 'success')
        except Exception as e:
            flash(f"Failed to add to database: {e}", 'danger')

    return render_template('admin.html')


@app.route('/main')
def main():
    return render_template('tabs/learn.html')


@app.route('/learn')
def learn():
    letters_ref = db.collection('letters')
    docs = letters_ref.stream()
    letters = [doc.id for doc in docs]

    return render_template('tabs/learn.html', letters=letters)


@app.route('/m_learn/<letter>')
def m_learn(letter):
    letter_ref = db.collection('letters').document(letter)
    letter_doc = letter_ref.get()

    if not letter_doc.exists:
        return render_template('tabs/m_learn.html', letter=letter, syllable_data={})

    letter_data = letter_doc.to_dict()
    syllables = letter_data.get('syllables', {})

    sorted_syllables = dict(sorted(syllables.items()))
    syllable_data = {}
    for syllable, words_list in sorted_syllables.items():
        words = [word for word in words_list if word]
        syllable_data[syllable] = words

    return render_template('tabs/m_learn.html', letter=letter, syllable_data=syllable_data)


@app.route('/quiz')
def quiz():
    user_id = session.get('user_id')  # Get the current user's ID

    if not user_id:
        return redirect(url_for('login'))

    letter_words, completed_words = get_letter_words_and_completed(user_id)

    return render_template('tabs/quiz.html', letter_words=letter_words, completed_words=completed_words)


@app.route('/collection')
def collection():
    return render_template('tabs/collection.html')


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
