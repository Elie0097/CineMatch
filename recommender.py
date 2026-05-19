import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


def get_recommendations(user_id, ratings_query_fn, n=20):
    """
    Collaborative filtering recommendation engine.
    Returns a list of tmdb_ids sorted by predicted score.
    ratings_query_fn returns all Rating objects from the DB.
    """
    all_ratings = ratings_query_fn()

    if not all_ratings:
        return []

    user_ids = list(set(r.user_id for r in all_ratings))
    movie_tmdb_ids = list(set(r.tmdb_id for r in all_ratings))

    if user_id not in user_ids:
        return []

    user_idx = {uid: i for i, uid in enumerate(user_ids)}
    movie_idx = {mid: i for i, mid in enumerate(movie_tmdb_ids)}

    matrix = np.zeros((len(user_ids), len(movie_tmdb_ids)))

    for r in all_ratings:
        u = user_idx[r.user_id]
        m = movie_idx[r.tmdb_id]
        matrix[u][m] = r.score

    current_user_idx = user_idx[user_id]

    user_rated_count = int(np.count_nonzero(matrix[current_user_idx]))
    if user_rated_count < 3:
        return []

    similarity = cosine_similarity(matrix)

    user_similarities = similarity[current_user_idx].copy()
    user_similarities[current_user_idx] = 0

    already_rated = set(
        movie_tmdb_ids[i]
        for i, val in enumerate(matrix[current_user_idx])
        if val > 0
    )

    scores = {}
    for mid, m_idx in movie_idx.items():
        if mid in already_rated:
            continue
        col = matrix[:, m_idx]
        rated_mask = col > 0
        if not np.any(rated_mask):
            continue
        sim_sum = np.sum(np.abs(user_similarities[rated_mask]))
        if sim_sum == 0:
            continue
        weighted_sum = np.dot(user_similarities, col)
        scores[mid] = weighted_sum / sim_sum

    recommended = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [tmdb_id for tmdb_id, score in recommended[:n] if score > 0]
