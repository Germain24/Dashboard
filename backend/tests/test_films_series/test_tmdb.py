"""Tests service TMDB (#535) — dégradation gracieuse sans clé."""

from app.services.films_series.tmdb import _map_movie, _map_tv, search, get_details


def test_search_no_key_returns_empty():
    assert search("Inception", "film", api_key="") == []


def test_search_empty_query_returns_empty():
    assert search("  ", "film", api_key="fake_key") == []


def test_get_details_no_key_returns_none():
    assert get_details(27205, "film", api_key="") is None


def test_map_movie_basic():
    raw = {
        "id": 27205,
        "title": "Inception",
        "release_date": "2010-07-16",
        "poster_path": "/9gk7adHYeDvHkCSEqAvQNLV5Uge.jpg",
        "overview": "Un voleur.",
        "runtime": 148,
    }
    result = _map_movie(raw)
    assert result["tmdb_id"] == 27205
    assert result["titre"] == "Inception"
    assert result["annee"] == 2010
    assert result["type"] == "film"
    assert result["duree_min"] == 148
    assert "tmdb.org" in result["poster_url"]


def test_map_movie_missing_date():
    raw = {"id": 1, "title": "Sans date", "release_date": "", "overview": ""}
    result = _map_movie(raw)
    assert result["annee"] is None


def test_map_tv_basic():
    raw = {
        "id": 65494,
        "name": "The Crown",
        "first_air_date": "2016-11-04",
        "poster_path": "/poster.jpg",
        "overview": "La famille royale.",
        "number_of_seasons": 6,
        "number_of_episodes": 60,
    }
    result = _map_tv(raw)
    assert result["tmdb_id"] == 65494
    assert result["titre"] == "The Crown"
    assert result["annee"] == 2016
    assert result["type"] == "serie"
    assert result["nb_saisons"] == 6
    assert result["nb_episodes_total"] == 60


def test_map_movie_no_poster():
    raw = {"id": 2, "title": "Sans affiche", "release_date": "2020-01-01", "overview": ""}
    result = _map_movie(raw)
    assert result["poster_url"] is None
