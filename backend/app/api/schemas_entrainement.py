"""Schémas Pydantic pour les endpoints `/entrainement/...` — CONV 7."""

from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Exercice
# ─────────────────────────────────────────────────────────────────────────────

class ExerciceBase(BaseModel):
    nom: str
    categorie: str
    muscles: list[str] = Field(default_factory=list)
    type_mouvement: str = "compose"
    unilateral: bool = False
    note: Optional[str] = None


class ExerciceCreate(ExerciceBase):
    source: str = "manual"


class ExerciceUpdate(BaseModel):
    nom: Optional[str] = None
    categorie: Optional[str] = None
    muscles: Optional[list[str]] = None
    type_mouvement: Optional[str] = None
    unilateral: Optional[bool] = None
    note: Optional[str] = None


class ExerciceRead(ExerciceBase):
    id: int
    source: str

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Programme
# ─────────────────────────────────────────────────────────────────────────────

class ProgrammeJourRead(BaseModel):
    id: int
    weekday: int
    label: str
    slots: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ProgrammeJourUpdate(BaseModel):
    label: Optional[str] = None
    slots: Optional[list[dict[str, Any]]] = None


class ProgrammeRead(BaseModel):
    id: int
    nom: str
    description: Optional[str] = None
    actif: bool
    jours: list[ProgrammeJourRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ProgrammeUpdate(BaseModel):
    nom: Optional[str] = None
    description: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# SetSerie + Seance
# ─────────────────────────────────────────────────────────────────────────────

class SetSerieRead(BaseModel):
    id: int
    seance_id: int
    exercice_id: int
    ordre: int
    reps: int
    poids_kg: float
    rpe: Optional[float] = None
    echec: bool = False

    model_config = {"from_attributes": True}


class SetSerieCreate(BaseModel):
    exercice_id: int
    reps: int
    poids_kg: float
    rpe: Optional[float] = None
    echec: bool = False
    ordre: Optional[int] = None


class SetSerieUpdate(BaseModel):
    reps: Optional[int] = None
    poids_kg: Optional[float] = None
    rpe: Optional[float] = None
    echec: Optional[bool] = None
    ordre: Optional[int] = None


class SeanceCreate(BaseModel):
    date: dt.datetime = Field(default_factory=dt.datetime.utcnow)
    type: Optional[str] = None
    duree_min: Optional[int] = None
    note: Optional[str] = None
    programme_jour_id: Optional[int] = None
    intensite: Optional[str] = None
    source: str = "manual"
    sets: list[SetSerieCreate] = Field(default_factory=list)


class SeanceUpdate(BaseModel):
    type: Optional[str] = None
    duree_min: Optional[int] = None
    note: Optional[str] = None
    programme_jour_id: Optional[int] = None
    intensite: Optional[str] = None


class SeanceRead(BaseModel):
    id: int
    date: dt.datetime
    type: Optional[str]
    duree_min: Optional[int]
    note: Optional[str]
    programme_jour_id: Optional[int]
    intensite: Optional[str]
    source: str
    sets: list[SetSerieRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Progression / 1RM
# ─────────────────────────────────────────────────────────────────────────────

class ProgressionPointOut(BaseModel):
    date: dt.date
    best_1rm_kg: float
    volume_kg: float
    top_set_kg: float
    nb_sets: int


class ProgressionResponse(BaseModel):
    exercice_id: int
    nom: str
    points: list[ProgressionPointOut]
    current_1rm_kg: float
    best_1rm_kg: float
    delta_4w_pct: Optional[float] = None


class OneRMResponse(BaseModel):
    exercice_id: int
    nom: str
    current_1rm_kg: float
    formula: str = "epley"


# ─────────────────────────────────────────────────────────────────────────────
# Cardio
# ─────────────────────────────────────────────────────────────────────────────

class CourseCardioRead(BaseModel):
    id: int
    date: dt.date
    distance_km: float
    duree_sec: int
    pace_sec_per_km: Optional[float] = None
    pace_str: Optional[str] = None
    note: Optional[str] = None
    source: str

    model_config = {"from_attributes": True}


class CourseCardioCreate(BaseModel):
    date: dt.date = Field(default_factory=dt.date.today)
    distance_km: float
    duree_sec: int
    note: Optional[str] = None
    source: str = "manual"


# ─────────────────────────────────────────────────────────────────────────────
# Intensité (contrat figé avec Santé)
# ─────────────────────────────────────────────────────────────────────────────

class IntensityResponse(BaseModel):
    """Contrat strict cf. PLAN.md note 11 + CONV7_entrainement.md."""

    date: dt.date
    intensity: str  # "none" | "low" | "medium" | "high"
