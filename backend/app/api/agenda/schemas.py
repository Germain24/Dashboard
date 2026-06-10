"""Schémas Pydantic entrée/sortie pour le module Agenda (CONV 5)."""

from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


# ── RegleRecurrence ─────────────────────────────────────────────────────────

class RegleRecurrenceCreate(BaseModel):
    titre: str
    weekdays: list[int] = Field(..., description="0=Lun…6=Dim")
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    lieu: Optional[str] = None
    description: Optional[str] = None
    categorie: Optional[str] = None
    couleur: Optional[str] = None
    until: Optional[dt.date] = None


class RegleRecurrenceUpdate(BaseModel):
    titre: Optional[str] = None
    weekdays: Optional[list[int]] = None
    start_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    end_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    lieu: Optional[str] = None
    description: Optional[str] = None
    categorie: Optional[str] = None
    couleur: Optional[str] = None
    until: Optional[dt.date] = None


class RegleRecurrenceRead(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    titre: str
    weekdays: list[int]
    start_time: str
    end_time: str
    lieu: Optional[str] = None
    description: Optional[str] = None
    categorie: Optional[str] = None
    couleur: Optional[str] = None
    until: Optional[dt.date] = None
    created_at: dt.datetime


# ── Evenement ───────────────────────────────────────────────────────────────

class EvenementCreate(BaseModel):
    titre: str
    debut: dt.datetime
    fin: Optional[dt.datetime] = None
    lieu: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = "manuel"
    source_id: Optional[str] = None
    categorie: Optional[str] = None
    couleur: Optional[str] = None
    recurrence_id: Optional[int] = None


class EvenementUpdate(BaseModel):
    titre: Optional[str] = None
    debut: Optional[dt.datetime] = None
    fin: Optional[dt.datetime] = None
    lieu: Optional[str] = None
    description: Optional[str] = None
    categorie: Optional[str] = None
    couleur: Optional[str] = None


class EvenementRead(BaseModel):
    model_config = {"from_attributes": True}
    id: Optional[int]                      # None = occurrence virtuelle
    titre: str
    debut: dt.datetime
    fin: Optional[dt.datetime]
    lieu: Optional[str]
    description: Optional[str]
    source: Optional[str]
    source_id: Optional[str]
    categorie: Optional[str]
    couleur: Optional[str]
    recurrence_id: Optional[int]
    is_virtual: bool = False


# ── Tache ────────────────────────────────────────────────────────────────────

class TacheCreate(BaseModel):
    titre: str
    deadline: Optional[dt.date] = None
    priorite: int = Field(default=3, ge=1, le=5)
    duree_estimee_min: Optional[int] = None
    note: Optional[str] = None
    categorie: Optional[str] = None


class TacheUpdate(BaseModel):
    titre: Optional[str] = None
    deadline: Optional[dt.date] = None
    priorite: Optional[int] = Field(None, ge=1, le=5)
    statut: Optional[str] = None
    duree_estimee_min: Optional[int] = None
    note: Optional[str] = None
    categorie: Optional[str] = None


class TacheRead(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    titre: str
    deadline: Optional[dt.date]
    priorite: int
    statut: str
    duree_estimee_min: Optional[int]
    note: Optional[str]
    categorie: Optional[str]
    source: Optional[str]
    created_at: dt.datetime


# ── Vues agrégées ────────────────────────────────────────────────────────────

class SlotLibre(BaseModel):
    debut: dt.datetime
    fin: dt.datetime
    duree_min: int


class AgendaJourResponse(BaseModel):
    """Vue Jour : événements + séance entraînement + slots libres + tâches urgentes."""
    date: dt.date
    evenements: list[EvenementRead]
    seance_entrainement: Optional[EvenementRead] = None
    slots_libres: list[SlotLibre]
    taches_urgentes: list[TacheRead]   # deadline <= aujourd'hui


class ImportIcalResponse(BaseModel):
    created_events: int
    skipped_duplicates: int
    created_rules: int
