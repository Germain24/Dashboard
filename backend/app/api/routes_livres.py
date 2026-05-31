import datetime as dt
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.core.db import get_session
from app.models.livres import Book, BookNote, BookQuote
from app.services.livres import books as books_svc
from app.services.livres import notes as notes_svc
from app.services.livres import sessions as sessions_svc
from pydantic import BaseModel

router = APIRouter(prefix="/api/livres", tags=["livres"])

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

@router.get("/books")
def list_books(statut: str | None = None, session: Session = Depends(get_session)):
    return books_svc.get_books(session, statut)

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
