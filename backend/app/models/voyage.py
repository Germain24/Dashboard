"""Modèles Voyage — planificateur d'itinéraire (liste de lieux à visiter).

Tables :
  - `lieu_voyage`          : cache de la wishlist (master = data/imports/Voyage.xlsx)
  - `voyage_price_cache`   : prix de vol live mis en cache par trajet/date
  - `voyage`               : itinéraire retenu, persisté par POST /voyage/confirmer
  - `voyage_etape`         : une étape du voyage + son budget estimé/réel
  - `voyage_checklist_item`: checklist de préparation, portée par voyage
"""
from __future__ import annotations

import datetime as dt

from sqlmodel import Field, SQLModel


class LieuVoyage(SQLModel, table=True):
    """Cache d'un lieu de la wishlist voyage.

    Écrasé à chaque POST /voyage/sync, sauf `visite` qui est aussi écrit
    directement dans l'Excel par POST /voyage/confirmer (import_excel.py) —
    la synchro Excel->DB est un import destructif, donc l'Excel doit rester
    la source de vérité pour ce champ.
    """

    __tablename__ = "lieu_voyage"

    id: int | None = Field(default=None, primary_key=True)
    nom: str
    ville: str | None = None
    pays: str | None = None
    visite: bool = False
    aeroport_iata: str | None = None
    jours_min: int | None = None
    jours_max: int | None = None
    cout_jour_estime: float | None = None
    ordre: int | None = None
    progression: str | None = None
    priorite: int = 3
    cout_activite: float | None = None
    cout_transport_local: float | None = None
    mois_disponibles: str | None = None
    cout_hebergement_jour: float | None = None
    cout_nourriture_jour: float | None = None
    statut: str = "possible"
    raison_indisponible: str | None = None


class VoyagePriceCache(SQLModel, table=True):
    """Offre de vol live, conservée brièvement pour éviter les recherches répétées."""

    __tablename__ = "voyage_price_cache"

    cache_key: str = Field(primary_key=True)
    itineraire: str
    dates: str
    prix: float
    devise: str
    duree_min: int
    transporteur: str | None = None
    fetched_at: str


class Voyage(SQLModel, table=True):
    """Itinéraire confirmé — ce à quoi se rattachent checklist et budget.

    Avant cette table, POST /voyage/confirmer ne persistait rien du voyage :
    il basculait seulement `visite=True` sur les lieux retenus. Un itinéraire
    calculé était donc perdu dès la réponse HTTP.
    """

    __tablename__ = "voyage"

    id: int | None = Field(default=None, primary_key=True)
    titre: str
    date_debut: dt.date
    date_fin: dt.date
    depart_iata: str | None = None
    arrivee_iata: str | None = None
    cree_le: dt.date = Field(default_factory=dt.date.today)


class VoyageEtape(SQLModel, table=True):
    """Une étape de l'itinéraire retenu, avec son budget estimé puis réel.

    `lieu_id` n'est volontairement PAS une clé étrangère : `sync_voyage` vide
    et réécrit `lieu_voyage` à chaque import Excel, donc les ids ne survivent
    pas à une resynchro. Le nom/pays sont dénormalisés pour la même raison.
    """

    __tablename__ = "voyage_etape"

    id: int | None = Field(default=None, primary_key=True)
    voyage_id: int = Field(foreign_key="voyage.id", index=True)
    lieu_id: int | None = None
    nom: str
    ville: str | None = None
    pays: str | None = None
    ordre: int = 0
    jours: int = 0
    date_arrivee: dt.date | None = None
    date_depart: dt.date | None = None
    cout_estime: float = 0.0
    cout_reel: float | None = None


class VoyageChecklistItem(SQLModel, table=True):
    """Item de préparation d'un voyage (passeport, assurance, vaccins…)."""

    __tablename__ = "voyage_checklist_item"

    id: int | None = Field(default=None, primary_key=True)
    voyage_id: int = Field(foreign_key="voyage.id", index=True)
    label: str
    fait: bool = False
    ordre: int = 0
