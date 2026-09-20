from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import re, os

app = Flask(__name__)
app.secret_key = "change-this-secret-key-12345"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///friends.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ---------- DATABASE MODELS ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    seen_intro = db.Column(db.Boolean, default=False)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User')

# ---------- YOUTUBE LINK DETECTION ----------
def extract_youtube_id(text):
    pattern = r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, text)
    return match.group(1) if match else None

# ---------- ROUTES ----------
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user.seen_intro and not user.is_admin:
        return redirect(url_for('intro'))
    return redirect(url_for('chat'))

@app.route('/intro')
def intro():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('intro.html', user=user)

@app.route('/skip_intro')
def skip_intro():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        user.seen_intro = True
        db.session.commit()
    return redirect(url_for('chat'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name'].strip()
        password = request.form['password']
        if User.query.filter_by(name=name).first():
            return render_template('signup.html', error="Name already taken")
        is_admin = (name.lower() == 'admin')  # 'admin' is YOU
        user = User(name=name, password=generate_password_hash(password), is_admin=is_admin)
        db.session.add(user)
        db.session.commit()
        session['user_id'] = user.id
        return redirect(url_for('index'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form['name'].strip()
        password = request.form['password']
        user = User.query.filter_by(name=name).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect(url_for('index'))
        return render_template('login.html', error="Wrong name or password")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('chat.html', user=user)

@app.route('/api/messages')
def get_messages():
    if 'user_id' not in session:
        return jsonify([])
    msgs = Message.query.order_by(Message.timestamp.asc()).limit(200).all()
    result = []
    for m in msgs:
        yt_id = extract_youtube_id(m.text)
        result.append({
            'id': m.id,
            'name': m.user.name,
            'text': m.text,
            'youtube_id': yt_id,
            'time': m.timestamp.strftime('%H:%M'),
            'is_admin': m.user.is_admin
        })
    return jsonify(result)

@app.route('/api/send', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return jsonify({'ok': False})
    text = request.json.get('text', '').strip()
    if not text:
        return jsonify({'ok': False})
    msg = Message(user_id=session['user_id'], text=text)
    db.session.add(msg)
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/api/delete/<int:msg_id>', methods=['DELETE'])
def delete_message(msg_id):
    if 'user_id' not in session:
        return jsonify({'ok': False})
    user = User.query.get(session['user_id'])
    if not user.is_admin:
        return jsonify({'ok': False})
    msg = Message.query.get(msg_id)
    if msg:
        db.session.delete(msg)
        db.session.commit()
    return jsonify({'ok': True})

# ---------- CREATE DB ON FIRST RUN ----------
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)