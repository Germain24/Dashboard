"""Schémas du module Budget (extraits de routes_budget.py, #507)."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class TransactionCreate(BaseModel):
    date: dt.date
    montant: float
    marchand: str
    description: str = ""
    compte: str = "principal"
    devise: str = "CAD"
    tags: list[str] = []


class TagsUpdate(BaseModel):
    tags: list[str] = []


class CategoryCreate(BaseModel):
    nom: str
    parent_id: int | None = None
    couleur: str = "#6366f1"


class RuleCreate(BaseModel):
    pattern: str
    category_id: int
    priorite: int = 0


class EnvelopeCreate(BaseModel):
    category_id: int
    mois: str
    montant: float


class ContractCreate(BaseModel):
    nom: str
    categorie: str
    montant: float
    periodicite: str
    date_echeance: str | None = None
    notes: str = ""


class ContractPatch(BaseModel):
    nom: str | None = None
    categorie: str | None = None
    montant: float | None = None
    periodicite: str | None = None
    date_echeance: str | None = None
    statut: str | None = None
    date_resiliation: str | None = None
    notes: str | None = None
