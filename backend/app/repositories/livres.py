"""Repositories du module Livres."""
from __future__ import annotations

from app.core.repository import Repository
from app.models.livres import Book, BookNote, BookQuote, ReadingSession


class BookRepository(Repository[Book]):
    model = Book


class BookNoteRepository(Repository[BookNote]):
    model = BookNote


class BookQuoteRepository(Repository[BookQuote]):
    model = BookQuote


class ReadingSessionRepository(Repository[ReadingSession]):
    model = ReadingSession
