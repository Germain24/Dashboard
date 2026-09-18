"""Tests stats annuelles & recommandations (#146, #149)."""

import datetime as dt

from app.models.livres import Book
from app.services.livres.analytics import annual_stats_pure, recommend_pure


def _book(**kw) -> Book:
    base = dict(titre="T", auteur="A", statut="a_lire", genre="", pages=100)
    base.update(kw)
    return Book(**base)


def test_annual_stats_counts_only_year_read():
    books = [
        _book(statut="lu", genre="SF", pages=200, date_fin=dt.date(2026, 3, 1)),
        _book(statut="lu", genre="SF", pages=300, date_fin=dt.date(2026, 9, 1)),
        _book(statut="lu", genre="Essai", pages=150, date_fin=dt.date(2025, 5, 1)),  # autre année
        _book(statut="a_lire", genre="SF"),  # pas lu
    ]
    s = annual_stats_pure(books, 2026)
    assert s["livres_lus"] == 2
    assert s["pages_lues"] == 500
    assert s["par_genre"] == {"SF": 2}


def test_annual_stats_empty():
    s = annual_stats_pure([], 2026)
    assert s["livres_lus"] == 0
    assert s["pages_lues"] == 0
    assert s["par_genre"] == {}


def test_recommend_prioritizes_read_genres():
    books = [
        _book(statut="lu", genre="SF"),
        _book(statut="lu", genre="SF"),
        _book(statut="lu", genre="Essai"),
        _book(titre="A lire SF", statut="a_lire", genre="SF"),
        _book(titre="A lire Polar", statut="a_lire", genre="Polar"),
    ]
    rec = recommend_pure(books)
    assert rec[0]["titre"] == "A lire SF"
    assert "SF" in rec[0]["raison"]


def test_recommend_empty_when_nothing_to_read():
    assert recommend_pure([_book(statut="lu", genre="SF")]) == []


def test_recommend_respects_limit():
    books = [_book(titre=f"L{i}", statut="a_lire", genre="X") for i in range(10)]
    assert len(recommend_pure(books, limit=3)) == 3
