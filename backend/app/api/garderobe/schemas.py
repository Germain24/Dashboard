"""Schémas Pydantic pour les endpoints `/garderobe/...`."""

from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Vetement
# ─────────────────────────────────────────────────────────────────────────────

class VetementBase(BaseModel):
    nom: str
    marque: Optional[str] = None
    categorie: str
    sous_categorie: Optional[str] = None
    matiere: Optional[str] = None
    couleur: Optional[str] = None
    type_objectif: Optional[str] = None
    image: Optional[str] = None
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    etat_propre: Optional[float] = None
    usure_max: Optional[float] = None
    portes: int = 0
    impermeable: bool = False
    style: Optional[list] = None
    extra: Optional[dict] = None


class VetementRead(VetementBase):
    id: str

    # Champs dérivés (calculés à la lecture)
    proprete_pct: float
    vie_pct: float
    needs_wash: bool
    is_worn_out: bool
    ports_avant_lavage: int
    thermal_score: float
    saison: str = "toutes"
    entretien: Optional[dict] = None  # consigne de lavage dérivée de la matière (#81)

    model_config = {"from_attributes": True}


class VetementCreate(VetementBase):
    id: str  # imposé par le user (slug)


class VetementUpdate(BaseModel):
    nom: Optional[str] = None
    marque: Optional[str] = None
    categorie: Optional[str] = None
    sous_categorie: Optional[str] = None
    matiere: Optional[str] = None
    couleur: Optional[str] = None
    type_objectif: Optional[str] = None
    image: Optional[str] = None
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    etat_propre: Optional[float] = None
    usure_max: Optional[float] = None
    portes: Optional[int] = None
    impermeable: Optional[bool] = None
    style: Optional[list] = None
    extra: Optional[dict] = None


# ─────────────────────────────────────────────────────────────────────────────
# Météo
# ─────────────────────────────────────────────────────────────────────────────

class HourlyTempOut(BaseModel):
    hour: int
    temp: float
    apparent_temp: float


class WeatherOut(BaseModel):
    temp: float
    feels: float
    temp_min: float
    temp_max: float
    humidity: float
    wind: float
    precip: float
    desc: str
    icon: str
    source: str
    pluie: bool
    snow: bool
    mean_window_temp: float
    hour_window: list[int]
    hourly: list[HourlyTempOut]


# ─────────────────────────────────────────────────────────────────────────────
# Suggestion de tenue
# ─────────────────────────────────────────────────────────────────────────────

class SuggestRequest(BaseModel):
    """Optionnel : permet de forcer une cible thermique ou la pluie."""

    mean_temp: Optional[float] = Field(
        default=None,
        description="Si fourni, override la moyenne 7h-23h. Sinon, calculée depuis la météo.",
    )
    rain: Optional[bool] = Field(
        default=None,
        description="Si fourni, override la détection pluie. Sinon, depuis la météo.",
    )


class OutfitSlotOut(BaseModel):
    slot_id: str
    vetement: Optional[VetementRead] = None


class SuggestResponse(BaseModel):
    slots: list[OutfitSlotOut]
    use_body: bool
    target_thermal: float
    total_thermal: float
    style_score: float
    mean_temp: float
    weather: WeatherOut


# ─────────────────────────────────────────────────────────────────────────────
# Validation d'une tenue
# ─────────────────────────────────────────────────────────────────────────────

class ValiderRequest(BaseModel):
    """Clés = slot_id (Manteau, Veste, …), valeurs = id du vêtement (str) ou null."""

    tenue: dict[str, Optional[str]]
    use_body: bool = False
    note: Optional[str] = None


class ValiderItemUpdate(BaseModel):
    id: str
    nom: str
    portes: int
    needs_wash: bool
    ports_avant_lavage: int
    vie_pct: float


class ValiderResponse(BaseModel):
    history_id: int
    updates: list[ValiderItemUpdate]


# ─────────────────────────────────────────────────────────────────────────────
# History
# ─────────────────────────────────────────────────────────────────────────────

class TenueHistoryOut(BaseModel):
    id: int
    date: dt.datetime
    tenue: dict[str, Optional[str]]   # slot → nom
    ids: dict[str, Optional[str]]     # slot → id
    note: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Stats
# ─────────────────────────────────────────────────────────────────────────────

class CountEntry(BaseModel):
    label: str
    count: int


class StatsResponse(BaseModel):
    total: int
    par_categorie: list[CountEntry]
    par_couleur: list[CountEntry]
    par_style: list[CountEntry]
    a_laver: list[VetementRead]
    hs: list[VetementRead]
    color_ratio: dict[str, float]   # {Neutre: 0.6, Secondaire: 0.3, Accent: 0.1}
    valeur_estimee: float = 0.0     # somme des prix connus (extra.prix), #80
    valeur_count: int = 0           # nb de pièces avec un prix renseigné


# ─────────────────────────────────────────────────────────────────────────────
# Recommandations
# ─────────────────────────────────────────────────────────────────────────────

class PlannerDayUpdate(BaseModel):
    """Tenue planifiée pour un jour : {slot_id: vetement_id | null}."""
    tenue: dict[str, Optional[str]] = {}


class ConseilAchat(BaseModel):
    slot: str
    couleur: str
    debloque: int
    total_apres: int


class ConseilsAchatResponse(BaseModel):
    total_tenues: int
    conseils: list[ConseilAchat]


# Slots config exposée au frontend
class SlotInfo(BaseModel):
    id: str
    emoji: str
    categories: list[str]
    need: str
    trigger: Optional[str] = None


class SlotsResponse(BaseModel):
    slots: list[SlotInfo]


# ─────────────────────────────────────────────────────────────────────────────
# Objectif garde-robe
# ─────────────────────────────────────────────────────────────────────────────

class Emplacement(BaseModel):
    statut: str  # "rempli" | "vide"
    vetement_id: Optional[str] = None
    vetement_nom: Optional[str] = None
    marque: Optional[str] = None
    position: Optional[float] = None  # 0..100, None si vide ou hors échelle
    hors_echelle: bool = False
    image: Optional[str] = None


class ObjectifTypeOut(BaseModel):
    nom: str
    ordre: int
    quantite_objectif: int
    echelle: list[str]
    rempli: int
    emplacements: list[Emplacement]
    excedent: list[Emplacement]


class NonRattacheOut(BaseModel):
    vetement_id: str
    vetement_nom: str
    type_objectif: Optional[str] = None


class ObjectifResponse(BaseModel):
    total_emplacements: int
    total_remplis: int
    non_rattaches: int
    non_rattaches_items: list[NonRattacheOut]
    types: list[ObjectifTypeOut]
