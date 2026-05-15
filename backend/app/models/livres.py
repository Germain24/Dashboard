"""Modèle Livres (vide en CONV 1, rempli en CONV 11)."""

import datetime as dt
from typing import Optional

from sqlmodel import Field, SQLModel


class Livre(SQLModel, table=True):
    __tablename__ = "livre"

    id: Optional[int] = Field(default=None, primary_key=True)
    titre: str
    auteur: Optional[str] = None
    statut: str = "à_lire"  # à_lire | en_cours | lu | abandonné
    pages: Optional[int] = None
    note: Optional[float] = None       # /5
    date_debut: Optional[dt.date] = None
    date_fin: Optional[dt.date] = None
    commentaire: Optional[str] = None
