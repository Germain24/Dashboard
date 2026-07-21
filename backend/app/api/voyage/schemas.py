"""Schémas Pydantic — module Voyage."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field


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
    ordre: int | None = None
    progression: str | None = None
    priorite: int = 3
    cout_activite: float | None = None
    cout_transport_local: float | None = None
    mois_disponibles: str | None = None
    verrouille: bool = False
    raison_verrouillage: str | None = None
    cout_hebergement_jour: float | None = None
    cout_nourriture_jour: float | None = None
    statut: str = "possible"
    raison_indisponible: str | None = None


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
    ville: str | None = None
    aeroport_iata: str | None = None
    cout_activite: float = 0.0
    cout_transport_local: float = 0.0
    ordre: int | None = None
    progression: str | None = None
    cout_hebergement: float = 0.0
    cout_nourriture: float = 0.0
    source_cout_journalier: str = "estimé"
    source_cout_activite: str = "estimé"
    source_transport_local: str = "estimé"


class ItineraireOut(BaseModel):
    etapes: list[EtapeItineraire]
    cout_total: float
    cout_transport: float
    cout_sejour: float
    depart: PointItineraire
    arrivee: PointItineraire
    cout_activites: float = 0.0
    cout_transport_local: float = 0.0
    cout_hebergement: float = 0.0
    cout_nourriture: float = 0.0
    source_prix_vol: str = "estimation"
    transporteur: str | None = None
    fiabilite_prix: str = "faible"
    avertissements: list[str] = Field(default_factory=list)


class EtapeConfirmee(BaseModel):
    """Étape retenue envoyée par le client. Les coûts ne sont PAS transmis :
    ils sont recalculés côté serveur depuis `lieu_voyage` (cf. costs.py)."""
    lieu_id: int
    jours: int = 0
    date_arrivee: dt.date | None = None
    date_depart: dt.date | None = None


class ConfirmerRequest(BaseModel):
    """`etapes` absent = ancien contrat : on marque seulement les lieux visités."""
    lieu_ids: list[int]
    titre: str | None = None
    date_debut: dt.date | None = None
    date_fin: dt.date | None = None
    depart_iata: str | None = None
    arrivee_iata: str | None = None
    etapes: list[EtapeConfirmee] | None = None


class ConfirmerOut(BaseModel):
    visites: int
    voyage_id: int | None = None


class VoyageEtapeOut(BaseModel):
    id: int
    lieu_id: int | None
    nom: str
    ville: str | None
    pays: str | None
    ordre: int
    jours: int
    date_arrivee: dt.date | None
    date_depart: dt.date | None
    cout_estime: float
    cout_reel: float | None


class ChecklistItemOut(BaseModel):
    id: int
    label: str
    fait: bool
    ordre: int


class BudgetVoyageOut(BaseModel):
    cout_estime_total: float
    cout_reel_total: float
    cout_projete_total: float
    ecart: float
    etapes_avec_cout_reel: int


class VoyageOut(BaseModel):
    id: int
    titre: str
    date_debut: dt.date
    date_fin: dt.date
    depart_iata: str | None
    arrivee_iata: str | None
    etapes: list[VoyageEtapeOut]
    checklist: list[ChecklistItemOut]
    budget: BudgetVoyageOut
    checklist_total: int
    checklist_faits: int


class CoutReelRequest(BaseModel):
    """`null` (ou champ absent) efface la saisie et refait tomber le projeté
    sur l'estimé."""
    cout_reel: float | None = None


class ChecklistItemCreate(BaseModel):
    label: str = Field(min_length=1)


class ChecklistItemUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1)
    fait: bool | None = None
    ordre: int | None = None


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
    k: int = 5
    max_lieux: int = 25
    prix_live: bool = True


class ItinerairesMultiOut(BaseModel):
    itineraires: list[ItineraireOut]
