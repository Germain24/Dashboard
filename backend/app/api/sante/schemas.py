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
    day_context: Optional[dict[str, Any]] = None


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
    consumed: Optional[dict[str, float]] = None
    warning: Optional[str] = None
    budget_max_daily: float
    day_context: Optional[dict[str, Any]] = None
    pricing_context: Optional[dict[str, Any]] = None


class PlanPatchRequest(BaseModel):
    """Modification manuelle du plan : remplace les quantités par celles fournies.

    - `quantites` : remplace le plan généré (clé = nom d'aliment, valeur = grammes).
    - `consumed` : totaux nutritionnels consommés (clé = nutriment, ex. Calories).
      Utilisé par la compensation J-1.
    - `consumed_grams` : grammes consommés par aliment (clé = nom d'aliment).
      Si fourni, le backend calcule automatiquement les totaux nutritionnels et
      les stocke dans `consumed` (les deux champs sont préservés pour l'UI).
    """

    quantites: Optional[dict[str, float]] = None
    consumed: Optional[dict[str, float]] = None
    consumed_grams: Optional[dict[str, float]] = None
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


# ─────────────────────────────────────────────────────────────────────────────
# Fenêtre batch-cook
# ─────────────────────────────────────────────────────────────────────────────

class FenetreGenerateRequest(BaseModel):
    date: Optional[dt.date] = Field(default=None, description="Un jour de la fenêtre (défaut : aujourd'hui). L'ancre lun/jeu en est dérivée.")
    poids: Optional[float] = Field(default=None, description="Poids ; si absent, dernière MesureSante.")
    force: bool = Field(default=False, description="Régénère (seed aléatoire) même si la fenêtre existe.")
    refresh_prices: bool = Field(
        default=True,
        description="Vérifie et rafraîchit les prix Super C avant l'optimisation.",
    )


class ShoppingItem(BaseModel):
    aliment: str
    quantite_g: float
    prix: Optional[float] = None
    promo: bool = False
    dispo_g: Optional[float] = None       # couvert par le garde-manger
    a_acheter_g: Optional[float] = None   # reste à acheter (besoin − stock)
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    href: Optional[str] = None
    format: Optional[str] = None
    qty: int = 1
    prix_unitaire: Optional[float] = None
    prix_verifie: bool = False


class FenetreDayPlan(BaseModel):
    date: dt.date
    intensite: str
    items: list[PlanItem]
    totals: dict[str, float]
    # Cibles du jour nécessaires pour afficher les macros apport/cible.
    targets: dict[str, float] = Field(default_factory=dict)
    repas_travail: list[dict] = Field(default_factory=list)


class FenetreScore(BaseModel):
    couverture_moyenne: float
    pct_micros_atteints: float
    equilibre_macros: float = 0.0
    equilibre_moyen: float = 0.0
    cout_total: float
    cout_optimise: float = 0.0  # coût économique : stock périssable 0 %, durable 50 %, surplus 100 %
    cout_a_payer: float = 0.0   # estimation à payer après déduction du stock et des formats
    ratio: float
    sous_couverts: list[str]


class WindowPlanResponse(BaseModel):
    anchor_date: dt.date
    #: Jour où l'on fait les courses et où l'on cuisine — lundi pour la fenêtre
    #: lun-mer, mercredi (veille) pour la fenêtre jeu-dim, afin de capter le
    #: rabais étudiant Super C (lun→mer). Dérivé de `anchor_date`, non persisté.
    shopping_date: Optional[dt.date] = None
    length: int
    poids_used: float
    jours: list[FenetreDayPlan]
    shopping_list: list[ShoppingItem]
    score: FenetreScore
    warning: Optional[str] = None


class CartPlanItem(BaseModel):
    aliment: str
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    href: Optional[str] = None
    format: Optional[str] = None
    qty: int
    prix_estime: Optional[float] = None
    a_verifier: bool
    promo: bool = False


class CartPlanResponse(BaseModel):
    anchor_date: dt.date
    items: list[CartPlanItem]
    total_estime: float
