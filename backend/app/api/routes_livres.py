import datetime as dt
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.livres import Book, BookNote, BookQuote, ReadingSession
from app.services.livres import books as books_svc
from app.services.livres import notes as notes_svc
from app.services.livres import sessions as sessions_svc
from app.services.livres import metadata as metadata_svc
from app.services.livres import analytics as analytics_svc
from app.services.livres import progress as progress_svc
from app.services.livres import goals as goals_svc
from pydantic import BaseModel

router = APIRouter(prefix="", tags=["livres"])

class BookCreate(BaseModel):
    titre: str
    auteur: str = ""
    isbn: str | None = None
    pages: int | None = None
    statut: str = "a_lire"
    genre: str = ""
    format: str = "papier"

class NoteCreate(BaseModel):
    contenu: str
    page: int | None = None
    tags: list[str] = []

class QuoteCreate(BaseModel):
    texte: str
    page: int | None = None

class SessionCreate(BaseModel):
    date: dt.date
    duree_minutes: int
    page_debut: int | None = None
    page_fin: int | None = None

class GoalUpdate(BaseModel):
    annual_goal: int

@router.get("/books")
def list_books(statut: str | None = None, sort: str | None = None,
               session: Session = Depends(get_session)):
    return books_svc.get_books(session, statut, sort)

@router.get("/search")
def search(q: str, limit: int = 10):
    """Recherche de livres via Open Library (#143)."""
    return metadata_svc.search_books(q, limit)

@router.post("/books", status_code=201)
def create_book(body: BookCreate, session: Session = Depends(get_session)):
    return books_svc.create_book(session, **body.model_dump())

@router.post("/books/from-isbn", status_code=201)
def from_isbn(isbn: str, session: Session = Depends(get_session)):
    book = books_svc.create_book_from_isbn(session, isbn)
    if not book:
        raise HTTPException(404, "ISBN not found in Open Library")
    return book

@router.patch("/books/{id}")
def update_book(id: int, body: dict, session: Session = Depends(get_session)):
    b = session.get(Book, id)
    if not b:
        raise HTTPException(404)
    for k, v in body.items():
        setattr(b, k, v)
    session.add(b)
    session.commit()
    session.refresh(b)
    return b

@router.delete("/books/{id}", status_code=204)
def delete_book(id: int, session: Session = Depends(get_session)):
    b = session.get(Book, id)
    if not b:
        raise HTTPException(404)
    session.delete(b)
    session.commit()

@router.get("/books/{id}/notes")
def get_notes(id: int, session: Session = Depends(get_session)):
    return notes_svc.get_notes(session, id)

@router.post("/books/{id}/notes", status_code=201)
def create_note(id: int, body: NoteCreate, session: Session = Depends(get_session)):
    return notes_svc.create_note(session, id, body.contenu, body.page, body.tags)

@router.patch("/notes/{id}")
def update_note(id: int, body: dict, session: Session = Depends(get_session)):
    n = session.get(BookNote, id)
    if not n:
        raise HTTPException(404)
    for k, v in body.items():
        setattr(n, k, v)
    session.add(n)
    session.commit()
    return n

@router.delete("/notes/{id}", status_code=204)
def delete_note(id: int, session: Session = Depends(get_session)):
    n = session.get(BookNote, id)
    if not n:
        raise HTTPException(404)
    session.delete(n)
    session.commit()

@router.get("/books/{id}/quotes")
def get_quotes(id: int, session: Session = Depends(get_session)):
    return notes_svc.get_quotes(session, id)

@router.post("/books/{id}/quotes", status_code=201)
def create_quote(id: int, body: QuoteCreate, session: Session = Depends(get_session)):
    return notes_svc.create_quote(session, id, body.texte, body.page)

@router.delete("/quotes/{id}", status_code=204)
def delete_quote(id: int, session: Session = Depends(get_session)):
    q = session.get(BookQuote, id)
    if not q:
        raise HTTPException(404)
    session.delete(q)
    session.commit()

@router.post("/books/{id}/sessions", status_code=201)
def create_reading_session(id: int, body: SessionCreate, session: Session = Depends(get_session)):
    return sessions_svc.create_session(session, id, body.date, body.duree_minutes,
                                       body.page_debut, body.page_fin)

@router.get("/stats")
def stats(session: Session = Depends(get_session)):
    return books_svc.get_stats(session)


@router.get("/stats/annual")
def annual_stats(year: int | None = None, session: Session = Depends(get_session)):
    """Stats annuelles + challenge lecture (#146/#151)."""
    y = year or dt.date.today().year
    data = analytics_svc.annual_stats(session, y)
    goal = goals_svc.get_annual_goal()
    data["challenge"] = goals_svc.goal_progress(data["livres_lus"], goal)
    return data


@router.get("/recommendations")
def recommendations(limit: int = 5, session: Session = Depends(get_session)):
    """Recommandations basées sur les genres lus (#149)."""
    return analytics_svc.recommend_books(session, limit)


@router.get("/reading-goal")
def get_reading_goal():
    """Objectif annuel de lecture (#151)."""
    return {"annual_goal": goals_svc.get_annual_goal()}


@router.post("/reading-goal")
def set_reading_goal(body: GoalUpdate):
    try:
        goal = goals_svc.set_annual_goal(body.annual_goal)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"annual_goal": goal}


@router.get("/books/{id}/estimate")
def estimate(id: int, session: Session = Depends(get_session)):
    """Temps de lecture restant estimé selon le rythme (#150)."""
    book = session.get(Book, id)
    if not book:
        raise HTTPException(404)
    sessions = session.exec(
        select(ReadingSession).where(ReadingSession.book_id == id)
    ).all()
    pages_read = sum(
        (s.page_fin - s.page_debut)
        for s in sessions
        if s.page_fin is not None and s.page_debut is not None and s.page_fin >= s.page_debut
    )
    minutes = sum(s.duree_minutes for s in sessions)
    pace = progress_svc.reading_pace(pages_read, minutes)
    remaining = progress_svc.estimate_remaining_minutes(book.page_courante, book.pages, pace)
    prog = progress_svc.reading_progress(book.page_courante, book.pages)
    return {
        **prog,
        "pace_pages_per_min": round(pace, 3),
        "remaining_minutes": remaining,
    }
