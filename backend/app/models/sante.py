"""Modèles Santé / Nutrition — CONV 3.

Notes :
- `dt.date` plutôt que `date` à cause du clash Pydantic 2 / SQLModel.
- `MesureSante.extra` reste un JSON libre pour stocker tout indicateur futur.
- `PlanNutrition` stocke à la fois les targets *de base* et les *compensés*.
- `NutritionGoal` est un singleton logique : on lit toujours `actif=True`.
"""

import datetime as dt
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class MesureSante(SQLModel, table=True):
    __tablename__ = "mesure_sante"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: dt.date = Field(index=True, unique=True)
    poids: Optional[float] = None
    photo_url: Optional[str] = None
    note: Optional[str] = None
    extra: Optional[dict] = Field(default=None, sa_column=Column(JSON))


class PlanNutrition(SQLModel, table=True):
    __tablename__ = "plan_nutrition"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: dt.date = Field(index=True, unique=True)
    poids_used: Optional[float] = None
    intensite: Optional[str] = None
    base_targets: dict = Field(default_factory=dict, sa_column=Column(JSON))
    targets: dict = Field(default_factory=dict, sa_column=Column(JSON))
    quantites: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    totals: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    consumed: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    warning: Optional[str] = None
    extra: Optional[dict] = Field(default=None, sa_column=Column(JSON))


class Aliment(SQLModel, table=True):
    __tablename__ = "aliment"

    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str = Field(unique=True, index=True)
    proprietes: dict = Field(sa_column=Column(JSON))


class NutritionGoal(SQLModel, table=True):
    __tablename__ = "nutrition_goal"

    id: Optional[int] = Field(default=None, primary_key=True)
    date_set: dt.date = Field(default_factory=dt.date.today, index=True)
    poids_cible: Optional[float] = None
    body_fat_target_pct: Optional[float] = None
    date_cible: Optional[dt.date] = None
    type: str = "bulk"
    surplus_kcal_sport: float = 500.0
    rest_factor: float = 1.1
    sport_days: list = Field(
        default_factory=lambda: [0, 1, 2, 4, 5],
        sa_column=Column(JSON),
    )
    actif: bool = Field(default=True, index=True)
    note: Optional[str] = None
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
    updated_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
