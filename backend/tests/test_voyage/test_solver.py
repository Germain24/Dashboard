"""Solveur d'itinéraire — circuit optionnel OR-Tools CP-SAT."""
from __future__ import annotations

import itertools

from app.services.voyage.solver import solve_itinerary, solve_top_k_itineraries, transit_cost


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
    """3 candidats à budget/jours tendus (budget=1400, jours=9, coût de
    subsistance en transit inclus) : le solveur doit en retenir exactement 2,
    pas 3, pas 1. Il reste alors un peu de marge -> comblée entièrement dans
    UN SEUL des deux lieux retenus, l'autre gardant sa durée minimale."""
    result = solve_itinerary(CANDIDATS_3, TRAJETS_3, budget_total=1400, jours_disponibles=9)
    assert result is not None
    assert len(result) == 2
    jours = sorted(r["jours"] for r in result)
    assert jours == [2, 3]  # jours_min inchangé pour l'un, le reste de la marge comblé dans l'autre


def test_all_candidates_fit_when_budget_and_time_allow():
    result = solve_itinerary(CANDIDATS_3, TRAJETS_3, budget_total=1800, jours_disponibles=10)
    assert result is not None
    assert len(result) == 3


def test_returns_empty_list_when_no_candidate_fits_but_direct_trip_does():
    result = solve_itinerary(CANDIDATS_3, TRAJETS_3, budget_total=250, jours_disponibles=1)
    assert result == []


def test_returns_none_when_even_direct_trip_is_infeasible():
    result = solve_itinerary(CANDIDATS_3, TRAJETS_3, budget_total=50, jours_disponibles=0)
    assert result is None


def test_fills_remaining_budget_and_days_without_jours_max_cap():
    """Budget/jours très larges par rapport au séjour minimal -> le solveur ne
    laisse pas les vacances/le budget inutilisés : il prolonge le séjour dans
    le lieu retenu jusqu'à épuiser le budget ou les jours disponibles, SANS
    être plafonné par jours_max=3 (on ne visite plus rien de spécial à ce
    stade, donc ce plafond touristique ne s'applique pas)."""
    candidats = [{"id": "X", "jours_min": 1, "jours_max": 3, "cout_jour": 10.0}]
    points = ["DEPART", "X", "ARRIVEE"]
    trajets = _trajets_uniformes(points, prix=10.0, duree_min=60)
    result = solve_itinerary(candidats, trajets, budget_total=1000, jours_disponibles=30)
    assert result is not None
    assert result[0]["jours"] == 28  # dépasse jours_max=3 : les 27 jours restants (budget largement suffisant) sont tous utilisés


def test_top_k_returns_distinct_visited_sets_ranked_best_first():
    # 3 candidats, budget/jours permettant exactement 2 a la fois (comme le
    # test single-solve ci-dessus) -> plusieurs paires distinctes possibles.
    results = solve_top_k_itineraries(CANDIDATS_3, TRAJETS_3, budget_total=1400, jours_disponibles=9, k=10)
    assert len(results) >= 2
    seen_sets = [frozenset(r["id"] for r in itin) for itin in results]
    assert len(seen_sets) == len(set(seen_sets))  # tous distincts
    # C(3,2)=3 paires distinctes possibles au meilleur score (2 lieux) ; une
    # fois épuisées, le solveur redescend vers des ensembles moins bons (1
    # lieu) plutôt que de s'arrêter -> seuls les premiers résultats sont à 2.
    assert len(seen_sets[0]) == 2
    assert all(len(s) == 2 for s in seen_sets[:3])
    # Le premier resultat doit matcher exactement ce que solve_itinerary (le
    # meilleur seul) renvoie comme ensemble de lieux.
    single = solve_itinerary(CANDIDATS_3, TRAJETS_3, budget_total=1400, jours_disponibles=9)
    assert frozenset(r["id"] for r in single) in seen_sets


def test_top_k_stops_early_when_fewer_than_k_solutions_exist():
    # Budget/jours n'autorisant qu'UN seul lieu a la fois parmi les 3 -> au
    # plus 3 combinaisons distinctes possibles (1 par candidat), meme si k=10.
    results = solve_top_k_itineraries(CANDIDATS_3, TRAJETS_3, budget_total=750, jours_disponibles=4, k=10)
    assert 1 <= len(results) <= 3
    for itin in results:
        assert len(itin) == 1


def test_top_k_empty_when_infeasible():
    results = solve_top_k_itineraries(CANDIDATS_3, TRAJETS_3, budget_total=50, jours_disponibles=0, k=10)
    assert results == []


def test_departure_and_arrival_can_differ():
    """DEPART != ARRIVEE (pas de retour au point de départ) — vérifie que le
    solveur ne force pas un aller-retour."""
    result = solve_itinerary(CANDIDATS_3, TRAJETS_3, budget_total=1400, jours_disponibles=10,
                              depart_id="DEPART", arrivee_id="ARRIVEE")
    assert result is not None
    ids_visites = {r["id"] for r in result}
    assert "DEPART" not in ids_visites and "ARRIVEE" not in ids_visites


def test_fills_only_cheapest_candidate_when_several_selected():
    """2 lieux retenus, coûts/jour différents -> le budget/temps restant est
    entièrement dépensé sur le MOINS CHER (10$/j), le plus cher (100$/j)
    gardant sa durée minimale."""
    candidats = [
        {"id": "Cher", "jours_min": 1, "jours_max": 10, "cout_jour": 100.0},
        {"id": "Pascher", "jours_min": 1, "jours_max": 10, "cout_jour": 10.0},
    ]
    points = ["DEPART", "Cher", "Pascher", "ARRIVEE"]
    trajets = _trajets_uniformes(points, prix=0.0, duree_min=0)
    result = solve_itinerary(candidats, trajets, budget_total=200, jours_disponibles=30)
    assert result is not None
    par_id = {r["id"]: r["jours"] for r in result}
    # budget_total=200, 2 jours_min consommés (1 chacun) laisse 190$ -- tout
    # dépensé sur "Pascher" (10$/j, 9 jours de plus = 90$) avant de toucher à "Cher".
    assert par_id["Pascher"] == 10
    assert par_id["Cher"] == 1  # jours_min : rien ne justifie d'y rester plus cher


def test_transit_cost_averages_endpoints_with_majoration():
    # Moyenne des deux coûts/jour (100 et 50 -> 75), x1 jour, x1.2 (aéroport/transit).
    assert transit_cost(100.0, 50.0, 1) == 90.0


def test_transit_cost_scales_with_travel_days():
    assert transit_cost(100.0, 100.0, 3) == 3 * transit_cost(100.0, 100.0, 1)


def test_transit_cost_zero_when_both_endpoints_free():
    # DEPART/ARRIVEE (aéroport d'origine du voyageur, pas un lieu à budget).
    assert transit_cost(0.0, 0.0, 2) == 0.0


def test_top_k_diversifies_by_country_not_just_by_lieu():
    """3 pays A/B/C avec plusieurs lieux chacun, tous aussi avantageux les uns
    que les autres -- sans diversité par pays, le solveur pourrait renvoyer k
    variations de "3 lieux en A + 1 en B" ne différant que par LESQUELS. Ici
    on vérifie que les résultats touchent des COMBINAISONS DE PAYS distinctes."""
    candidats = (
        [{"id": f"A{i}", "jours_min": 1, "jours_max": 1, "cout_jour": 10.0, "pays": "A"} for i in range(1, 4)]
        + [{"id": f"B{i}", "jours_min": 1, "jours_max": 1, "cout_jour": 10.0, "pays": "B"} for i in range(1, 4)]
        + [{"id": f"C{i}", "jours_min": 1, "jours_max": 1, "cout_jour": 10.0, "pays": "C"} for i in range(1, 3)]
    )
    pays_by_id = {c["id"]: c["pays"] for c in candidats}
    points = ["DEPART"] + [c["id"] for c in candidats] + ["ARRIVEE"]
    trajets = _trajets_uniformes(points, prix=0.0, duree_min=0)
    results = solve_top_k_itineraries(candidats, trajets, budget_total=40, jours_disponibles=4, k=5)
    pays_combos = [frozenset(pays_by_id[r["id"]] for r in itin) for itin in results]
    assert len(pays_combos) >= 2
    assert len(pays_combos) == len(set(pays_combos))  # distincts par PAYS, pas seulement par lieu


def test_top_k_ranks_by_cost_when_tied_on_number_of_lieux():
    """À nombre de lieux égal (2, le max possible ici), le classement final
    doit privilégier le coût total le plus bas, pas l'ordre interne CP-SAT."""
    results = solve_top_k_itineraries(CANDIDATS_3, TRAJETS_3, budget_total=1400, jours_disponibles=9, k=10)
    couts = []
    for itin in results:
        trajet_ids = ["DEPART"] + [e["id"] for e in itin] + ["ARRIVEE"]
        cout = sum(TRAJETS_3[(a, b)]["prix"] for a, b in zip(trajet_ids, trajet_ids[1:]))
        cout += sum(100.0 * e["jours"] for e in itin)  # cout_jour=100 pour les 3 candidats
        couts.append(cout)
    tailles = [len(itin) for itin in results]
    # Tant que la taille reste au max (2), le coût doit être croissant.
    max_taille = max(tailles)
    couts_au_max = [c for c, t in zip(couts, tailles) if t == max_taille]
    assert couts_au_max == sorted(couts_au_max)
