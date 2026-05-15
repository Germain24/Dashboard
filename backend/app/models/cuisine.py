"""Modèle Cuisine (vide en CONV 1, rempli en CONV 9)."""

from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class Recette(SQLModel, table=True):
    __tablename__ = "recette"

    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str
    ingredients: Optional[list] = Field(default=None, sa_column=Column(JSON))
    etapes: Optional[list] = Field(default=None, sa_column=Column(JSON))
    portions: Optional[int] = None
    duree_min: Optional[int] = None
    tags: Optional[list] = Field(default=None, sa_column=Column(JSON))
