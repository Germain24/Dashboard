"""Routes Voyage : sync Excel, candidats, planification, confirmation.

Master = data/imports/Voyage.xlsx. POST /sync l'importe dans lieu_voyage ;
POST /planifier calcule l'itinéraire optimal (prix live/fallback + OR-Tools) ;
POST /confirmer écrit Visité=True dans l'Excel + DB.
"""
from __future__ import annotations

import datetime as dt
import math
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.voyage.schemas import (
    BudgetVoyageOut,
    ChecklistItemCreate,
    ChecklistItemOut,
    ChecklistItemUpdate,
    ConfirmerOut,
    ConfirmerRequest,
    CoutReelRequest,
    EtapeItineraire,
    ItineraireOut,
    ItinerairesMultiOut,
    LieuProcheOut,
    LieuVoyageOut,
    PlanifierAutoRequest,
    PlanifierRequest,
    PointItineraire,
    SyncVoyageOut,
    VoyageEtapeOut,
    VoyageOut,
)
from app.core.config import settings
from app.core.db import get_session
from app.models.voyage import LieuVoyage
from app.services.voyage.airports import haversine_km, lookup_coords
from app.services.voyage.costs import cost_breakdown
from app.services.voyage.import_excel import marquer_visites, sync_voyage
from app.services.voyage.live_pricing import fetch_live_itinerary
from app.services.voyage.planning_rules import (
    is_in_season,
    lock_reason,
    route_detour_ratio,
    select_diverse_candidates,
    unlocked_levels,
)
from app.services.voyage.price_estimator import estimate_trajet
from app.services.voyage.solver import solve_itinerary, solve_top_k_itineraries, transit_cost
from app.services.voyage.voyages import (
    add_checklist_item,
    aggregate_budget,
    create_voyage,
    delete_checklist_item,
    delete_voyage,
    get_voyage,
    list_voyages,
    set_cout_reel,
    update_checklist_item,
    voyage_checklist,
    voyage_etapes,
)

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


def _solver_candidate(lv: LieuVoyage) -> dict:
    costs = cost_breakdown(lv, lv.jours_min)
    return {
        "id": str(lv.id), "jours_min": lv.jours_min, "jours_max": lv.jours_max,
        "cout_jour": costs["cout_jour"], "pays": lv.pays,
        "hub": lv.aeroport_iata, "priorite": lv.priorite,
        "cout_fixe": costs["activite"] + costs["transport_local"],
    }


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
    levels = unlocked_levels(lieux)
    return [
        LieuVoyageOut(
            id=lv.id, nom=lv.nom, ville=lv.ville, pays=lv.pays, visite=lv.visite,
            aeroport_iata=lv.aeroport_iata, jours_min=lv.jours_min, jours_max=lv.jours_max,
            cout_jour_estime=lv.cout_jour_estime, complet=_est_complet(lv),
            ordre=lv.ordre, progression=lv.progression, priorite=lv.priorite,
            cout_activite=lv.cout_activite,
            cout_transport_local=lv.cout_transport_local,
            mois_disponibles=lv.mois_disponibles,
            verrouille=lock_reason(lv, levels) is not None or lv.statut == "impossible",
            raison_verrouillage=(
                lv.raison_indisponible if lv.statut == "impossible" else lock_reason(lv, levels)
            ),
            cout_hebergement_jour=lv.cout_hebergement_jour,
            cout_nourriture_jour=lv.cout_nourriture_jour,
            statut=lv.statut,
            raison_indisponible=lv.raison_indisponible,
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
        if not _est_complet(lv) or lv.statut == "impossible":
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


def _build_trajets(points: list[tuple[str, str, str | None]]) -> dict[tuple[str, str], dict]:
    """Prix/durée estimés pour chaque paire ordonnée de `points` (id, code
    IATA) -- calcul local instantané (formule par distance + éventuelle
    valeur éditée dans la feuille "Prix" de Voyage.xlsx), aucun appel réseau."""
    trajets: dict[tuple[str, str], dict] = {}
    for a_id, a_iata, a_pays in points:
        for b_id, b_iata, b_pays in points:
            if a_id == b_id:
                continue
            if a_iata == b_iata:
                # Même aéroport (ex. YUL -> YUL par défaut) : rien à parcourir.
                trajets[(a_id, b_id)] = {"prix": 0.0, "duree_min": 0, "source": "local"}
                continue
            offer = estimate_trajet(a_iata, b_iata)
            if offer is None:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"Aéroport inconnu : {a_iata} ou {b_iata}",
                )
            # Pour deux villes d'un même pays assez proches, bus/train/voiture
            # est généralement plus réaliste qu'un nouveau billet d'avion.
            a_coords, b_coords = lookup_coords(a_iata), lookup_coords(b_iata)
            distance = haversine_km(a_coords, b_coords) if a_coords and b_coords else None
            if a_pays and a_pays == b_pays and distance is not None and distance <= 600:
                trajets[(a_id, b_id)] = {
                    "prix": round(15 + distance * 0.10, 2),
                    "duree_min": round(60 + distance / 70 * 60),
                    "source": "transport_local_estime",
                }
            else:
                trajets[(a_id, b_id)] = {**offer, "source": "vol_estime"}
    return trajets


def _format_itineraire(
    resultat: list[dict], trajets: dict[tuple[str, str], dict], by_id: dict[str, LieuVoyage],
    date_debut: dt.date, depart_iata: str, arrivee_iata: str,
    depart_lat: float | None, depart_lon: float | None,
    arrivee_lat: float | None, arrivee_lon: float | None,
    *, prix_vol_live: dict | None = None,
) -> ItineraireOut:
    etapes: list[EtapeItineraire] = []
    cout_sejour = 0.0
    cout_hebergement = 0.0
    cout_nourriture = 0.0
    cout_activites = 0.0
    cout_transport_local = 0.0
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
        costs = cost_breakdown(lieu, etape["jours"])
        etapes.append(EtapeItineraire(
            lieu_id=lieu.id, nom=lieu.nom, pays=lieu.pays, jours=etape["jours"],
            date_arrivee=date_arrivee, date_depart=date_depart,
            lat=lat, lon=lon,
            ville=lieu.ville, aeroport_iata=lieu.aeroport_iata,
            cout_activite=costs["activite"],
            cout_transport_local=costs["transport_local"],
            ordre=lieu.ordre, progression=lieu.progression,
            cout_hebergement=costs["hebergement"],
            cout_nourriture=costs["nourriture"],
            source_cout_journalier=costs["source_journalier"],
            source_cout_activite=costs["source_activite"],
            source_transport_local=costs["source_local"],
        ))
        cout_hebergement += costs["hebergement"]
        cout_nourriture += costs["nourriture"]
        cout_sejour += costs["hebergement"] + costs["nourriture"]
        cout_activites += costs["activite"]
        cout_transport_local += costs["transport_local"]

    paires = list(zip(trajet_ids, trajet_ids[1:], strict=False))
    cout_deplacements_estime = sum(
        trajets[(a, b)]["prix"] for a, b in zip(trajet_ids, trajet_ids[1:], strict=False)
    )
    cout_terrestre = sum(
        trajets[(a, b)]["prix"] for a, b in paires
        if trajets[(a, b)].get("source") != "vol_estime"
    )
    cout_transport = (
        prix_vol_live["prix"] + cout_terrestre if prix_vol_live else cout_deplacements_estime
    )
    # Subsistance pendant les jours de trajet (cf. solver.transit_cost) : pas
    # gratuit malgré l'absence de "visite" ce jour-là -- inclus dans le
    # transport plutôt que le séjour puisqu'il n'est rattaché à aucune étape.
    for a, b in zip(trajet_ids, trajet_ids[1:], strict=False):
        travel_days = math.ceil(trajets[(a, b)]["duree_min"] / 1440)
        if travel_days:
            cout_a = cost_breakdown(by_id[a])["cout_jour"] if a in by_id else 0.0
            cout_b = cost_breakdown(by_id[b])["cout_jour"] if b in by_id else 0.0
            cout_transport += transit_cost(cout_a, cout_b, travel_days)

    return ItineraireOut(
        etapes=etapes,
        cout_total=cout_transport + cout_sejour + cout_activites + cout_transport_local,
        cout_transport=cout_transport, cout_sejour=cout_sejour,
        depart=PointItineraire(iata=depart_iata, lat=depart_lat, lon=depart_lon),
        arrivee=PointItineraire(iata=arrivee_iata, lat=arrivee_lat, lon=arrivee_lon),
        cout_activites=cout_activites,
        cout_transport_local=cout_transport_local,
        cout_hebergement=cout_hebergement,
        cout_nourriture=cout_nourriture,
        source_prix_vol=prix_vol_live["source"] if prix_vol_live else "estimation",
        transporteur=prix_vol_live.get("transporteur") if prix_vol_live else None,
        fiabilite_prix="élevée" if prix_vol_live else "faible",
        avertissements=_pricing_warnings(resultat, by_id, trajets, prix_vol_live),
    )


def _pricing_warnings(
    resultat: list[dict], by_id: dict[str, LieuVoyage],
    trajets: dict[tuple[str, str], dict], prix_vol_live: dict | None,
) -> list[str]:
    warnings: list[str] = []
    if prix_vol_live is None:
        warnings.append("Vols estimés par distance : configure DUFFEL_API_KEY pour vérifier les dates réelles.")
    lieux = [by_id[e["id"]] for e in resultat]
    breakdowns = [cost_breakdown(lieu) for lieu in lieux]
    if any(cost["source_activite"] == "estimé" for cost in breakdowns):
        warnings.append("Certains prix d'activité sont estimés ; renseigne-les dans Voyage.xlsx.")
    if any(cost["source_local"] == "estimé" for cost in breakdowns):
        warnings.append("Certains transports locaux sont estimés ; renseigne-les dans Voyage.xlsx.")
    if any(cost["source_journalier"] != "renseigné" for cost in breakdowns):
        warnings.append("Hébergement et nourriture sont ventilés depuis le coût/jour historique.")
    if any(lieu.mois_disponibles is None for lieu in lieux):
        warnings.append("La saison de certaines activités n'est pas renseignée.")
    ids = ["DEPART"] + [e["id"] for e in resultat] + ["ARRIVEE"]
    used = [trajets[pair] for pair in zip(ids, ids[1:], strict=False)]
    if any(trajet.get("source") == "transport_local_estime" for trajet in used):
        warnings.append("Les trajets terrestres intérieurs sont estimés ; la matrice Excel reste prioritaire.")
    return warnings


def _live_slices(
    resultat: list[dict], by_id: dict[str, LieuVoyage], date_debut: dt.date,
    depart_iata: str, arrivee_iata: str, trajets: dict[tuple[str, str], dict],
) -> list[dict]:
    """Construit les tranches Duffel aux dates où chaque déplacement démarre."""
    slices: list[dict] = []
    current_iata = depart_iata
    current_id = "DEPART"
    current_date = date_debut
    for etape in resultat:
        lieu = by_id[etape["id"]]
        if (
            current_iata != lieu.aeroport_iata
            and trajets[(current_id, etape["id"])].get("source") == "vol_estime"
        ):
            slices.append({
                "origin": current_iata, "destination": lieu.aeroport_iata,
                "departure_date": current_date.isoformat(),
            })
        current_date += dt.timedelta(
            days=math.ceil(trajets[(current_id, etape["id"])]["duree_min"] / 1440)
        )
        current_iata = lieu.aeroport_iata
        current_id = etape["id"]
        current_date += dt.timedelta(days=etape["jours"])
    if (
        current_iata != arrivee_iata
        and trajets[(current_id, "ARRIVEE")].get("source") == "vol_estime"
    ):
        slices.append({
            "origin": current_iata, "destination": arrivee_iata,
            "departure_date": current_date.isoformat(),
        })
    return slices


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

    impossibles = [lv for lv in lieux if lv.statut == "impossible"]
    if impossibles:
        lieu = impossibles[0]
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{lieu.nom} est indisponible : {lieu.raison_indisponible or 'activité impossible'}",
        )

    tous = session.exec(select(LieuVoyage)).all()
    levels = unlocked_levels(tous)
    locked = [lock_reason(lv, levels) for lv in lieux if lock_reason(lv, levels)]
    if locked:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, locked[0])
    hors_saison = [lv.nom for lv in lieux if not is_in_season(lv, req.date_debut, req.date_fin)]
    if hors_saison:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Indisponible à cette saison : {', '.join(hors_saison)}",
        )

    arrivee_iata = req.arrivee_iata or req.depart_iata
    depart_lat, depart_lon = lookup_coords(req.depart_iata) or (None, None)
    arrivee_lat, arrivee_lon = lookup_coords(arrivee_iata) or (None, None)
    by_id = {str(lv.id): lv for lv in lieux}
    points = (
        [("DEPART", req.depart_iata, None)]
        + [(str(lv.id), lv.aeroport_iata, lv.pays) for lv in lieux]
        + [("ARRIVEE", arrivee_iata, None)]
    )
    trajets = _build_trajets(points)

    candidats_solver = [_solver_candidate(lv) for lv in lieux]
    jours_disponibles = (req.date_fin - req.date_debut).days
    max_destinations = max(1, min(9, math.ceil(jours_disponibles / 7)))
    resultat = solve_itinerary(
        candidats_solver, trajets, req.budget_total, jours_disponibles,
        max_destinations=max_destinations,
    )
    if resultat is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Aucun itinéraire ne respecte le budget/temps disponibles, même le trajet direct",
        )

    live = fetch_live_itinerary(
        session,
        _live_slices(resultat, by_id, req.date_debut, req.depart_iata, arrivee_iata, trajets),
    )
    return _format_itineraire(
        resultat, trajets, by_id, req.date_debut, req.depart_iata, arrivee_iata,
        depart_lat, depart_lon, arrivee_lat, arrivee_lon, prix_vol_live=live,
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

    arrivee_iata = req.arrivee_iata or req.depart_iata
    arrivee_coords = lookup_coords(arrivee_iata)
    if arrivee_coords is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Aéroport inconnu : {arrivee_iata}")

    tous_lieux = session.exec(select(LieuVoyage)).all()
    levels = unlocked_levels(tous_lieux)
    tous = [lv for lv in tous_lieux if not lv.visite]
    valeurs: list[tuple[float, LieuVoyage, float]] = []
    eligible_count = 0
    for lv in tous:
        if not _est_complet(lv) or lv.statut != "possible":
            continue
        if lock_reason(lv, levels) or not is_in_season(lv, req.date_debut, req.date_fin):
            continue
        eligible_count += 1
        candidate_coords = lookup_coords(lv.aeroport_iata)
        if candidate_coords is None:
            continue
        detour = route_detour_ratio(origine, arrivee_coords, candidate_coords)
        # Un voyage avec des aéroports différents est un trajet orienté, pas
        # un tour du monde implicite. 1.65 laisse de vrais détours régionaux
        # tout en excluant le Pacifique sur un YUL -> CDG.
        if req.depart_iata != arrivee_iata and detour > 1.65:
            continue
        outbound = estimate_trajet(req.depart_iata, lv.aeroport_iata)
        inbound = estimate_trajet(lv.aeroport_iata, arrivee_iata)
        if outbound is None or inbound is None:
            continue
        costs = cost_breakdown(lv, lv.jours_min)
        min_cost = (
            outbound["prix"] + inbound["prix"]
            + costs["hebergement"] + costs["nourriture"]
            + costs["activite"] + costs["transport_local"]
        )
        if min_cost <= req.budget_total:
            valeurs.append((min_cost, lv, detour))
    max_lieux = max(1, min(req.max_lieux, MAX_CANDIDATS))
    lieux = select_diverse_candidates(valeurs, req.budget_total, max_lieux)
    if not lieux:
        if eligible_count:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Aucune destination disponible ne respecte ce budget et ces dates",
            )
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Aucun lieu complet, déverrouillé et disponible à cette saison",
        )

    depart_lat, depart_lon = origine
    arrivee_lat, arrivee_lon = arrivee_coords
    by_id = {str(lv.id): lv for lv in lieux}
    points = (
        [("DEPART", req.depart_iata, None)]
        + [(str(lv.id), lv.aeroport_iata, lv.pays) for lv in lieux]
        + [("ARRIVEE", arrivee_iata, None)]
    )
    trajets = _build_trajets(points)

    candidats_solver = [_solver_candidate(lv) for lv in lieux]
    jours_disponibles = (req.date_fin - req.date_debut).days
    max_destinations = max(1, min(9, math.ceil(jours_disponibles / 7)))
    k = max(1, min(req.k, 20))
    resultats = solve_top_k_itineraries(
        candidats_solver, trajets, req.budget_total, jours_disponibles,
        k=k, max_destinations=max_destinations,
    )
    if not resultats:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Aucun itinéraire ne respecte le budget/temps disponibles, même le trajet direct",
        )

    itineraires: list[ItineraireOut] = []
    for index, resultat in enumerate(resultats):
        live = None
        live_required = req.prix_live and bool(settings.duffel_api_key)
        if req.prix_live and index < settings.voyage_max_live_itineraries:
            live = fetch_live_itinerary(
                session,
                _live_slices(
                    resultat, by_id, req.date_debut, req.depart_iata, arrivee_iata, trajets,
                ),
            )
        if live_required and live is None:
            continue
        formatted = _format_itineraire(
            resultat, trajets, by_id, req.date_debut, req.depart_iata, arrivee_iata,
            depart_lat, depart_lon, arrivee_lat, arrivee_lon, prix_vol_live=live,
        )
        # Un prix live supérieur au budget invalide réellement l'option. Les
        # estimations restent proposées avec leur avertissement explicite.
        if live is None or formatted.cout_total <= req.budget_total:
            itineraires.append(formatted)
    if not itineraires:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Les vols live dépassent le budget pour tous les itinéraires candidats",
        )
    return ItinerairesMultiOut(itineraires=itineraires)


@router.post("/confirmer", response_model=ConfirmerOut)
def post_confirmer(
    req: ConfirmerRequest, session: Session = Depends(get_session),
) -> ConfirmerOut:
    """Marque les lieux visités et, si l'itinéraire est fourni, persiste le
    voyage (checklist + budget par étape s'y rattachent)."""
    lieux = session.exec(select(LieuVoyage).where(LieuVoyage.id.in_(req.lieu_ids))).all()
    noms = [lv.nom for lv in lieux]
    path = _voyage_xlsx_path()
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Fichier introuvable : {path}")
    marquer_visites(session, path, noms)

    voyage_id = None
    if req.etapes:
        try:
            voyage = create_voyage(
                session,
                titre=req.titre or "Voyage",
                date_debut=req.date_debut or dt.date.today(),
                date_fin=req.date_fin or dt.date.today(),
                depart_iata=req.depart_iata, arrivee_iata=req.arrivee_iata,
                etapes=[e.model_dump() for e in req.etapes],
            )
        except ValueError as exc:
            session.rollback()
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
        voyage_id = voyage.id
    return ConfirmerOut(visites=len(noms), voyage_id=voyage_id)


# ─── Voyages confirmés : checklist + budget par étape ─────────────────────────

def _voyage_out(session: Session, voyage) -> VoyageOut:
    etapes = voyage_etapes(session, voyage.id)
    checklist = voyage_checklist(session, voyage.id)
    return VoyageOut(
        id=voyage.id, titre=voyage.titre,
        date_debut=voyage.date_debut, date_fin=voyage.date_fin,
        depart_iata=voyage.depart_iata, arrivee_iata=voyage.arrivee_iata,
        etapes=[VoyageEtapeOut.model_validate(e, from_attributes=True) for e in etapes],
        checklist=[ChecklistItemOut.model_validate(i, from_attributes=True) for i in checklist],
        budget=BudgetVoyageOut(**aggregate_budget(etapes)),
        checklist_total=len(checklist),
        checklist_faits=sum(1 for i in checklist if i.fait),
    )


def _require_voyage(session: Session, voyage_id: int):
    voyage = get_voyage(session, voyage_id)
    if voyage is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Voyage {voyage_id} introuvable")
    return voyage


@router.get("/voyages", response_model=list[VoyageOut])
def get_voyages(session: Session = Depends(get_session)) -> list[VoyageOut]:
    return [_voyage_out(session, v) for v in list_voyages(session)]


@router.get("/voyages/{voyage_id}", response_model=VoyageOut)
def get_voyage_detail(voyage_id: int, session: Session = Depends(get_session)) -> VoyageOut:
    return _voyage_out(session, _require_voyage(session, voyage_id))


@router.delete("/voyages/{voyage_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_voyage_route(voyage_id: int, session: Session = Depends(get_session)) -> None:
    _require_voyage(session, voyage_id)
    delete_voyage(session, voyage_id)


@router.patch("/voyages/{voyage_id}/etapes/{etape_id}", response_model=VoyageEtapeOut)
def patch_etape_cout_reel(
    voyage_id: int, etape_id: int, req: CoutReelRequest,
    session: Session = Depends(get_session),
) -> VoyageEtapeOut:
    _require_voyage(session, voyage_id)
    etape = set_cout_reel(session, voyage_id, etape_id, req.cout_reel)
    if etape is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Étape {etape_id} introuvable")
    return VoyageEtapeOut.model_validate(etape, from_attributes=True)


@router.post("/voyages/{voyage_id}/checklist", response_model=ChecklistItemOut,
             status_code=status.HTTP_201_CREATED)
def post_checklist_item(
    voyage_id: int, req: ChecklistItemCreate, session: Session = Depends(get_session),
) -> ChecklistItemOut:
    _require_voyage(session, voyage_id)
    item = add_checklist_item(session, voyage_id, req.label)
    return ChecklistItemOut.model_validate(item, from_attributes=True)


@router.patch("/voyages/{voyage_id}/checklist/{item_id}", response_model=ChecklistItemOut)
def patch_checklist_item(
    voyage_id: int, item_id: int, req: ChecklistItemUpdate,
    session: Session = Depends(get_session),
) -> ChecklistItemOut:
    _require_voyage(session, voyage_id)
    item = update_checklist_item(
        session, voyage_id, item_id, label=req.label, fait=req.fait, ordre=req.ordre,
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Item {item_id} introuvable")
    return ChecklistItemOut.model_validate(item, from_attributes=True)


@router.delete("/voyages/{voyage_id}/checklist/{item_id}",
               status_code=status.HTTP_204_NO_CONTENT)
def delete_checklist_item_route(
    voyage_id: int, item_id: int, session: Session = Depends(get_session),
) -> None:
    _require_voyage(session, voyage_id)
    if not delete_checklist_item(session, voyage_id, item_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Item {item_id} introuvable")
