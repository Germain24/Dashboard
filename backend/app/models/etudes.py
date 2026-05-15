"""Modèle Études (vide en CONV 1, rempli en CONV 6)."""

import datetime as dt
from typing import Optional

from sqlmodel import Field, SQLModel


class Etude(SQLModel, table=True):
    __tablename__ = "etude"

    id: Optional[int] = Field(default=None, primary_key=True)
    matiere: str
    sujet: str
    date: dt.date = Field(index=True)
    duree_min: Optional[int] = None
    note: Optional[str] = None
