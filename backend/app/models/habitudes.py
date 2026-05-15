"""Modèle Habitudes (vide en CONV 1, rempli en CONV 10)."""

import datetime as dt
from typing import Optional

from sqlmodel import Field, SQLModel


class Habitude(SQLModel, table=True):
    __tablename__ = "habitude"

    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str = Field(index=True)
    cible_par_semaine: Optional[int] = None
    actif: bool = True


class HabitudeLog(SQLModel, table=True):
    __tablename__ = "habitude_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    habitude_id: int = Field(foreign_key="habitude.id", index=True)
    date: dt.date = Field(index=True)
    fait: bool = True
