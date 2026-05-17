"""Schémas Pydantic pour les endpoints `/sante/...` — CONV 3."""

from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# MesureSante
# ─────────────────────────────────────────────────────────────────────────────

class MesureSanteBase(BaseModel):
    date: dt.date
    poids: Optional[float] = None
    photo_url: Optional[str] = None
    note: Optional[str] = None
    extra: Optional[dict[str, Any]] = None


class MesureSanteCreate(MesureSanteBase):
    pass


class MesureSanteUpdate(BaseModel):
    poids: Optional[float] = None
    photo_url: Optional[str] = None
    note: Optional[str] = None
    extra: Optional[dict[str, Any]] = None


class MesureSanteRead(MesureSanteBase):
    id: int

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Aliment
# ─────────────────────────────────────────────────────────────────────────────

class AlimentRead(BaseModel):
    id: int
    nom: str
    proprietes: dict[str, Any]

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# NutritionGoal
# ─────────────────────────────────────────────────────────────────────────────

class NutritionGoalRead(BaseModel):
    id: int
    date_set: dt.date
    poids_cible: Optional[float] = None
    body_fat_target_pct: Optional[float] = None
    date_cible: Optional[dt.date] = None
    type: str
    surplus_kcal_sport: float
    rest_factor: float
    sport_days: list[int]
    actif: bool
    note: Optional[str] = None

    model_config = {"from_attributes": True}


class NutritionGoalUpdate(BaseModel):
    poids_cible: Optional[float] = None
    body_fat_target_pct: Optional[float] = None
    date_cible: Optional[dt.date] = None
    type: Optional[str] = None
    surplus_kcal_sport: Optional[float] = None
    rest_factor: Optional[float] = None
    sport_days: Optional[list[int]] = None
    note: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Targets
# ─────────────────────────────────────────────────────────────────────────────

class TargetsResponse(BaseModel):
    date: dt.date
    poids: float
    intensity: str
    intensity_was_default: bool
    base_targets: dict[str, float]
    targets: dict[str, float]  # compensés J-1


# ─────────────────────────────────────────────────────────────────────────────
# Plan
# ─────────────────────────────────────────────────────────────────────────────

class PlanGenerateRequest(BaseModel):
    date: Optional[dt.date] = Field(
        default=None,
        description="Date du plan (défaut : aujourd'hui).",
    )
    poids: Optional[float] = Field(
        default=None,
        description="Poids du jour ; si absent, on prend la dernière MesureSante.",
    )
    intensity: Optional[str] = Field(
        default=None,
        description="none / low / medium / high ; si absent, défaut date-based.",
    )
    budget_max_daily: Optional[float] = Field(
        default=None,
        description="Budget CAD/jour ; défaut 18 CAD (legacy).",
    )
    force: bool = Field(
        default=False,
        description="Régénère même si un plan existe déjà pour cette date.",
    )


class PlanItem(BaseModel):
    """Une ligne du plan : nom, quantité, contributions macros."""

    aliment: str
    quantite_g: float
    quantite_str: str
    calories: float
    proteines: float
    lipides: float
    glucides: float
    prix: float


class PlanResponse(BaseModel):
    date: dt.date
    poids_used: float
    intensite: str
    intensity_was_default: bool
    base_targets: dict[str, float]
    targets: dict[str, float]
    items: list[PlanItem]
    totals: dict[str, float]
    warning: Optional[str] = None
    budget_max_daily: float


class PlanPatchRequest(BaseModel):
    """Modification manuelle du plan : remplace les quantités par celles fournies.

    Si `quantites` est fourni, il REMPLACE intégralement le plan courant
    (clé = nom d'aliment, valeur = grammes). `consumed` met à jour la
    consommation réelle pour la compensation J-1.
    """

    quantites: Optional[dict[str, float]] = None
    consumed: Optional[dict[str, float]] = None
    warning: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Projection
# ─────────────────────────────────────────────────────────────────────────────

class WeightTrendOut(BaseModel):
    days: int
    slope_kg_per_day: float
    slope_kg_per_week: float
    last_weight: float
    samples: int


class ProjectionResponse(BaseModel):
    target_weight: float
    current_weight: float
    delta_kg: float
    days_to_target: Optional[int] = None
    target_date: Optional[dt.date] = None
    slope_kg_per_week: float
    confidence: str
    note: str
    trend_7d: Optional[WeightTrendOut] = None
    trend_30d: Optional[WeightTrendOut] = None
