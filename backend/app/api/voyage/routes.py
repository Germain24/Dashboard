"""Routes Voyage : sync Excel, candidats, planification, confirmation.

Master = data/imports/Voyage.xlsx. POST /sync l'importe dans lieu_voyage ;
POST /planifier calcule l'itinéraire optimal (Duffel + OR-Tools) ;
POST /confirmer écrit Visité=True dans l'Excel + DB.
"""
from __future__ import annotations

import datetime as dt
import math
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.voyage.schemas import (
    ConfirmerRequest, EtapeItineraire, ItineraireOut, LieuVoyageOut,
    PlanifierRequest, SyncVoyageOut,
)
from app.core.config import settings
from app.core.db import get_session
from app.models.voyage import LieuVoyage
from app.services.finance import fx
from app.services.voyage.duffel_client import fetch_offer
from app.services.voyage.import_excel import marquer_visites, sync_voyage
from app.services.voyage.solver import solve_itinerary

router = APIRouter(tags=["voyage"])

MAX_CANDIDATS = 25


def _voyage_xlsx_path() -> Path:
    return settings.imports_dir / "Voyage.xlsx"


def _est_complet(lv: LieuVoyage) -> bool:
    return (
        bool(lv.aeroport_iata)
        and lv.jours_min is not None
        and lv.jours_max is not None
        and lv.cout_jour_estime is not None
    )


def _prix_en_eur(prix: float, devise: str | None) -> float:
    """Convertit `prix` (dans `devise`) en EUR, best-effort (repli sur la
    valeur brute si le taux de change est indisponible). Mirroir de
    `app.services.finance.patrimoine.to_eur`."""
    if not devise or devise.upper() == "EUR":
        return round(float(prix), 2)
    try:
        eur = fx.convert(float(prix), devise.upper(), "EUR")
        return eur if eur else round(float(prix), 2)
    except Exception:
        return round(float(prix), 2)


@router.get("/ping")
def ping() -> dict:
    return {"module": "voyage", "ready": True}


@router.post("/sync", response_model=SyncVoyageOut)
def post_sync(session: Session = Depends(get_session)) -> SyncVoyageOut:
    path = _voyage_xlsx_path()
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Fichier introuvable : {path}")
    result = sync_voyage(session, path)
    return SyncVoyageOut(**result)


@router.get("/lieux", response_model=list[LieuVoyageOut])
def get_lieux(session: Session = Depends(get_session)) -> list[LieuVoyageOut]:
    lieux = session.exec(select(LieuVoyage).order_by(LieuVoyage.nom)).all()
    return [
        LieuVoyageOut(
            id=lv.id, nom=lv.nom, ville=lv.ville, pays=lv.pays, visite=lv.visite,
            aeroport_iata=lv.aeroport_iata, jours_min=lv.jours_min, jours_max=lv.jours_max,
            cout_jour_estime=lv.cout_jour_estime, complet=_est_complet(lv),
        )
        for lv in lieux
    ]


@router.post("/planifier", response_model=ItineraireOut)
def post_planifier(req: PlanifierRequest, session: Session = Depends(get_session)) -> ItineraireOut:
    if len(req.candidats) > MAX_CANDIDATS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                             f"{MAX_CANDIDATS} lieux candidats maximum par requête")

    lieux = session.exec(select(LieuVoyage).where(LieuVoyage.id.in_(req.candidats))).all()
    if len(lieux) != len(set(req.candidats)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Un ou plusieurs lieux candidats introuvables")

    incomplets = [lv.nom for lv in lieux if not _est_complet(lv)]
    if incomplets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                             f"Lieux incomplets (aéroport/jours manquants) : {', '.join(incomplets)}")

    visites = [lv.nom for lv in lieux if lv.visite]
    if visites:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                             f"Lieux déjà visités (exclus des candidats) : {', '.join(visites)}")

    arrivee_iata = req.arrivee_iata or req.depart_iata
    date_ref = req.date_debut.isoformat()
    by_id = {str(lv.id): lv for lv in lieux}
    points = (
        [("DEPART", req.depart_iata)]
        + [(str(lv.id), lv.aeroport_iata) for lv in lieux]
        + [("ARRIVEE", arrivee_iata)]
    )

    trajets: dict[tuple[str, str], dict] = {}
    for a_id, a_iata in points:
        for b_id, b_iata in points:
            if a_id == b_id:
                continue
            if a_iata == b_iata:
                # Même aéroport (ex. YUL -> YUL par défaut) : rien à parcourir,
                # Duffel ne peut de toute façon pas pricer une paire identique.
                trajets[(a_id, b_id)] = {"prix": 0.0, "duree_min": 0}
                continue
            offer = fetch_offer(session, a_iata, b_iata, date_ref)
            if offer is None:
                raise HTTPException(
                    status.HTTP_502_BAD_GATEWAY,
                    f"Impossible d'obtenir un prix de vol {a_iata} -> {b_iata}",
                )
            prix_eur = _prix_en_eur(offer["prix"], offer.get("devise"))
            trajets[(a_id, b_id)] = {"prix": prix_eur, "duree_min": offer["duree_min"]}

    candidats_solver = [
        {"id": str(lv.id), "jours_min": lv.jours_min, "jours_max": lv.jours_max,
         "cout_jour": lv.cout_jour_estime or 0.0}
        for lv in lieux
    ]
    jours_disponibles = (req.date_fin - req.date_debut).days
    resultat = solve_itinerary(candidats_solver, trajets, req.budget_total, jours_disponibles)
    if resultat is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Aucun itinéraire ne respecte le budget/temps disponibles, même le trajet direct",
        )

    etapes: list[EtapeItineraire] = []
    cout_sejour = 0.0
    current_date = req.date_debut
    trajet_ids = ["DEPART"] + [e["id"] for e in resultat] + ["ARRIVEE"]
    for i, etape in enumerate(resultat):
        lieu = by_id[etape["id"]]
        prev_id = trajet_ids[i]
        travel_days = math.ceil(trajets[(prev_id, etape["id"])]["duree_min"] / 1440)
        current_date += dt.timedelta(days=travel_days)
        date_arrivee = current_date
        current_date += dt.timedelta(days=etape["jours"])
        date_depart = current_date
        etapes.append(EtapeItineraire(
            lieu_id=lieu.id, nom=lieu.nom, jours=etape["jours"],
            date_arrivee=date_arrivee, date_depart=date_depart,
        ))
        cout_sejour += (lieu.cout_jour_estime or 0.0) * etape["jours"]

    cout_transport = sum(trajets[(a, b)]["prix"] for a, b in zip(trajet_ids, trajet_ids[1:]))

    return ItineraireOut(
        etapes=etapes, cout_total=cout_transport + cout_sejour,
        cout_transport=cout_transport, cout_sejour=cout_sejour,
    )


@router.post("/confirmer")
def post_confirmer(req: ConfirmerRequest, session: Session = Depends(get_session)) -> dict:
    lieux = session.exec(select(LieuVoyage).where(LieuVoyage.id.in_(req.lieu_ids))).all()
    noms = [lv.nom for lv in lieux]
    path = _voyage_xlsx_path()
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Fichier introuvable : {path}")
    marquer_visites(session, path, noms)
    return {"visites": len(noms)}
