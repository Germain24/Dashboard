"""Solveur d'itinéraire — circuit optionnel OR-Tools CP-SAT."""
from __future__ import annotations

import itertools

from app.services.voyage.solver import solve_itinerary


def _trajets_uniformes(points: list[str], prix: float, duree_min: int) -> dict:
    return {(a, b): {"prix": prix, "duree_min": duree_min} for a, b in itertools.permutations(points, 2)}


CANDIDATS_3 = [
    {"id": "X", "jours_min": 2, "jours_max": 4, "cout_jour": 100.0},
    {"id": "Y", "jours_min": 2, "jours_max": 3, "cout_jour": 100.0},
    {"id": "Z", "jours_min": 2, "jours_max": 3, "cout_jour": 100.0},
]
POINTS_3 = ["DEPART", "X", "Y", "Z", "ARRIVEE"]
TRAJETS_3 = _trajets_uniformes(POINTS_3, prix=200.0, duree_min=300)


def test_selects_max_candidates_within_tight_budget():
    """3 candidats coûtent exactement pile (budget=1400, jours=9 -> tous les 3
    tiennent tout juste à 10j/1400$ mais pas à 9j/1400$) : le solveur doit en
    retenir exactement 2, pas 3, pas 1."""
    result = solve_itinerary(CANDIDATS_3, TRAJETS_3, budget_total=1400, jours_disponibles=9)
    assert result is not None
    assert len(result) == 2
    assert all(r["jours"] == 2 for r in result)  # jours_min respecté (le minimum suffit ici)


def test_all_candidates_fit_when_budget_and_time_allow():
    result = solve_itinerary(CANDIDATS_3, TRAJETS_3, budget_total=1400, jours_disponibles=10)
    assert result is not None
    assert len(result) == 3


def test_returns_empty_list_when_no_candidate_fits_but_direct_trip_does():
    result = solve_itinerary(CANDIDATS_3, TRAJETS_3, budget_total=250, jours_disponibles=1)
    assert result == []


def test_returns_none_when_even_direct_trip_is_infeasible():
    result = solve_itinerary(CANDIDATS_3, TRAJETS_3, budget_total=50, jours_disponibles=0)
    assert result is None


def test_defaults_to_shortest_stay_when_unconstrained():
    """Rien ne pousse vers une durée précise dans [jours_min, jours_max] hormis
    l'objectif secondaire (minimiser le total de jours à nombre de lieux égal)
    -> sans lui, CP-SAT peut légitimement choisir n'importe quelle valeur de la
    fourchette et le résultat devient non déterministe d'une machine à l'autre
    (constaté en le vérifiant sur deux machines différentes avant ce plan)."""
    candidats = [{"id": "X", "jours_min": 1, "jours_max": 3, "cout_jour": 10.0}]
    points = ["DEPART", "X", "ARRIVEE"]
    trajets = _trajets_uniformes(points, prix=10.0, duree_min=60)
    result = solve_itinerary(candidats, trajets, budget_total=1000, jours_disponibles=30)
    assert result is not None
    assert result[0]["jours"] == 1  # jours_min : rien ne justifie de rester plus longtemps


def test_departure_and_arrival_can_differ():
    """DEPART != ARRIVEE (pas de retour au point de départ) — vérifie que le
    solveur ne force pas un aller-retour."""
    result = solve_itinerary(CANDIDATS_3, TRAJETS_3, budget_total=1400, jours_disponibles=10,
                              depart_id="DEPART", arrivee_id="ARRIVEE")
    assert result is not None
    ids_visites = {r["id"] for r in result}
    assert "DEPART" not in ids_visites and "ARRIVEE" not in ids_visites
