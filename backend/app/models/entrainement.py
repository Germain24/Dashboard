"""Modèle Entraînement (vide en CONV 1, rempli en CONV 7)."""

import datetime as dt
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class Seance(SQLModel, table=True):
    __tablename__ = "seance"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: dt.datetime = Field(index=True)
    type: Optional[str] = None  # "push", "pull", "jambes", "cardio"...
    exercices: Optional[list] = Field(default=None, sa_column=Column(JSON))
    duree_min: Optional[int] = None
    note: Optional[str] = None
