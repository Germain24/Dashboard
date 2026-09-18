"""Modèles Garde-robe — vêtements et historique de tenues."""

import datetime as dt
from app.core.timeutil import utcnow
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
    type_objectif: Optional[str] = None  # relie la pièce à un ObjectifType.nom
    image: Optional[str] = None  # chemin relatif sous assets/, ex. "Haut/xxx.png"
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    etat_propre: Optional[float] = None  # % propreté
    usure_max: Optional[float] = None
    portes: int = 0
    impermeable: bool = False
    # Listes / dicts arbitraires (styles, tags…)
    style: Optional[list] = Field(default=None, sa_column=Column(JSON))
    extra: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    created_at: dt.datetime = Field(default_factory=utcnow)
    updated_at: dt.datetime = Field(default_factory=utcnow)


class TenueHistory(SQLModel, table=True):
    __tablename__ = "tenue_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: dt.datetime = Field(index=True)
    tenue: dict = Field(sa_column=Column(JSON))  # {Manteau: nom, Haut: nom, ...}
    ids: dict = Field(sa_column=Column(JSON))    # {Manteau: id, Haut: id, ...}
    note: Optional[str] = None


class ObjectifType(SQLModel, table=True):
    """Cache de l'objectif garde-robe (master = data/imports/Vetements.xlsx).

    Écrasé à chaque POST /garderobe/objectif/sync.
    """

    __tablename__ = "objectif_type"

    nom: str = Field(primary_key=True)
    ordre: int = 0
    quantite_objectif: int = 0
    echelle: list = Field(default_factory=list, sa_column=Column(JSON))
