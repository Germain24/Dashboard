"""Tests TDD — regroupement en series/mangas (tomes) (#5.3).

Les livres sans `serie` restent des ouvrages isoles : ils ne doivent jamais
apparaitre dans le regroupement.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.db import get_session
from app.main import create_app
from app.models.livres import Book
from app.services.livres.series import group_series_pure


def _book(**kw) -> Book:
    base = dict(titre="T", auteur="A", statut="a_lire", genre="", pages=200)
    base.update(kw)
    return Book(**base)


def test_standalone_books_are_excluded():
    """Un livre sans `serie` (essai, roman isole) n'entre dans aucun groupe."""
    books = [
        _book(titre="Sapiens"),
        _book(titre="Vagabond 1", serie="Vagabond", tome=1),
    ]
    groupes = group_series_pure(books)
    assert [g["serie"] for g in groupes] == ["Vagabond"]
    assert [t["titre"] for t in groupes[0]["tomes"]] == ["Vagabond 1"]


def test_tomes_are_sorted_by_number():
    books = [
        _book(titre="OP 3", serie="One Piece", tome=3),
        _book(titre="OP 1", serie="One Piece", tome=1),
        _book(titre="OP 2", serie="One Piece", tome=2),
    ]
    groupes = group_series_pure(books)
    assert [t["tome"] for t in groupes[0]["tomes"]] == [1, 2, 3]


def test_progression_counts_read_tomes():
    books = [
        _book(titre="B1", serie="Berserk", tome=1, statut="lu"),
        _book(titre="B2", serie="Berserk", tome=2, statut="lu"),
        _book(titre="B3", serie="Berserk", tome=3, statut="en_cours"),
        _book(titre="B4", serie="Berserk", tome=4, statut="a_lire"),
    ]
    g = group_series_pure(books)[0]
    assert g["total"] == 4
    assert g["tomes_lus"] == 2
    assert g["pct"] == 50


def test_missing_tome_numbers_do_not_crash():
    """Numerotation trouee (1, 3) + tome inconnu (None) : pas d'exception, et le
    tome sans numero est classe en dernier."""
    books = [
        _book(titre="Gunnm 3", serie="Gunnm", tome=3),
        _book(titre="Gunnm HS", serie="Gunnm", tome=None),
        _book(titre="Gunnm 1", serie="Gunnm", tome=1),
    ]
    g = group_series_pure(books)[0]
    assert [t["tome"] for t in g["tomes"]] == [1, 3, None]
    assert g["total"] == 3


def test_several_series_sorted_alphabetically():
    books = [
        _book(titre="Z1", serie="Zetman", tome=1),
        _book(titre="A1", serie="Akira", tome=1),
    ]
    assert [g["serie"] for g in group_series_pure(books)] == ["Akira", "Zetman"]


def test_empty_library():
    assert group_series_pure([]) == []


# ───────────────────── endpoint ──────────────────────────────────

@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    with Session(engine) as s:
        s.add(_book(titre="Sapiens"))
        s.add(_book(titre="OP 2", serie="One Piece", tome=2, statut="lu"))
        s.add(_book(titre="OP 1", serie="One Piece", tome=1, statut="lu"))
        s.commit()
    with TestClient(app) as c:
        yield c


def test_series_endpoint_shape(client):
    r = client.get("/livres/series")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1  # Sapiens est isole, pas une serie
    g = data[0]
    assert g["serie"] == "One Piece"
    assert g["total"] == 2
    assert g["tomes_lus"] == 2
    assert g["pct"] == 100
    assert [t["tome"] for t in g["tomes"]] == [1, 2]
    assert g["tomes"][0]["titre"] == "OP 1"
