import datetime as dt
from sqlmodel import SQLModel, Field

class Book(SQLModel, table=True):
    __tablename__ = "book"
    id: int | None = Field(default=None, primary_key=True)
    titre: str
    auteur: str = ""
    isbn: str | None = None
    pages: int | None = None
    statut: str = "a_lire"
    genre: str = ""
    format: str = "papier"
    note: float | None = None
    page_courante: int | None = None
    date_debut: dt.date | None = None
    date_fin: dt.date | None = None
    couverture_url: str | None = None
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)

class BookNote(SQLModel, table=True):
    __tablename__ = "book_note"
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id")
    page: int | None = None
    contenu: str
    tags: str = "[]"

class BookQuote(SQLModel, table=True):
    __tablename__ = "book_quote"
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id")
    page: int | None = None
    texte: str

class ReadingSession(SQLModel, table=True):
    __tablename__ = "reading_session"
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id")
    date: dt.date
    duree_minutes: int
    page_debut: int | None = None
    page_fin: int | None = None
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
