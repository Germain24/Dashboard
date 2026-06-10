"""Schemas Pydantic (in/out) pour le module Études."""

from __future__ import annotations

import datetime as dt
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ───────────────────────────── Cours ─────────────────────────────

class CoursCreate(BaseModel):
    code: str
    nom: str
    semestre: str
    credits: int = 3
    prof: Optional[str] = None
    local: Optional[str] = None
    note: Optional[str] = None


class CoursPatch(BaseModel):
    code: Optional[str] = None
    nom: Optional[str] = None
    semestre: Optional[str] = None
    credits: Optional[int] = None
    prof: Optional[str] = None
    local: Optional[str] = None
    note_finale: Optional[float] = None
    actif: Optional[bool] = None
    note: Optional[str] = None


class CoursRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    nom: str
    semestre: str
    credits: int
    prof: Optional[str]
    local: Optional[str]
    note_finale: Optional[float]
    actif: bool
    note: Optional[str]
    created_at: dt.datetime
    updated_at: dt.datetime

    # Champs calculés injectés par la route
    lettre: Optional[str] = None
    points_gpa: Optional[float] = None
    total_minutes_etude: Optional[int] = None


# ───────────────────────────── Evaluation ────────────────────────

class EvaluationCreate(BaseModel):
    cours_id: int
    titre: str
    type_eval: str = "autre"
    date_limite: Optional[dt.date] = None
    note_obtenue: Optional[float] = None
    note_max: Optional[float] = 100
    note: Optional[str] = None


class EvaluationPatch(BaseModel):
    titre: Optional[str] = None
    type_eval: Optional[str] = None
    date_limite: Optional[dt.date] = None
    note_obtenue: Optional[float] = None
    note_max: Optional[float] = None
    note: Optional[str] = None


class EvaluationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cours_id: int
    titre: str
    type_eval: str
    date_limite: Optional[dt.date]
    note_obtenue: Optional[float]
    note_max: Optional[float]
    note: Optional[str]
    created_at: dt.datetime
    updated_at: dt.datetime

    # Champs calculés
    jours_restants: Optional[int] = None


# ───────────────────────────── SessionEtude ──────────────────────

class SessionCreate(BaseModel):
    cours_id: Optional[int] = None
    date: Optional[dt.date] = None
    duree_min: int
    sujet: Optional[str] = None
    note: Optional[str] = None


class SessionPatch(BaseModel):
    cours_id: Optional[int] = None
    date: Optional[dt.date] = None
    duree_min: Optional[int] = None
    sujet: Optional[str] = None
    note: Optional[str] = None


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cours_id: Optional[int]
    date: dt.date
    duree_min: int
    sujet: Optional[str]
    note: Optional[str]
    created_at: dt.datetime


# ───────────────────────────── GPA ───────────────────────────────

class CoursGradeRead(BaseModel):
    cours_id: int
    code: str
    nom: str
    semestre: str
    note_finale: Optional[float]
    lettre: Optional[str]
    points_gpa: Optional[float]


class GpaRead(BaseModel):
    semestre: Optional[str]
    nb_cours: int
    nb_cours_notes: int
    gpa: Optional[float]
    detail: list[CoursGradeRead]
