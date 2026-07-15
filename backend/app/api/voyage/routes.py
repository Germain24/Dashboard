"""Routes Voyage : sync Excel, candidats, planification, confirmation.

Master = data/imports/Voyage.xlsx. POST /sync l'importe dans lieu_voyage ;
POST /planifier calcule l'itinéraire optimal (prix estimés + OR-Tools) ;
POST /confirmer écrit Visité=True dans l'Excel + DB.
"""
from __future__ import annotations

import datetime as dt
import math
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.voyage.schemas import (
    ConfirmerRequest, EtapeItineraire, ItineraireOut, ItinerairesMultiOut, LieuProcheOut,
    LieuVoyageOut, PlanifierAutoRequest, PlanifierRequest, PointItineraire, SyncVoyageOut,
)
from app.core.config import settings
from app.core.db import get_session
from app.models.voyage import LieuVoyage
from app.services.voyage.airports import haversine_km, lookup_coords
from app.services.voyage.import_excel import marquer_visites, sync_voyage
from app.services.voyage.price_estimator import estimate_trajet
from app.services.voyage.solver import solve_itinerary, solve_top_k_itineraries, transit_cost

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


@router.get("/suggerer", response_model=list[LieuProcheOut])
def get_suggestions(depart_iata: str, limit: int = MAX_CANDIDATS,
                     session: Session = Depends(get_session)) -> list[LieuProcheOut]:
    """Suggère automatiquement les `limit` lieux non visités les plus proches
    (vol d'oiseau) de `depart_iata` — évite de cocher un par un dans une liste
    de ~1300 lieux, et regroupe naturellement une région (ex. Amérique du Sud
    depuis un hub colombien) plutôt que de tout tester globalement, ce qui
    exploserait la taille du circuit CP-SAT."""
    origine = lookup_coords(depart_iata)
    if origine is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Aéroport inconnu : {depart_iata}")

    lieux = session.exec(
        select(LieuVoyage).where(LieuVoyage.visite == False)  # noqa: E712
    ).all()
    proches: list[tuple[float, LieuVoyage]] = []
    for lv in lieux:
        if not _est_complet(lv):
            continue
        coords = lookup_coords(lv.aeroport_iata)
        if coords is None:
            continue
        proches.append((haversine_km(origine, coords), lv))
    proches.sort(key=lambda t: t[0])

    return [
        LieuProcheOut(
            id=lv.id, nom=lv.nom, ville=lv.ville, pays=lv.pays, visite=lv.visite,
            aeroport_iata=lv.aeroport_iata, jours_min=lv.jours_min, jours_max=lv.jours_max,
            cout_jour_estime=lv.cout_jour_estime, complet=True, distance_km=round(dist, 1),
        )
        for dist, lv in proches[:limit]
    ]


def _build_trajets(points: list[tuple[str, str]]) -> dict[tuple[str, str], dict]:
    """Prix/durée estimés pour chaque paire ordonnée de `points` (id, code
    IATA) -- calcul local instantané (formule par distance + éventuelle
    valeur éditée dans la feuille "Prix" de Voyage.xlsx), aucun appel réseau."""
    trajets: dict[tuple[str, str], dict] = {}
    for a_id, a_iata in points:
        for b_id, b_iata in points:
            if a_id == b_id:
                continue
            if a_iata == b_iata:
                # Même aéroport (ex. YUL -> YUL par défaut) : rien à parcourir.
                trajets[(a_id, b_id)] = {"prix": 0.0, "duree_min": 0}
                continue
            offer = estimate_trajet(a_iata, b_iata)
            if offer is None:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"Aéroport inconnu : {a_iata} ou {b_iata}",
                )
            trajets[(a_id, b_id)] = offer
    return trajets


def _format_itineraire(
    resultat: list[dict], trajets: dict[tuple[str, str], dict], by_id: dict[str, LieuVoyage],
    date_debut: dt.date, depart_iata: str, arrivee_iata: str,
    depart_lat: float | None, depart_lon: float | None,
    arrivee_lat: float | None, arrivee_lon: float | None,
) -> ItineraireOut:
    etapes: list[EtapeItineraire] = []
    cout_sejour = 0.0
    current_date = date_debut
    trajet_ids = ["DEPART"] + [e["id"] for e in resultat] + ["ARRIVEE"]
    for i, etape in enumerate(resultat):
        lieu = by_id[etape["id"]]
        prev_id = trajet_ids[i]
        travel_days = math.ceil(trajets[(prev_id, etape["id"])]["duree_min"] / 1440)
        current_date += dt.timedelta(days=travel_days)
        date_arrivee = current_date
        current_date += dt.timedelta(days=etape["jours"])
        date_depart = current_date
        lat, lon = lookup_coords(lieu.aeroport_iata) or (None, None)
        etapes.append(EtapeItineraire(
            lieu_id=lieu.id, nom=lieu.nom, pays=lieu.pays, jours=etape["jours"],
            date_arrivee=date_arrivee, date_depart=date_depart,
            lat=lat, lon=lon,
        ))
        cout_sejour += (lieu.cout_jour_estime or 0.0) * etape["jours"]

    cout_transport = sum(trajets[(a, b)]["prix"] for a, b in zip(trajet_ids, trajet_ids[1:]))
    # Subsistance pendant les jours de trajet (cf. solver.transit_cost) : pas
    # gratuit malgré l'absence de "visite" ce jour-là -- inclus dans le
    # transport plutôt que le séjour puisqu'il n'est rattaché à aucune étape.
    for a, b in zip(trajet_ids, trajet_ids[1:]):
        travel_days = math.ceil(trajets[(a, b)]["duree_min"] / 1440)
        if travel_days:
            cout_a = (by_id[a].cout_jour_estime or 0.0) if a in by_id else 0.0
            cout_b = (by_id[b].cout_jour_estime or 0.0) if b in by_id else 0.0
            cout_transport += transit_cost(cout_a, cout_b, travel_days)

    return ItineraireOut(
        etapes=etapes, cout_total=cout_transport + cout_sejour,
        cout_transport=cout_transport, cout_sejour=cout_sejour,
        depart=PointItineraire(iata=depart_iata, lat=depart_lat, lon=depart_lon),
        arrivee=PointItineraire(iata=arrivee_iata, lat=arrivee_lat, lon=arrivee_lon),
    )


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
    depart_lat, depart_lon = lookup_coords(req.depart_iata) or (None, None)
    arrivee_lat, arrivee_lon = lookup_coords(arrivee_iata) or (None, None)
    by_id = {str(lv.id): lv for lv in lieux}
    points = (
        [("DEPART", req.depart_iata)]
        + [(str(lv.id), lv.aeroport_iata) for lv in lieux]
        + [("ARRIVEE", arrivee_iata)]
    )
    trajets = _build_trajets(points)

    candidats_solver = [
        {"id": str(lv.id), "jours_min": lv.jours_min, "jours_max": lv.jours_max,
         "cout_jour": lv.cout_jour_estime or 0.0, "pays": lv.pays}
        for lv in lieux
    ]
    jours_disponibles = (req.date_fin - req.date_debut).days
    resultat = solve_itinerary(candidats_solver, trajets, req.budget_total, jours_disponibles)
    if resultat is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Aucun itinéraire ne respecte le budget/temps disponibles, même le trajet direct",
        )

    return _format_itineraire(
        resultat, trajets, by_id, req.date_debut, req.depart_iata, arrivee_iata,
        depart_lat, depart_lon, arrivee_lat, arrivee_lon,
    )


@router.post("/planifier-auto", response_model=ItinerairesMultiOut)
def post_planifier_auto(
    req: PlanifierAutoRequest, session: Session = Depends(get_session),
) -> ItinerairesMultiOut:
    """Planification "tout-en-un" : aucune sélection manuelle -- les
    candidats sont choisis automatiquement par VALEUR estimée depuis
    `depart_iata` (prix du vol + coût du séjour minimal), pas par pure
    proximité : une destination plus loin (vol plus cher) mais avec un
    coût/jour bien plus faible peut être un meilleur candidat qu'une
    destination proche mais chère une fois sur place (ex. Colombie vs
    Caraïbes). Jusqu'à `k` itinéraires DISTINCTS sont renvoyés (du meilleur
    au moins bon), pour laisser un choix plutôt qu'un unique résultat imposé."""
    origine = lookup_coords(req.depart_iata)
    if origine is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Aéroport inconnu : {req.depart_iata}")

    tous = session.exec(select(LieuVoyage).where(LieuVoyage.visite == False)).all()  # noqa: E712
    valeurs: list[tuple[float, LieuVoyage]] = []
    for lv in tous:
        if not _est_complet(lv):
            continue
        offer = estimate_trajet(req.depart_iata, lv.aeroport_iata)
        if offer is None:
            continue
        # Coût d'un séjour minimal viable là-bas : vol + jours_min au coût/jour
        # estimé -- une pénalité de vol élevée peut être largement compensée
        # par un coût/jour bien plus bas (et inversement).
        valeurs.append((offer["prix"] + lv.cout_jour_estime * lv.jours_min, lv))
    valeurs.sort(key=lambda t: t[0])
    max_lieux = max(1, min(req.max_lieux, MAX_CANDIDATS))
    lieux = [lv for _, lv in valeurs[:max_lieux]]
    if not lieux:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucun lieu candidat disponible près de ce départ")

    arrivee_iata = req.arrivee_iata or req.depart_iata
    depart_lat, depart_lon = origine
    arrivee_lat, arrivee_lon = lookup_coords(arrivee_iata) or (None, None)
    by_id = {str(lv.id): lv for lv in lieux}
    points = (
        [("DEPART", req.depart_iata)]
        + [(str(lv.id), lv.aeroport_iata) for lv in lieux]
        + [("ARRIVEE", arrivee_iata)]
    )
    trajets = _build_trajets(points)

    candidats_solver = [
        {"id": str(lv.id), "jours_min": lv.jours_min, "jours_max": lv.jours_max,
         "cout_jour": lv.cout_jour_estime or 0.0, "pays": lv.pays}
        for lv in lieux
    ]
    jours_disponibles = (req.date_fin - req.date_debut).days
    k = max(1, min(req.k, 20))
    resultats = solve_top_k_itineraries(candidats_solver, trajets, req.budget_total, jours_disponibles, k=k)
    if not resultats:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Aucun itinéraire ne respecte le budget/temps disponibles, même le trajet direct",
        )

    itineraires = [
        _format_itineraire(
            resultat, trajets, by_id, req.date_debut, req.depart_iata, arrivee_iata,
            depart_lat, depart_lon, arrivee_lat, arrivee_lon,
        )
        for resultat in resultats
    ]
    return ItinerairesMultiOut(itineraires=itineraires)


@router.post("/confirmer")
def post_confirmer(req: ConfirmerRequest, session: Session = Depends(get_session)) -> dict:
    lieux = session.exec(select(LieuVoyage).where(LieuVoyage.id.in_(req.lieu_ids))).all()
    noms = [lv.nom for lv in lieux]
    path = _voyage_xlsx_path()
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Fichier introuvable : {path}")
    marquer_visites(session, path, noms)
    return {"visites": len(noms)}
