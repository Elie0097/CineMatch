import os
import requests
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config
from models import db, User, Movie, Rating, WatchlistItem, FavoritePerson, FeedbackMessage, UserPreferences, WatchedItem
from recommender import get_recommendations

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def tmdb_get(endpoint, params=None):
    api_key = app.config['TMDB_API_KEY']
    if not api_key:
        return None
    base_url = app.config['TMDB_BASE_URL']
    params = params or {}
    params['api_key'] = api_key
    try:
        response = requests.get(f"{base_url}/{endpoint}", params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def omdb_get(imdb_id):
    api_key = app.config.get('OMDB_API_KEY', '')
    if not api_key or not imdb_id:
        return None
    try:
        response = requests.get(
            'https://www.omdbapi.com/',
            params={'i': imdb_id, 'apikey': api_key},
            timeout=8
        )
        response.raise_for_status()
        data = response.json()
        return data if data.get('Response') == 'True' else None
    except Exception:
        return None


def youtube_trailer(title, year=None):
    api_key = app.config.get('YOUTUBE_API_KEY', '')
    if not api_key or not title:
        return None
    query = f"{title} {year or ''} official trailer".strip()
    try:
        response = requests.get(
            'https://www.googleapis.com/youtube/v3/search',
            params={
                'q': query,
                'part': 'snippet',
                'type': 'video',
                'videoEmbeddable': 'true',
                'maxResults': 1,
                'key': api_key,
            },
            timeout=8
        )
        response.raise_for_status()
        items = response.json().get('items', [])
        return items[0]['id']['videoId'] if items else None
    except Exception:
        return None


@app.route('/api/search-suggestions')
def search_suggestions():
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([])
    results = tmdb_get('search/movie', {'query': query, 'language': 'en-US', 'page': 1}) or {}
    movies = results.get('results', [])[:8]
    suggestions = [
        {
            'id': m['id'],
            'title': m.get('title', ''),
            'year': m.get('release_date', '')[:4] if m.get('release_date') else '',
            'poster_path': m.get('poster_path') or '',
        }
        for m in movies
    ]
    return jsonify(suggestions)


@app.route('/')
def index():
    popular = tmdb_get('movie/popular', {'language': 'en-US', 'page': 1})
    featured = popular.get('results', [])[:6] if popular else []
    trending = tmdb_get('trending/movie/week', {'language': 'en-US'})
    trending_movies = trending.get('results', [])[:4] if trending else []
    api_configured = bool(app.config['TMDB_API_KEY'])
    return render_template('index.html',
                           featured=featured,
                           trending=trending_movies,
                           api_configured=api_configured,
                           image_base=app.config['TMDB_IMAGE_BASE_URL'])


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not all([username, email, password]):
            flash('All fields are required.', 'error')
        elif password != confirm:
            flash('Passwords do not match.', 'error')
        elif len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
        elif User.query.filter_by(username=username).first():
            flash('Username already taken.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
        else:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Account created! Start rating movies to get recommendations.', 'success')
            return redirect(url_for('movies'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/movies')
def movies():
    query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    genre_id = request.args.get('genre', '', type=str)

    if query:
        data = tmdb_get('search/movie', {'query': query, 'language': 'en-US', 'page': page})
    elif genre_id:
        data = tmdb_get('discover/movie', {
            'with_genres': genre_id,
            'language': 'en-US',
            'page': page,
            'sort_by': 'popularity.desc'
        })
    else:
        data = tmdb_get('movie/popular', {'language': 'en-US', 'page': page})

    movies_list = []
    total_pages = 1

    if data:
        movies_list = data.get('results', [])
        total_pages = min(data.get('total_pages', 1), 500)

    genres_data = tmdb_get('genre/movie/list', {'language': 'en-US'})
    genres = genres_data.get('genres', []) if genres_data else []

    user_ratings = {}
    if current_user.is_authenticated:
        ratings = Rating.query.filter_by(user_id=current_user.id).all()
        user_ratings = {r.tmdb_id: r.score for r in ratings}

    api_configured = bool(app.config['TMDB_API_KEY'])
    return render_template('movies.html',
                           movies=movies_list,
                           query=query,
                           page=page,
                           total_pages=total_pages,
                           genres=genres,
                           selected_genre=genre_id,
                           user_ratings=user_ratings,
                           api_configured=api_configured,
                           image_base=app.config['TMDB_IMAGE_BASE_URL'])


@app.route('/movies/<int:tmdb_id>')
def movie_detail(tmdb_id):
    data = tmdb_get(f'movie/{tmdb_id}', {
        'language': 'en-US',
        'append_to_response': 'credits'
    })

    if not data:
        flash('Movie not found or API not configured.', 'error')
        return redirect(url_for('movies'))

    user_rating = None
    if current_user.is_authenticated:
        rating = Rating.query.filter_by(user_id=current_user.id, tmdb_id=tmdb_id).first()
        if rating:
            user_rating = rating.score

    db_movie = Movie.query.filter_by(tmdb_id=tmdb_id).first()
    community_rating = db_movie.average_user_rating if db_movie else None
    rating_count = db_movie.rating_count if db_movie else 0

    on_watchlist = False
    is_watched = False
    if current_user.is_authenticated:
        on_watchlist = WatchlistItem.query.filter_by(
            user_id=current_user.id, tmdb_id=tmdb_id
        ).first() is not None
        is_watched = WatchedItem.query.filter_by(
            user_id=current_user.id, tmdb_id=tmdb_id
        ).first() is not None

    # Extract cast and director
    cast = []
    director = None
    if 'credits' in data:
        cast = data['credits'].get('cast', [])[:6]
        crew = data['credits'].get('crew', [])
        directors = [p for p in crew if p.get('job') == 'Director']
        director = directors[0] if directors else None

    # Combine /similar and /recommendations, filter by shared genre, dedupe, top 8
    current_genre_ids = {g['id'] for g in data.get('genres', [])}
    sim_results  = (tmdb_get(f'movie/{tmdb_id}/similar',         {'language': 'en-US'}) or {}).get('results', [])
    rec_results  = (tmdb_get(f'movie/{tmdb_id}/recommendations', {'language': 'en-US'}) or {}).get('results', [])

    seen_ids = {tmdb_id}
    similar = []
    for m in sim_results + rec_results:
        mid = m.get('id')
        if mid in seen_ids:
            continue
        seen_ids.add(mid)
        movie_genres = set(m.get('genre_ids', []))
        if current_genre_ids and not current_genre_ids.intersection(movie_genres):
            continue
        similar.append(m)
        if len(similar) == 8:
            break

    # "Because you liked..." — find user's top-rated different movie
    because_liked = None
    if current_user.is_authenticated:
        top_rating = (Rating.query
                      .filter(Rating.user_id == current_user.id,
                              Rating.tmdb_id != tmdb_id,
                              Rating.score >= 4)
                      .order_by(Rating.score.desc(), Rating.created_at.desc())
                      .first())
        if top_rating:
            source_movie = Movie.query.filter_by(tmdb_id=top_rating.tmdb_id).first()
            if source_movie:
                rec_data = tmdb_get(f'movie/{top_rating.tmdb_id}/recommendations',
                                    {'language': 'en-US', 'page': 1})
                if rec_data:
                    seen_ids = {r.tmdb_id for r in Rating.query.filter_by(user_id=current_user.id).all()}
                    recs = [m for m in rec_data.get('results', [])
                            if m['id'] not in seen_ids and m['id'] != tmdb_id][:4]
                    if recs:
                        because_liked = {'source_title': source_movie.title, 'movies': recs}

    # Favorite person IDs for heart buttons
    favorite_person_ids = set()
    if current_user.is_authenticated:
        favs = FavoritePerson.query.filter_by(user_id=current_user.id).all()
        favorite_person_ids = {f.tmdb_person_id for f in favs}

    # OMDB enrichment (awards, box office, Metacritic, Rotten Tomatoes)
    omdb_data = omdb_get(data.get('imdb_id'))

    # YouTube trailer
    release_year = data.get('release_date', '')[:4] if data.get('release_date') else None
    trailer_video_id = youtube_trailer(data.get('title', ''), release_year)

    return render_template('movie_detail.html',
                           movie=data,
                           cast=cast,
                           director=director,
                           similar=similar,
                           because_liked=because_liked,
                           user_rating=user_rating,
                           on_watchlist=on_watchlist,
                           is_watched=is_watched,
                           community_rating=community_rating,
                           rating_count=rating_count,
                           favorite_person_ids=favorite_person_ids,
                           omdb=omdb_data,
                           trailer_video_id=trailer_video_id,
                           image_base=app.config['TMDB_IMAGE_BASE_URL'])


@app.route('/movies/<int:tmdb_id>/rate', methods=['POST'])
@login_required
def rate_movie(tmdb_id):
    score = request.form.get('score', type=int)
    if not score or score < 1 or score > 5:
        flash('Invalid rating.', 'error')
        return redirect(url_for('movie_detail', tmdb_id=tmdb_id))

    movie = Movie.query.filter_by(tmdb_id=tmdb_id).first()
    if not movie:
        data = tmdb_get(f'movie/{tmdb_id}', {'language': 'en-US'})
        if data:
            genres = ', '.join(g['name'] for g in data.get('genres', []))
            movie = Movie(
                tmdb_id=tmdb_id,
                title=data.get('title', ''),
                overview=data.get('overview', ''),
                poster_path=data.get('poster_path', ''),
                release_date=data.get('release_date', ''),
                vote_average=data.get('vote_average', 0),
                genres=genres
            )
            db.session.add(movie)
            db.session.commit()

    if movie:
        existing = Rating.query.filter_by(user_id=current_user.id, tmdb_id=tmdb_id).first()
        if existing:
            existing.score = score
        else:
            rating = Rating(
                user_id=current_user.id,
                movie_id=movie.id,
                tmdb_id=tmdb_id,
                score=score
            )
            db.session.add(rating)
        db.session.commit()
        flash(f'Rated {score} star{"s" if score != 1 else ""}!', 'success')

    return redirect(url_for('movie_detail', tmdb_id=tmdb_id))


@app.route('/recommendations')
@login_required
def recommendations():
    def all_ratings():
        return Rating.query.all()

    rated_ids = {r.tmdb_id for r in Rating.query.filter_by(user_id=current_user.id).all()}
    user_rating_count = len(rated_ids)

    # Read filter params from URL
    genre_filter = request.args.get('genre', '')
    year_from    = request.args.get('year_from', '')
    year_to      = request.args.get('year_to', '')
    min_rating   = request.args.get('min_rating', '')
    sort_by      = request.args.get('sort_by', 'match')

    all_movies = []

    if genre_filter:
        # Genre selected → use TMDB discover for that genre (guarantees 20+ results)
        discover_params = {
            'language': 'en-US',
            'with_genres': genre_filter,
            'sort_by': 'vote_count.desc',
            'vote_count.gte': 100,
        }
        if min_rating:
            discover_params['vote_average.gte'] = float(min_rating)
        if year_from:
            discover_params['primary_release_date.gte'] = f'{year_from}-01-01'
        if year_to:
            discover_params['primary_release_date.lte'] = f'{year_to}-12-31'

        seen = set()
        for page in range(1, 11):          # up to 3 pages = 60 candidates
            discover_params['page'] = page
            data = tmdb_get('discover/movie', discover_params)
            if not data:
                break
            for m in data.get('results', []):
                if m['id'] not in rated_ids and m['id'] not in seen:
                    all_movies.append(m)
                    seen.add(m['id'])
            if len(all_movies) >= 200:
                break
    else:
        # No genre filter → popular + top_rated pool + ML picks
        pool = {}
        for endpoint, page in [
            ('movie/popular', 1), ('movie/popular', 2), ('movie/popular', 3),
            ('movie/top_rated', 1), ('movie/top_rated', 2), ('movie/top_rated', 3),
        ]:
            data = tmdb_get(endpoint, {'language': 'en-US', 'page': page})
            if data:
                for m in data.get('results', []):
                    if m['id'] not in rated_ids and m['id'] not in pool:
                        pool[m['id']] = m

        if user_rating_count >= 3:
            recommended_ids = get_recommendations(current_user.id, all_ratings, n=30)
            for tmdb_id in recommended_ids:
                if tmdb_id not in rated_ids and tmdb_id not in pool:
                    data = tmdb_get(f'movie/{tmdb_id}', {'language': 'en-US'})
                    if data:
                        pool[tmdb_id] = data

        all_movies = list(pool.values())

        # Apply year / rating filters server-side
        if year_from:
            all_movies = [m for m in all_movies
                          if (m.get('release_date') or '') >= f'{year_from}-01-01']
        if year_to:
            all_movies = [m for m in all_movies
                          if (m.get('release_date') or '9') <= f'{year_to}-12-31']
        if min_rating:
            all_movies = [m for m in all_movies
                          if (m.get('vote_average') or 0) >= float(min_rating)]

    # Sort
    if sort_by == 'rating':
        all_movies.sort(key=lambda m: m.get('vote_average') or 0, reverse=True)
    elif sort_by == 'year_desc':
        all_movies.sort(key=lambda m: m.get('release_date') or '', reverse=True)
    elif sort_by == 'year_asc':
        all_movies.sort(key=lambda m: m.get('release_date') or '')
    elif sort_by == 'popularity':
        all_movies.sort(key=lambda m: m.get('popularity') or 0, reverse=True)
    # 'match' keeps natural order

    genres_data = tmdb_get('genre/movie/list', {'language': 'en-US'})
    genres = genres_data.get('genres', []) if genres_data else []

    prefs = UserPreferences.query.filter_by(user_id=current_user.id).first()

    return render_template('recommendations.html',
                           movies=all_movies,
                           user_rating_count=user_rating_count,
                           genres=genres,
                           prefs=prefs,
                           genre_filter=genre_filter,
                           year_from=year_from,
                           year_to=year_to,
                           min_rating=min_rating,
                           sort_by=sort_by,
                           image_base=app.config['TMDB_IMAGE_BASE_URL'])


@app.route('/profile')
@login_required
def profile():
    ratings = (Rating.query
               .filter_by(user_id=current_user.id)
               .order_by(Rating.created_at.desc())
               .all())

    rated_movies = []
    for r in ratings:
        movie = Movie.query.get(r.movie_id)
        if movie:
            rated_movies.append({'movie': movie, 'score': r.score, 'rated_at': r.created_at})

    avg_score = None
    if ratings:
        avg_score = round(sum(r.score for r in ratings) / len(ratings), 1)

    favorite_people = (FavoritePerson.query
                       .filter_by(user_id=current_user.id)
                       .order_by(FavoritePerson.added_at.desc())
                       .all())

    prefs = UserPreferences.query.filter_by(user_id=current_user.id).first()
    watched_count = WatchedItem.query.filter_by(user_id=current_user.id).count()

    genres_data = tmdb_get('genre/movie/list', {'language': 'en-US'})
    genres = genres_data.get('genres', []) if genres_data else []
    pref_genre_ids = set(prefs.favorite_genre_ids.split(',')) if prefs and prefs.favorite_genre_ids else set()

    return render_template('profile.html',
                           rated_movies=rated_movies,
                           avg_score=avg_score,
                           favorite_people=favorite_people,
                           prefs=prefs,
                           genres=genres,
                           pref_genre_ids=pref_genre_ids,
                           watched_count=watched_count,
                           image_base=app.config['TMDB_IMAGE_BASE_URL'])


@app.route('/favorites/person/add', methods=['POST'])
@login_required
def favorite_person_add():
    tmdb_person_id = request.form.get('tmdb_person_id', type=int)
    name = request.form.get('name', '').strip()
    profile_path = request.form.get('profile_path', '')
    known_for_department = request.form.get('known_for_department', '')

    if not tmdb_person_id or not name:
        flash('Invalid data.', 'error')
        return redirect(request.referrer or url_for('movies'))

    existing = FavoritePerson.query.filter_by(
        user_id=current_user.id, tmdb_person_id=tmdb_person_id
    ).first()
    if not existing:
        fav = FavoritePerson(
            user_id=current_user.id,
            tmdb_person_id=tmdb_person_id,
            name=name,
            profile_path=profile_path or None,
            known_for_department=known_for_department or 'Acting'
        )
        db.session.add(fav)
        db.session.commit()
        flash(f'{name} added to your favorites.', 'success')

    return redirect(request.referrer or url_for('movies'))


@app.route('/favorites/person/remove/<int:tmdb_person_id>', methods=['POST'])
@login_required
def favorite_person_remove(tmdb_person_id):
    fav = FavoritePerson.query.filter_by(
        user_id=current_user.id, tmdb_person_id=tmdb_person_id
    ).first()
    if fav:
        name = fav.name
        db.session.delete(fav)
        db.session.commit()
        flash(f'{name} removed from favorites.', 'success')
    return redirect(request.referrer or url_for('profile'))


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()

        if not all([name, email, subject, message]):
            flash('All fields are required.', 'error')
        else:
            msg = FeedbackMessage(name=name, email=email, subject=subject, message=message)
            db.session.add(msg)
            db.session.commit()
            flash('Message sent! We appreciate your feedback.', 'success')
            return redirect(url_for('contact'))

    return render_template('contact.html')


@app.route('/profile/preferences', methods=['POST'])
@login_required
def save_preferences():
    genre_ids = request.form.getlist('genre_ids')
    min_rating = request.form.get('min_tmdb_rating', '0')
    decade = request.form.get('preferred_decade', '')

    try:
        min_rating_f = float(min_rating)
    except ValueError:
        min_rating_f = 0.0

    prefs = UserPreferences.query.filter_by(user_id=current_user.id).first()
    if prefs:
        prefs.favorite_genre_ids = ','.join(genre_ids)
        prefs.min_tmdb_rating = min_rating_f
        prefs.preferred_decade = decade
        prefs.updated_at = datetime.utcnow()
    else:
        prefs = UserPreferences(
            user_id=current_user.id,
            favorite_genre_ids=','.join(genre_ids),
            min_tmdb_rating=min_rating_f,
            preferred_decade=decade
        )
        db.session.add(prefs)
    db.session.commit()
    flash('Preferences saved.', 'success')
    return redirect(url_for('profile') + '#preferences')


@app.route('/watched/mark/<int:tmdb_id>', methods=['POST'])
@login_required
def watched_mark(tmdb_id):
    existing = WatchedItem.query.filter_by(user_id=current_user.id, tmdb_id=tmdb_id).first()
    if not existing:
        title = request.form.get('title', '')
        poster_path = request.form.get('poster_path', '')
        if not title:
            data = tmdb_get(f'movie/{tmdb_id}', {'language': 'en-US'})
            title = data.get('title', '') if data else ''
            poster_path = data.get('poster_path', '') if data else ''
        item = WatchedItem(
            user_id=current_user.id,
            tmdb_id=tmdb_id,
            title=title,
            poster_path=poster_path or None
        )
        db.session.add(item)
        db.session.commit()
        flash(f'"{title}" marked as watched.', 'success')
    return redirect(request.referrer or url_for('watchlist'))


@app.route('/watched/unmark/<int:tmdb_id>', methods=['POST'])
@login_required
def watched_unmark(tmdb_id):
    item = WatchedItem.query.filter_by(user_id=current_user.id, tmdb_id=tmdb_id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
        flash('Removed from watched.', 'success')
    return redirect(request.referrer or url_for('watchlist'))


@app.route('/watchlist')
@login_required
def watchlist():
    items = (WatchlistItem.query
             .filter_by(user_id=current_user.id)
             .order_by(WatchlistItem.added_at.desc())
             .all())
    watched_ids = {w.tmdb_id for w in WatchedItem.query.filter_by(user_id=current_user.id).all()}
    return render_template('watchlist.html',
                           items=items,
                           watched_ids=watched_ids,
                           image_base=app.config['TMDB_IMAGE_BASE_URL'])


@app.route('/watchlist/add/<int:tmdb_id>', methods=['POST'])
@login_required
def watchlist_add(tmdb_id):
    existing = WatchlistItem.query.filter_by(user_id=current_user.id, tmdb_id=tmdb_id).first()
    if existing:
        flash('Already on your watchlist.', 'info')
        return redirect(url_for('movie_detail', tmdb_id=tmdb_id))

    data = tmdb_get(f'movie/{tmdb_id}', {'language': 'en-US'})
    if not data:
        flash('Could not fetch movie data.', 'error')
        return redirect(url_for('movie_detail', tmdb_id=tmdb_id))

    item = WatchlistItem(
        user_id=current_user.id,
        tmdb_id=tmdb_id,
        title=data.get('title', ''),
        poster_path=data.get('poster_path', ''),
        release_date=data.get('release_date', ''),
        vote_average=data.get('vote_average', 0),
    )
    db.session.add(item)
    db.session.commit()
    flash(f'"{data.get("title")}" added to your watchlist.', 'success')
    return redirect(url_for('movie_detail', tmdb_id=tmdb_id))


@app.route('/watchlist/remove/<int:tmdb_id>', methods=['POST'])
@login_required
def watchlist_remove(tmdb_id):
    item = WatchlistItem.query.filter_by(user_id=current_user.id, tmdb_id=tmdb_id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
        flash('Removed from your watchlist.', 'success')
    return redirect(request.referrer or url_for('watchlist'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
