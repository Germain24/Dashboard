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


class SyncVoyageOut(BaseModel):
    lieux: int
    incomplets: list[str]


class PlanifierRequest(BaseModel):
    candidats: list[int]
    depart_iata: str
    arrivee_iata: str
    date_debut: dt.date
    date_fin: dt.date
    budget_total: float


class EtapeItineraire(BaseModel):
    lieu_id: int
    nom: str
    jours: int
    date_arrivee: dt.date
    date_depart: dt.date


class ItineraireOut(BaseModel):
    etapes: list[EtapeItineraire]
    cout_total: float
    cout_transport: float
    cout_sejour: float


class ConfirmerRequest(BaseModel):
    lieu_ids: list[int]
