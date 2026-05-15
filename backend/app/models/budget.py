"""Modèle Budget (vide en CONV 1, rempli en CONV 8)."""

import datetime as dt
from typing import Optional

from sqlmodel import Field, SQLModel


class Depense(SQLModel, table=True):
    __tablename__ = "depense"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: dt.date = Field(index=True)
    montant: float
    devise: str = "EUR"
    categorie: Optional[str] = None
    libelle: Optional[str] = None
    moyen_paiement: Optional[str] = None
