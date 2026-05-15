"""Modèle Agenda (vide en CONV 1, rempli en CONV 5)."""

import datetime as dt
from typing import Optional

from sqlmodel import Field, SQLModel


class Evenement(SQLModel, table=True):
    __tablename__ = "evenement"

    id: Optional[int] = Field(default=None, primary_key=True)
    titre: str
    debut: dt.datetime = Field(index=True)
    fin: Optional[dt.datetime] = None
    lieu: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None  # ex: "google", "manuel", "ical"
    source_id: Optional[str] = None
