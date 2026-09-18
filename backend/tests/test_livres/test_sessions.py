import datetime as dt

from sqlmodel import SQLModel, Session, create_engine, select

from app.models.livres import Book, ReadingSession  # noqa: F401
from app.models.etudes import SessionEtude
from app.services.livres.sessions import LECTURE_HABIT_MIN, is_technical, create_session


def test_lecture_habit_threshold():
    assert LECTURE_HABIT_MIN == 30


def test_triggers_at_threshold():
    assert 30 >= LECTURE_HABIT_MIN
    assert 45 >= LECTURE_HABIT_MIN
    assert 29 < LECTURE_HABIT_MIN


# ── is_technical (#152) ──────────────────────────────────────────────────────

def test_is_technical_true():
    assert is_technical("Informatique")
    assert is_technical("programmation web")
    assert is_technical("Science")


def test_is_technical_false():
    assert not is_technical("Roman")
    assert not is_technical("")
    assert not is_technical(None)


# ── create_session (DB) ──────────────────────────────────────────────────────

def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_create_session_updates_page_courante():
    s = _session()
    b = Book(titre="Roman", genre="Roman", pages=300)
    s.add(b)
    s.commit()
    s.refresh(b)
    create_session(s, b.id, dt.date(2026, 6, 1), 40, page_debut=0, page_fin=120)
    s.refresh(b)
    assert b.page_courante == 120


def test_create_session_does_not_regress_page():
    s = _session()
    b = Book(titre="Roman", genre="Roman", pages=300, page_courante=200)
    s.add(b)
    s.commit()
    s.refresh(b)
    create_session(s, b.id, dt.date(2026, 6, 1), 40, page_debut=100, page_fin=150)
    s.refresh(b)
    assert b.page_courante == 200  # 150 < 200, pas de régression


def test_technical_book_creates_etude_session():
    s = _session()
    b = Book(titre="Clean Code", genre="Informatique", pages=400)
    s.add(b)
    s.commit()
    s.refresh(b)
    create_session(s, b.id, dt.date(2026, 6, 1), 50, page_debut=0, page_fin=40)
    etudes = s.exec(select(SessionEtude)).all()
    assert len(etudes) == 1
    assert "Clean Code" in etudes[0].sujet
    assert etudes[0].duree_min == 50


def test_non_technical_book_no_etude_session():
    s = _session()
    b = Book(titre="Roman", genre="Roman", pages=400)
    s.add(b)
    s.commit()
    s.refresh(b)
    create_session(s, b.id, dt.date(2026, 6, 1), 50, page_debut=0, page_fin=40)
    assert s.exec(select(SessionEtude)).all() == []
