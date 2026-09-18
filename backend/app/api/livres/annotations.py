"""Sous-routeur Livres : notes, citations, sessions de lecture (#510)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.livres.schemas import NoteCreate, QuoteCreate, SessionCreate
from app.core.db import get_session
from app.repositories.livres import BookNoteRepository, BookQuoteRepository
from app.services.livres import notes as notes_svc
from app.services.livres import sessions as sessions_svc

router = APIRouter()


@router.get("/books/{id}/notes")
def get_notes(id: int, session: Session = Depends(get_session)):
    return notes_svc.get_notes(session, id)


@router.post("/books/{id}/notes", status_code=201)
def create_note(id: int, body: NoteCreate, session: Session = Depends(get_session)):
    return notes_svc.create_note(session, id, body.contenu, body.page, body.tags)


@router.patch("/notes/{id}")
def update_note(id: int, body: dict, session: Session = Depends(get_session)):
    repo = BookNoteRepository(session)
    n = repo.get(id)
    if not n:
        raise HTTPException(404)
    return repo.update(n, body)


@router.delete("/notes/{id}", status_code=204)
def delete_note(id: int, session: Session = Depends(get_session)):
    if not BookNoteRepository(session).delete_by_id(id):
        raise HTTPException(404)


@router.get("/books/{id}/quotes")
def get_quotes(id: int, session: Session = Depends(get_session)):
    return notes_svc.get_quotes(session, id)


@router.post("/books/{id}/quotes", status_code=201)
def create_quote(id: int, body: QuoteCreate, session: Session = Depends(get_session)):
    return notes_svc.create_quote(session, id, body.texte, body.page)


@router.delete("/quotes/{id}", status_code=204)
def delete_quote(id: int, session: Session = Depends(get_session)):
    if not BookQuoteRepository(session).delete_by_id(id):
        raise HTTPException(404)


@router.post("/books/{id}/sessions", status_code=201)
def create_reading_session(id: int, body: SessionCreate, session: Session = Depends(get_session)):
    return sessions_svc.create_session(session, id, body.date, body.duree_minutes,
                                       body.page_debut, body.page_fin)
