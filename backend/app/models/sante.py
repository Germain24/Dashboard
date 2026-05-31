"""Modèles Santé / Nutrition."""

import datetime as dt
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class MesureSante(SQLModel, table=True):
    """Mesures journalières (poids, mensurations, etc.)."""

    __tablename__ = "mesure_sante"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: dt.date = Field(index=True, unique=True)
    poids: Optional[float] = None
    extra: Optional[dict] = Field(default=None, sa_column=Column(JSON))


class PlanNutrition(SQLModel, table=True):
    """Snapshot d'un plan nutritionnel à une date donnée (targets + repartition)."""

    __tablename__ = "plan_nutrition"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: dt.date = Field(index=True)
    targets: dict = Field(sa_column=Column(JSON))      # {Calories, Protéines, ...}
    quantites: Optional[dict] = Field(default=None, sa_column=Column(JSON))  # {aliment: g/j}
    extra: Optional[dict] = Field(default=None, sa_column=Column(JSON))


class Aliment(SQLModel, table=True):
    """Table des aliments avec leurs propriétés nutritionnelles.

    Le legacy `aliments.csv` est transposé : 1 ligne = 1 aliment, colonnes =
    propriétés (prix, protéines, glucides, vitamines…). On stocke ça en JSON
    pour rester agnostique au schéma exact.
    """

    __tablename__ = "aliment"

    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str = Field(unique=True, index=True)
    proprietes: dict = Field(sa_column=Column(JSON))  # {Prix: x, Proteines: y, ...}


class NutritionGoal(SQLModel, table=True):
    """Objectif nutritionnel actif (poids cible, type de diète, etc.)."""

    __tablename__ = "nutrition_goal"

    id: Optional[int] = Field(default=None, primary_key=True)
    date_set: dt.date = Field(default_factory=dt.date.today, index=True)
    poids_cible: Optional[float] = None
    body_fat_target_pct: Optional[float] = None
    date_cible: Optional[dt.date] = None
    type: str = "maintenance"
    surplus_kcal_sport: float = 0.0
    rest_factor: float = 1.2
    sport_days: Optional[list] = Field(default=None, sa_column=Column(JSON))
    actif: bool = True
    note: Optional[str] = None
