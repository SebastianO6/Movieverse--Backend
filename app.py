from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv

# Load .env
load_dotenv()

app = Flask(__name__)
CORS(app)

OMDB_API_KEY = os.getenv('OMDB_API_KEY')

@app.route('/')
def home():
    return jsonify({"status": "running", "message": "Welcome to Movieverse API"}), 200

@app.route('/api/movies', methods=['GET'])
def search_movies():
    query = request.args.get('query')
    if not query:
        return jsonify({'error': 'Missing search query'}), 400
    
    omdb_url = f"http://www.omdbapi.com/?apikey={OMDB_API_KEY}&s={query}"
    response = requests.get(omdb_url)
    data = response.json()

    if data.get('Response') == 'False':
        return jsonify({'error': data.get('Error', 'No results found')}), 404

    return jsonify(data.get('Search', [])), 200

@app.route('/api/movies/<imdb_id>', methods=['GET'])
def get_movie_details(imdb_id):
    omdb_url = f"http://www.omdbapi.com/?apikey={OMDB_API_KEY}&i={imdb_id}"
    response = requests.get(omdb_url)
    data = response.json()

    if data.get('Response') == 'False':
        return jsonify({'error': data.get('Error', 'Movie not found')}), 404

    return jsonify(data), 200

if __name__ == '__main__':
    app.run(debug=True)
