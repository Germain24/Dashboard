"""Schémas Pydantic — module Voyage."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class LieuVoyageOut(BaseModel):
    id: int
    nom: str
    ville: str | None
    pays: str | None
    visite: bool
    aeroport_iata: str | None
    jours_min: int | None
    jours_max: int | None
    cout_jour_estime: float | None
    complet: bool


class LieuProcheOut(LieuVoyageOut):
    distance_km: float


class SyncVoyageOut(BaseModel):
    lieux: int
    incomplets: list[str]


class PlanifierRequest(BaseModel):
    candidats: list[int]
    depart_iata: str = "YUL"
    arrivee_iata: str | None = None
    date_debut: dt.date
    date_fin: dt.date
    budget_total: float


class PointItineraire(BaseModel):
    iata: str
    lat: float | None
    lon: float | None


class EtapeItineraire(BaseModel):
    lieu_id: int
    nom: str
    pays: str | None
    jours: int
    date_arrivee: dt.date
    date_depart: dt.date
    lat: float | None
    lon: float | None


class ItineraireOut(BaseModel):
    etapes: list[EtapeItineraire]
    cout_total: float
    cout_transport: float
    cout_sejour: float
    depart: PointItineraire
    arrivee: PointItineraire


class ConfirmerRequest(BaseModel):
    lieu_ids: list[int]


class PlanifierAutoRequest(BaseModel):
    """Planification sans sélection manuelle : les candidats sont choisis
    automatiquement par proximité de `depart_iata` (comme /suggerer). Les
    prix de vol sont estimés localement (aucun appel réseau), donc
    `max_lieux` peut aller jusqu'à MAX_CANDIDATS sans risque de timeout."""
    depart_iata: str = "YUL"
    arrivee_iata: str | None = None
    date_debut: dt.date
    date_fin: dt.date
    budget_total: float
    k: int = 10
    max_lieux: int = 25


class ItinerairesMultiOut(BaseModel):
    itineraires: list[ItineraireOut]
