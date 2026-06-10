"""Schémas du module Livres (extraits de routes_livres.py, #510)."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


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
