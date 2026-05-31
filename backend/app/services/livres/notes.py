import json
from sqlmodel import Session, select
from app.models.livres import BookNote, BookQuote

def get_notes(session: Session, book_id: int) -> list[BookNote]:
    return session.exec(select(BookNote).where(BookNote.book_id == book_id)).all()

def create_note(session: Session, book_id: int, contenu: str,
                page: int | None = None, tags: list[str] | None = None) -> BookNote:
    note = BookNote(book_id=book_id, contenu=contenu, page=page, tags=json.dumps(tags or []))
    session.add(note)
    session.commit()
    session.refresh(note)
    return note

def get_quotes(session: Session, book_id: int) -> list[BookQuote]:
    return session.exec(select(BookQuote).where(BookQuote.book_id == book_id)).all()

def create_quote(session: Session, book_id: int, texte: str, page: int | None = None) -> BookQuote:
    q = BookQuote(book_id=book_id, texte=texte, page=page)
    session.add(q)
    session.commit()
    session.refresh(q)
    return q
