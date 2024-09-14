from flask import Flask, jsonify, request, redirect, url_for, session, flash, render_template, make_response
import firebase_admin
from firebase_admin import credentials, firestore, auth
from firebase_admin.exceptions import FirebaseError
import os

app = Flask(__name__)

# Set the secret key for session management
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')

# Firebase credentials
credentialsURL = r'C:\Users\Daniel\Desktop\Flask Project\Abakada\abakada_flask\services\credentials.json'
firebaseUrl = 'https://abakada-flask-default-rtdb.firebaseio.com/'

try:
    cred = credentials.Certificate(credentialsURL)
    firebase_admin.initialize_app(
        cred, {"databaseURL": firebaseUrl})
    print("Firebase initialized successfully.")
except Exception as e:
    print(f"Error initializing Firebase: {e}")

# Initialize Firestore
db = firestore.client()


@app.before_request
def check_authentication():
    # List of routes that can be accessed without being logged in
    public_routes = ['login', 'signup']
    if request.endpoint in public_routes and 'user_id' in session:
        return redirect(url_for('main'))

    # Redirect users to login if trying to access protected routes without being authenticated
    if request.endpoint not in public_routes and 'user_id' not in session:
        return redirect(url_for('login'))


@app.after_request
def add_cache_control(response):
    # Set cache control for all responses
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
            return redirect(url_for('main'))
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
                display_name=f"{first_name} {last_name}"
            )
            db.collection('users').document(user.uid).set({
                'firstName': first_name,
                'lastName': last_name,
                'email': email,
                'age': age
            })
            session['user_id'] = user.uid
            return redirect(url_for('main'))
        except ValueError as ve:
            flash(f'Error: {ve}')
        except FirebaseError as e:
            flash(f'Error creating user: {e}')
    return render_template('signup.html')


@app.route('/main')
def main():
    return render_template('tabs/learn.html')


@app.route('/learn')
def learn():
    return render_template('tabs/learn.html')


@app.route('/quiz')
def quiz():
    return render_template('tabs/quiz.html')


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
    users_ref = db.collection('users')
    docs = users_ref.stream()

    users = {}
    for doc in docs:
        users[doc.id] = doc.to_dict()

    return jsonify(users)


if __name__ == '__main__':
    app.run(debug=True)
