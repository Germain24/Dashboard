"""Sous-routeur Livres : bibliothèque (CRUD, recherche, estimation) (#510)."""
from __future__ import annotations
from app.core.timeutil import utcnow

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.livres.schemas import BookCreate
from app.core.db import get_session
from app.models.livres import ReadingSession
from app.repositories.livres import BookRepository
from app.services.livres import books as books_svc
from app.services.livres import metadata as metadata_svc
from app.services.livres import progress as progress_svc

router = APIRouter()


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
    repo = BookRepository(session)
    b = repo.get(id)
    if not b:
        raise HTTPException(404)
    return repo.update(b, body)


@router.delete("/books/{id}", status_code=204)
def delete_book(id: int, session: Session = Depends(get_session)):
    if not BookRepository(session).delete_by_id(id):
        raise HTTPException(404)


@router.post("/sync-from-json")
def sync_from_json(session: Session = Depends(get_session)):
    """Synchronise la bibliothèque depuis data/mes_livres.json (upsert par titre).

    Équivalent à relancer scripts/seed_mes_livres.py depuis l'interface.
    """
    import datetime as dt
    import json
    from app.core.config import settings as _settings

    path = _settings.data_dir / "mes_livres.json"
    if not path.exists():
        raise HTTPException(404, detail=f"Fichier introuvable : {path}")
    try:
        livres = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(400, detail=f"JSON invalide : {e}")

    UPDATABLE = ["auteur", "isbn", "pages", "genre", "langue", "couverture_url"]
    existing = {b.titre: b for b in session.exec(select(books_svc.Book)).all()}
    added = updated = 0
    for data in livres:
        titre = data.get("titre", "").strip()
        if not titre:
            continue
        if titre in existing:
            book = existing[titre]
            changed = [f for f in UPDATABLE if data.get(f) is not None and getattr(book, f) != data[f]]
            for f in changed:
                setattr(book, f, data[f])
            if changed:
                session.add(book)
                updated += 1
        else:
            session.add(books_svc.Book(
                titre=titre,
                auteur=data.get("auteur", ""),
                isbn=data.get("isbn"),
                pages=data.get("pages"),
                genre=data.get("genre", ""),
                langue=data.get("langue", ""),
                statut=data.get("statut", "a_lire"),
                couverture_url=data.get("couverture_url"),
                created_at=utcnow(),
            ))
            added += 1
    session.commit()
    return {"added": added, "updated": updated, "source": str(path)}


@router.get("/books/{id}/estimate")
def estimate(id: int, session: Session = Depends(get_session)):
    """Temps de lecture restant estimé selon le rythme (#150)."""
    book = BookRepository(session).get(id)
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
