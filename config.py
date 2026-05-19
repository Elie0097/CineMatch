import os

class Config:
    SECRET_KEY = os.environ.get('SESSION_SECRET', 'dev-secret-key')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///movies.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TMDB_API_KEY = os.environ.get('TMDB_API_KEY', '')
    TMDB_BASE_URL = 'https://api.themoviedb.org/3'
    TMDB_IMAGE_BASE_URL = 'https://image.tmdb.org/t/p/w500'
    OMDB_API_KEY = os.environ.get('OMDB_API_KEY', '')
    YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY', '')
