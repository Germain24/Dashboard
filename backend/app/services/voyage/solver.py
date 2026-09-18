"""Solveur d'itinéraire — circuit optionnel (OR-Tools CP-SAT).

Modélise le choix des lieux à visiter + leur ordre comme un TSP à sélection
de nœuds (proche d'un « Orienteering Problem ») : chaque candidat a une
boucle sur lui-même (non retenu) ou fait partie du chemin
depart -> ... -> arrivee. Un arc virtuel arrivee -> depart (coût/durée nuls)
ferme le circuit pour satisfaire la contrainte `AddCircuit` de CP-SAT — ce
n'est pas un vrai trajet, juste un artifice de modélisation.

Algorithme en deux temps :
  1. CP-SAT maximise une valeur de voyage : priorité des activités, diversité
     des pays et des hubs, puis pénalise coût et temps de transport.
  2. Les jours restants sont distribués dans les limites `jours_max`, en
     privilégiant les étapes à forte priorité. Le solveur n'invente plus un
     séjour démesuré dans le lieu le moins cher.

`solve_top_k_itineraries` impose un recouvrement maximal entre les hubs et les
pays des propositions afin que les alternatives soient réellement distinctes.
"""
from __future__ import annotations

import math
from typing import Optional

from ortools.sat.python import cp_model

# Un jour de trajet n'est pas gratuit : on mange et on dort quand même, même
# sans rien "visiter" ce jour-là. Estimé comme la moyenne des coûts/jour des
# deux extrémités du trajet (0 pour DEPART/ARRIVEE, qui n'ont pas de coût/jour
# -- le budget vacances ne couvre pas la vie courante à la maison), majorée
# de 20% (aéroport/transit habituellement plus cher qu'un jour normal en ville).
TRANSIT_MAJORATION = 1.2


def transit_cost(cout_jour_a: float, cout_jour_b: float, travel_days: int) -> float:
    return travel_days * 0.5 * (cout_jour_a + cout_jour_b) * TRANSIT_MAJORATION


def _build_model(
    candidats: list[dict],
    trajets: dict[tuple[str, str], dict],
    budget_total: float,
    jours_disponibles: int,
    depart_id: str,
    arrivee_id: str,
    max_destinations: int | None = None,
):
    """Construit le modèle CP-SAT partagé par `solve_itinerary` et
    `solve_top_k_itineraries` (mêmes variables/contraintes/objectif)."""
    ids = [depart_id] + [c["id"] for c in candidats] + [arrivee_id]
    n = len(ids)
    idx = {v: i for i, v in enumerate(ids)}
    depart_idx, arrivee_idx = 0, n - 1

    model = cp_model.CpModel()

    duree_days: dict[int, cp_model.IntVar] = {}
    skip_lit: dict[int, cp_model.IntVar] = {}
    for c in candidats:
        i = idx[c["id"]]
        duree_days[i] = model.NewIntVar(0, c["jours_max"], f"duree_{i}")
        skip_lit[i] = model.NewBoolVar(f"skip_{i}")
        # 0 jour si écarté (sinon jours_min grève le budget temps même non visité)
        model.Add(duree_days[i] == 0).OnlyEnforceIf(skip_lit[i])
        model.Add(duree_days[i] >= c["jours_min"]).OnlyEnforceIf(skip_lit[i].Not())

    arcs: list[tuple[int, int, cp_model.IntVar]] = []
    arc_lit: dict[tuple[int, int], cp_model.IntVar] = {}
    for i in range(n):
        for j in range(n):
            if i == j:
                if i in skip_lit:
                    arcs.append((i, i, skip_lit[i]))
                continue
            if j == depart_idx and i != arrivee_idx:
                continue  # seule arrivee peut revenir vers depart (ferme le circuit)
            if i == arrivee_idx and j != depart_idx:
                continue  # arrivee ne repart que vers depart
            lit = model.NewBoolVar(f"arc_{i}_{j}")
            arc_lit[(i, j)] = lit
            arcs.append((i, j, lit))

    model.AddCircuit(arcs)
    model.Add(arc_lit[(arrivee_idx, depart_idx)] == 1)  # arc virtuel, toujours emprunté

    candidats_by_id = {c["id"]: c for c in candidats}
    total_days = list(duree_days.values())
    total_cost = []
    for (i, j), lit in arc_lit.items():
        if (i, j) == (arrivee_idx, depart_idx):
            continue  # arc virtuel : pas un vrai trajet, ne consomme rien
        t = trajets[(ids[i], ids[j])]
        travel_days = math.ceil(t["duree_min"] / 1440)
        if travel_days:
            total_days.append(cp_model.LinearExpr.Term(lit, travel_days))
            cout_a = candidats_by_id.get(ids[i], {}).get("cout_jour", 0.0)
            cout_b = candidats_by_id.get(ids[j], {}).get("cout_jour", 0.0)
            cout_transit = round(transit_cost(cout_a, cout_b, travel_days))
            if cout_transit:
                total_cost.append(cp_model.LinearExpr.Term(lit, cout_transit))
        total_cost.append(cp_model.LinearExpr.Term(lit, round(t["prix"])))
    for c in candidats:
        i = idx[c["id"]]
        total_cost.append(cp_model.LinearExpr.Term(duree_days[i], round(c["cout_jour"])))
        fixed_cost = round(c.get("cout_fixe", 0.0))
        if fixed_cost:
            total_cost.append(fixed_cost * (1 - skip_lit[i]))

    model.Add(cp_model.LinearExpr.Sum(total_days) <= jours_disponibles)
    model.Add(cp_model.LinearExpr.Sum(total_cost) <= round(budget_total))

    # Regroupe les candidats par pays (fallback : chaque candidat forme son
    # propre groupe si `pays` est absent -- utilisé par les tests unitaires
    # et rend le groupement inoffensif quand la donnée n'est pas fournie) --
    # sert de granularité de diversité à `solve_top_k_itineraries`, pour éviter
    # de ne proposer que des variations de lieux au sein des 2-3 mêmes pays.
    pays_indices: dict[str, list[int]] = {}
    for c in candidats:
        p = c.get("pays") or c["id"]
        pays_indices.setdefault(p, []).append(idx[c["id"]])
    pays_lit: dict[str, cp_model.IntVar] = {}
    for p, idxs in pays_indices.items():
        lit = model.NewBoolVar(f"pays_{p}")
        model.AddMaxEquality(lit, [skip_lit[i].Not() for i in idxs])
        pays_lit[p] = lit

    hub_indices: dict[str, list[int]] = {}
    for c in candidats:
        hub = c.get("hub") or c["id"]
        hub_indices.setdefault(hub, []).append(idx[c["id"]])
    hub_lit: dict[str, cp_model.IntVar] = {}
    for hub, idxs in hub_indices.items():
        lit = model.NewBoolVar(f"hub_{hub}")
        model.AddMaxEquality(lit, [skip_lit[i].Not() for i in idxs])
        hub_lit[hub] = lit
    if max_destinations is not None:
        model.Add(cp_model.LinearExpr.Sum(list(hub_lit.values())) <= max_destinations)

    # Valeur par activité (priorité 1..5), bonus de vraie diversité, puis
    # pénalités en euros/jours. Les coefficients conservent l'intérêt d'une
    # activité sans rendre le coût invisible comme dans l'ancien objectif.
    activity_value = cp_model.LinearExpr.Sum([
        (100 + 40 * max(1, min(5, int(c.get("priorite", 3))))) * 100
        * (1 - skip_lit[idx[c["id"]]])
        for c in candidats
    ])
    diversity = 2_000 * cp_model.LinearExpr.Sum(list(pays_lit.values()))
    diversity += 1_000 * cp_model.LinearExpr.Sum(list(hub_lit.values()))
    model.Maximize(
        activity_value + diversity
        - cp_model.LinearExpr.Sum(total_cost)
        - 100 * cp_model.LinearExpr.Sum(total_days)
    )

    return (
        model, ids, idx, depart_idx, arrivee_idx, skip_lit, duree_days,
        arc_lit, pays_lit, hub_lit,
    )


def _extract_itinerary(solver, ids, idx, depart_idx, arrivee_idx, duree_days, arc_lit) -> list[dict]:
    """Reconstruit l'ordre du parcours en suivant les arcs retenus depuis depart."""
    ordre: list[str] = []
    current = depart_idx
    while current != arrivee_idx:
        nxt = next(j for (i, j), lit in arc_lit.items() if i == current and solver.Value(lit) == 1)
        if nxt != arrivee_idx:
            ordre.append(ids[nxt])
        current = nxt
    return [{"id": nom_id, "jours": solver.Value(duree_days[idx[nom_id]])} for nom_id in ordre]


def _cout_et_jours(
    resultat: list[dict], candidats_by_id: dict[str, dict],
    trajets: dict[tuple[str, str], dict], depart_id: str, arrivee_id: str,
) -> tuple[float, int]:
    """(coût total, jours totaux) d'un itinéraire déjà résolu (transport +
    subsistance pendant les jours de trajet, entre étapes consécutives, +
    coût/jour × durée de chaque étape)."""
    trajet_ids = [depart_id] + [e["id"] for e in resultat] + [arrivee_id]
    paires = list(zip(trajet_ids, trajet_ids[1:]))
    jours = sum(math.ceil(trajets[(a, b)]["duree_min"] / 1440) for a, b in paires)
    jours += sum(e["jours"] for e in resultat)
    cout = sum(trajets[(a, b)]["prix"] for a, b in paires)
    for a, b in paires:
        travel_days = math.ceil(trajets[(a, b)]["duree_min"] / 1440)
        if travel_days:
            cout_a = candidats_by_id.get(a, {}).get("cout_jour", 0.0)
            cout_b = candidats_by_id.get(b, {}).get("cout_jour", 0.0)
            cout += transit_cost(cout_a, cout_b, travel_days)
    cout += sum(candidats_by_id[e["id"]]["cout_jour"] * e["jours"] for e in resultat)
    return cout, jours


def _remplir_jours_restants(
    resultat: list[dict], candidats_by_id: dict[str, dict],
    trajets: dict[tuple[str, str], dict], budget_total: float, jours_disponibles: int,
    depart_id: str, arrivee_id: str,
) -> list[dict]:
    """Distribue les jours libres sans dépasser la durée pertinente de chaque
    activité. Un reliquat de budget ou de congés est préférable à une fausse
    précision qui inventerait 20 jours sur une activité prévue pour 3."""
    if not resultat:
        return resultat
    cout_actuel, jours_actuels = _cout_et_jours(resultat, candidats_by_id, trajets, depart_id, arrivee_id)
    reste_jours = jours_disponibles - jours_actuels
    reste_budget = budget_total - cout_actuel
    if reste_jours <= 0 or reste_budget <= 0:
        return resultat

    out = [dict(e) for e in resultat]
    ranked = sorted(
        out,
        key=lambda e: (
            -int(candidats_by_id[e["id"]].get("priorite", 3)),
            candidats_by_id[e["id"]]["cout_jour"],
        ),
    )
    for etape in ranked:
        candidat = candidats_by_id[etape["id"]]
        capacity = max(0, int(candidat["jours_max"]) - etape["jours"])
        cout_jour = candidat["cout_jour"]
        affordable = capacity if cout_jour <= 0 else int(reste_budget // cout_jour)
        extra = min(capacity, reste_jours, affordable)
        etape["jours"] += extra
        reste_jours -= extra
        reste_budget -= extra * cout_jour
        if reste_jours <= 0 or reste_budget <= 0:
            break
    return out


def solve_itinerary(
    candidats: list[dict],
    trajets: dict[tuple[str, str], dict],
    budget_total: float,
    jours_disponibles: int,
    depart_id: str = "DEPART",
    arrivee_id: str = "ARRIVEE",
    max_destinations: int | None = None,
) -> Optional[list[dict]]:
    """Choisit un sous-ensemble ordonné de `candidats` maximisant leur nombre,
    puis comble le budget/temps restant (cf. docstring du module).

    `candidats` : [{"id": str, "jours_min": int, "jours_max": int, "cout_jour": float}, ...]
    `trajets` : prix/durée pour CHAQUE paire ordonnée (i, j) parmi
    {depart_id} ∪ {candidat["id"] pour chaque candidat} ∪ {arrivee_id}, i != j.

    Retourne les lieux retenus dans l'ordre du parcours, avec la durée de
    séjour assignée : [{"id": str, "jours": int}, ...]. Liste vide si aucun
    candidat ne rentre mais que depart->arrivee direct est faisable. `None`
    si même le trajet direct dépasse le budget ou les jours disponibles.
    """
    (
        model, ids, idx, depart_idx, arrivee_idx, skip_lit, duree_days,
        arc_lit, _pays_lit, _hub_lit,
    ) = _build_model(
        candidats, trajets, budget_total, jours_disponibles, depart_id, arrivee_id,
        max_destinations,
    )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 3
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    resultat = _extract_itinerary(solver, ids, idx, depart_idx, arrivee_idx, duree_days, arc_lit)
    candidats_by_id = {c["id"]: c for c in candidats}
    return _remplir_jours_restants(
        resultat, candidats_by_id, trajets, budget_total, jours_disponibles, depart_id, arrivee_id,
    )


def solve_top_k_itineraries(
    candidats: list[dict],
    trajets: dict[tuple[str, str], dict],
    budget_total: float,
    jours_disponibles: int,
    depart_id: str = "DEPART",
    arrivee_id: str = "ARRIVEE",
    k: int = 10,
    max_destinations: int | None = None,
) -> list[list[dict]]:
    """Comme `solve_itinerary`, avec jusqu'à `k` alternatives dont au moins
    50 % des hubs et 40 % des pays diffèrent des solutions précédentes."""
    (
        model, ids, idx, depart_idx, arrivee_idx, skip_lit, duree_days,
        arc_lit, pays_lit, hub_lit,
    ) = _build_model(
        candidats, trajets, budget_total, jours_disponibles, depart_id, arrivee_id,
        max_destinations,
    )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 2
    solver.parameters.num_search_workers = 8

    bruts: list[list[dict]] = []
    for _ in range(k):
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break
        visited = [idx[c["id"]] for c in candidats if solver.Value(skip_lit[idx[c["id"]]]) == 0]
        if not visited:
            break  # rien de retenu -> les tentatives suivantes ne feraient que répéter ça
        bruts.append(_extract_itinerary(solver, ids, idx, depart_idx, arrivee_idx, duree_days, arc_lit))
        visited_pays = [p for p, lit in pays_lit.items() if solver.Value(lit) == 1]
        visited_hubs = [hub for hub, lit in hub_lit.items() if solver.Value(lit) == 1]
        # Chaque nouvelle proposition doit remplacer au moins 50 % des hubs et
        # 40 % des pays. On obtient ainsi de vraies alternatives plutôt que le
        # même voyage dans un ordre légèrement différent.
        if visited_hubs:
            model.Add(
                cp_model.LinearExpr.Sum([hub_lit[hub] for hub in visited_hubs])
                <= math.floor(len(visited_hubs) * 0.50)
            )
        if visited_pays:
            model.Add(
                cp_model.LinearExpr.Sum([pays_lit[pays] for pays in visited_pays])
                <= math.floor(len(visited_pays) * 0.60)
            )

    candidats_by_id = {c["id"]: c for c in candidats}
    remplis = [
        _remplir_jours_restants(r, candidats_by_id, trajets, budget_total, jours_disponibles, depart_id, arrivee_id)
        for r in bruts
    ]
    def quality(r: list[dict]) -> tuple:
        countries = {candidats_by_id[e["id"]].get("pays") for e in r}
        hubs = {candidats_by_id[e["id"]].get("hub", e["id"]) for e in r}
        priority = sum(int(candidats_by_id[e["id"]].get("priorite", 3)) for e in r)
        cost = _cout_et_jours(r, candidats_by_id, trajets, depart_id, arrivee_id)[0]
        return (-priority, -len(countries), -len(hubs), cost)

    remplis.sort(key=quality)
    return remplis
