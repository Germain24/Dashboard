"""Modèles Garde-robe — vêtements et historique de tenues."""

import datetime as dt
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class Vetement(SQLModel, table=True):
    __tablename__ = "vetement"

    id: str = Field(primary_key=True)
    nom: str
    marque: Optional[str] = None
    categorie: str
    sous_categorie: Optional[str] = None
    matiere: Optional[str] = None
    couleur: Optional[str] = None
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    etat_propre: Optional[float] = None  # % propreté
    usure_max: Optional[float] = None
    portes: int = 0
    impermeable: bool = False
    # Listes / dicts arbitraires (styles, tags…)
    style: Optional[list] = Field(default=None, sa_column=Column(JSON))
    extra: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
    updated_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)


class TenueHistory(SQLModel, table=True):
    __tablename__ = "tenue_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: dt.datetime = Field(index=True)
    tenue: dict = Field(sa_column=Column(JSON))  # {Manteau: nom, Haut: nom, ...}
    ids: dict = Field(sa_column=Column(JSON))    # {Manteau: id, Haut: id, ...}
    note: Optional[str] = None
