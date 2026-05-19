from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ratings = db.relationship('Rating', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tmdb_id = db.Column(db.Integer, unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    overview = db.Column(db.Text)
    poster_path = db.Column(db.String(200))
    release_date = db.Column(db.String(20))
    vote_average = db.Column(db.Float)
    genres = db.Column(db.String(200))
    ratings = db.relationship('Rating', backref='movie', lazy=True)

    @property
    def average_user_rating(self):
        if not self.ratings:
            return None
        return round(sum(r.score for r in self.ratings) / len(self.ratings), 1)

    @property
    def rating_count(self):
        return len(self.ratings)


class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey('movie.id'), nullable=False)
    tmdb_id = db.Column(db.Integer, nullable=False)
    score = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'movie_id'),)


class WatchlistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tmdb_id = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    poster_path = db.Column(db.String(200))
    release_date = db.Column(db.String(20))
    vote_average = db.Column(db.Float)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'tmdb_id'),)


class FavoritePerson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tmdb_person_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    profile_path = db.Column(db.String(200))
    known_for_department = db.Column(db.String(50))
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'tmdb_person_id'),)


class FeedbackMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class UserPreferences(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    favorite_genre_ids = db.Column(db.String(200), default='')
    min_tmdb_rating = db.Column(db.Float, default=0.0)
    preferred_decade = db.Column(db.String(10), default='')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class WatchedItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tmdb_id = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    poster_path = db.Column(db.String(200))
    watched_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'tmdb_id'),)
