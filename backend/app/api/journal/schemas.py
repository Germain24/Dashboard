"""Schémas du module Journal (extraits de routes_journal.py, #509)."""
from __future__ import annotations

from pydantic import BaseModel


class MoodEntryIn(BaseModel):
    humeur: int
    energie: int
    tags: list[str] = []
    note: str = ""
