"""Schémas du module Données (extraits de routes_data.py, #513)."""
from __future__ import annotations

from pydantic import BaseModel


class ImportRequest(BaseModel):
    data: dict
    mode: str = "replace"  # "replace" | "merge"
