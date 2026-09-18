"""Schémas du module Habitudes (extraits de routes_habitudes.py, #501)."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class HabitCreate(BaseModel):
    nom: str
    type: str = "binaire"
    unite: str | None = None
    cible: float = 1.0
    frequence: str = "daily"
    couleur: str | None = None
    icone: str | None = None


class EntryCreate(BaseModel):
    habit_id: int
    date: dt.date
    valeur: float = 1.0
