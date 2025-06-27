from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_migrate import Migrate
from models import db, User, Favorite
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

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

OMDB_API_KEY = os.getenv('OMDB_API_KEY')

@app.route('/')
def home():
    return jsonify({"status": "running", "message": "Welcome to Movieverse API"}), 200

@app.route('/api/register', methods=['POST'])
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
        return jsonify({'error': str(e)}), 500

@app.route('/api/login', methods=['POST'])
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
        return jsonify({'error': str(e)}), 500

@app.route('/api/movies', methods=['GET'])
def search_movies():
    try:
        query = request.args.get('query')
        if not query:
            return jsonify({'error': 'Missing search query'}), 400
        
        omdb_url = f"http://www.omdbapi.com/?apikey={OMDB_API_KEY}&s={query}"
        response = requests.get(omdb_url, timeout=10)  # Added timeout
        data = response.json()

        if data.get('Response') == 'False':
            return jsonify({'error': data.get('Error', 'No results found')}), 404

        return jsonify(data.get('Search', [])), 200
    except requests.exceptions.RequestException as e:
        return jsonify({'error': 'Failed to connect to OMDB API'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/movies/<imdb_id>', methods=['GET'])
def get_movie_details(imdb_id):
    try:
        omdb_url = f"http://www.omdbapi.com/?apikey={OMDB_API_KEY}&i={imdb_id}"
        response = requests.get(omdb_url, timeout=10)
        data = response.json()

        if data.get('Response') == 'False':
            return jsonify({'error': data.get('Error', 'Movie not found')}), 404

        return jsonify(data), 200
    except requests.exceptions.RequestException as e:
        return jsonify({'error': 'Failed to connect to OMDB API'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/favorites', methods=['GET'])
@jwt_required()
def get_favorites():
    try:
        user_id = get_jwt_identity()
        favorites = Favorite.query.filter_by(user_id=user_id).all()
        return jsonify([{
            'id': fav.id,
            'movie_id': fav.movie_id,
            'title': fav.title,
            'poster_url': fav.poster_url
        } for fav in favorites]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/favorites', methods=['POST'])
@jwt_required()
def add_favorite():
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'movie_id' not in data or 'title' not in data:
            return jsonify({'error': 'Missing required fields'}), 400

        existing = Favorite.query.filter_by(
            movie_id=data['movie_id'], 
            user_id=user_id
        ).first()
        if existing:
            return jsonify({'error': 'Movie already in favorites'}), 409

        new_fav = Favorite(
            movie_id=data['movie_id'],
            title=data['title'],
            poster_url=data.get('poster_url'),
            user_id=user_id
        )
        db.session.add(new_fav)
        db.session.commit()
        return jsonify({'message': 'Favorite added'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/favorites/<int:fav_id>', methods=['DELETE'])
@jwt_required()
def delete_favorite(fav_id):
    try:
        user_id = get_jwt_identity()
        fav = Favorite.query.filter_by(id=fav_id, user_id=user_id).first()
        if not fav:
            return jsonify({'error': 'Favorite not found'}), 404
        db.session.delete(fav)
        db.session.commit()
        return jsonify({'message': 'Favorite deleted'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)