from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from models import db, User, Favorite
import requests
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
app.config['PROPAGATE_EXCEPTIONS'] = True
app.config['JWT_COOKIE_SECURE'] = True
app.config['JWT_COOKIE_SAMESITE'] = 'Lax'
app.config['JWT_TOKEN_LOCATION'] = ['headers', 'cookies']

db.init_app(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"  
)

logging.basicConfig(level=logging.INFO)
app.logger.addHandler(logging.StreamHandler())

OMDB_API_KEY = os.getenv('OMDB_API_KEY')

@app.route('/')
def home():
    return jsonify({"status": "running", "message": "Welcome to Movieverse API"}), 200

@app.route('/api/register', methods=['POST'])
@limiter.limit("10 per minute")
def register():
    try:
        data = request.get_json()
        required_fields = ['username', 'email', 'password']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400

        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already exists'}), 400

        new_user = User(username=data['username'], email=data['email'])
        new_user.set_password(data['password'])
        db.session.add(new_user)
        db.session.commit()

        return jsonify({'message': 'User registered successfully'}), 201
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Registration error: {str(e)}")
        return jsonify({'error': 'Registration failed'}), 500

@app.route('/api/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    try:
        data = request.get_json()
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({'error': 'Missing username or password'}), 400

        user = User.query.filter_by(username=data['username']).first()
        if user and user.check_password(data['password']):
            token = create_access_token(identity=user.id)
            return jsonify({
                'token': token,
                'user_id': user.id,
                'username': user.username
            }), 200
        return jsonify({'error': 'Invalid credentials'}), 401
    except Exception as e:
        app.logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500

@app.route('/api/movies', methods=['GET'])
@limiter.limit("30 per minute")
def search_movies():
    try:
        query = request.args.get('query')
        if not query:
            return jsonify({'error': 'Missing search query'}), 400
        
        omdb_url = f"http://www.omdbapi.com/?apikey={OMDB_API_KEY}&s={query}"
        response = requests.get(omdb_url, timeout=10)
        data = response.json()

        if data.get('Response') == 'False':
            return jsonify({'error': data.get('Error', 'No results found')}), 404

        return jsonify(data.get('Search', [])), 200
    except requests.exceptions.RequestException as e:
        app.logger.error(f"OMDB API connection error: {str(e)}")
        return jsonify({'error': 'Failed to connect to movie database'}), 502
    except Exception as e:
        app.logger.error(f"Search error: {str(e)}")
        return jsonify({'error': 'Search failed'}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
else:
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)