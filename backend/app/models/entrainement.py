"""Modèles Entraînement (sport, prise de muscle) — CONV 7."""

import datetime as dt
from app.core.timeutil import utcnow
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class Exercice(SQLModel, table=True):
    __tablename__ = "exercice"

    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str = Field(unique=True, index=True)
    categorie: str = Field(index=True)
    muscles: list = Field(default_factory=list, sa_column=Column(JSON))
    type_mouvement: str = "compose"
    unilateral: bool = False
    source: str = "seed"
    note: Optional[str] = None
    created_at: dt.datetime = Field(default_factory=utcnow)


class Programme(SQLModel, table=True):
    __tablename__ = "programme"

    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str = Field(default="PPL/UL")
    description: Optional[str] = None
    actif: bool = Field(default=True, index=True)
    created_at: dt.datetime = Field(default_factory=utcnow)
    updated_at: dt.datetime = Field(default_factory=utcnow)


class ProgrammeJour(SQLModel, table=True):
    __tablename__ = "programme_jour"

    id: Optional[int] = Field(default=None, primary_key=True)
    programme_id: int = Field(foreign_key="programme.id", index=True)
    weekday: int = Field(index=True)
    label: str = "Repos"
    slots: list = Field(default_factory=list, sa_column=Column(JSON))


class Seance(SQLModel, table=True):
    __tablename__ = "seance"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: dt.datetime = Field(index=True)
    type: Optional[str] = None
    exercices: Optional[list] = Field(default=None, sa_column=Column(JSON))
    duree_min: Optional[int] = None
    note: Optional[str] = None
    programme_jour_id: Optional[int] = Field(default=None, foreign_key="programme_jour.id")
    intensite: Optional[str] = None
    source: str = "manual"


class SetSerie(SQLModel, table=True):
    __tablename__ = "set_serie"

    id: Optional[int] = Field(default=None, primary_key=True)
    seance_id: int = Field(foreign_key="seance.id", index=True)
    exercice_id: int = Field(foreign_key="exercice.id", index=True)
    ordre: int = 0
    reps: int
    poids_kg: float
    rpe: Optional[float] = None
    echec: bool = False


class CourseCardio(SQLModel, table=True):
    __tablename__ = "course_cardio"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: dt.date = Field(index=True)
    distance_km: float
    duree_sec: int
    note: Optional[str] = None
    source: str = "manual"
    created_at: dt.datetime = Field(default_factory=utcnow)
