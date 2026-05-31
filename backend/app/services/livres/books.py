from sqlmodel import Session, select
from app.models.livres import Book
from app.services.livres.metadata import lookup_isbn

def create_book(session: Session, **kwargs) -> Book:
    book = Book(**kwargs)
    session.add(book)
    session.commit()
    session.refresh(book)
    return book

def create_book_from_isbn(session: Session, isbn: str) -> Book | None:
    meta = lookup_isbn(isbn)
    if not meta:
        return None
    return create_book(session, isbn=isbn, **meta)

def get_books(session: Session, statut: str | None = None) -> list[Book]:
    q = select(Book)
    if statut:
        q = q.where(Book.statut == statut)
    return session.exec(q.order_by(Book.created_at.desc())).all()

def get_stats(session: Session) -> dict:
    books = session.exec(select(Book)).all()
    lus = [b for b in books if b.statut == "lu"]
    pages_lues = sum(b.pages or 0 for b in lus)
    par_genre: dict[str, int] = {}
    for b in lus:
        g = b.genre or "Autre"
        par_genre[g] = par_genre.get(g, 0) + 1
    return {"total_lus": len(lus), "pages_lues": pages_lues, "par_genre": par_genre}
