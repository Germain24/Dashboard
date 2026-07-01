"""Solveur d'itinéraire — circuit optionnel (OR-Tools CP-SAT).

Modélise le choix des lieux à visiter + leur ordre comme un TSP à sélection
de nœuds (proche d'un « Orienteering Problem ») : chaque candidat a une
boucle sur lui-même (non retenu) ou fait partie du chemin
depart -> ... -> arrivee. Un arc virtuel arrivee -> depart (coût/durée nuls)
ferme le circuit pour satisfaire la contrainte `AddCircuit` de CP-SAT — ce
n'est pas un vrai trajet, juste un artifice de modélisation.

Objectif lexicographique : (1) maximiser le nombre de lieux retenus, sous
contrainte de jours disponibles et de budget total (transport + coût/jour ×
durée du séjour) ; (2) à nombre égal, minimiser le total de jours utilisés
(un lieu retenu reçoit sa durée minimale, sauf si en rester justifié par
ailleurs — ce qui ne se produit jamais dans ce modèle).
"""
from __future__ import annotations

import math
from typing import Optional

from ortools.sat.python import cp_model


def solve_itinerary(
    candidats: list[dict],
    trajets: dict[tuple[str, str], dict],
    budget_total: float,
    jours_disponibles: int,
    depart_id: str = "DEPART",
    arrivee_id: str = "ARRIVEE",
) -> Optional[list[dict]]:
    """Choisit un sous-ensemble ordonné de `candidats` maximisant leur nombre.

    `candidats` : [{"id": str, "jours_min": int, "jours_max": int, "cout_jour": float}, ...]
    `trajets` : prix/durée pour CHAQUE paire ordonnée (i, j) parmi
    {depart_id} ∪ {candidat["id"] pour chaque candidat} ∪ {arrivee_id}, i != j.

    Retourne les lieux retenus dans l'ordre du parcours, avec la durée de
    séjour assignée : [{"id": str, "jours": int}, ...]. Liste vide si aucun
    candidat ne rentre mais que depart->arrivee direct est faisable. `None`
    si même le trajet direct dépasse le budget ou les jours disponibles.
    """
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

    total_days = list(duree_days.values())
    total_cost = []
    for (i, j), lit in arc_lit.items():
        if (i, j) == (arrivee_idx, depart_idx):
            continue  # arc virtuel : pas un vrai trajet, ne consomme rien
        t = trajets[(ids[i], ids[j])]
        travel_days = math.ceil(t["duree_min"] / 1440)
        if travel_days:
            total_days.append(cp_model.LinearExpr.Term(lit, travel_days))
        total_cost.append(cp_model.LinearExpr.Term(lit, round(t["prix"])))
    for c in candidats:
        i = idx[c["id"]]
        total_cost.append(cp_model.LinearExpr.Term(duree_days[i], round(c["cout_jour"])))

    model.Add(cp_model.LinearExpr.Sum(total_days) <= jours_disponibles)
    model.Add(cp_model.LinearExpr.Sum(total_cost) <= round(budget_total))

    # Objectif lexicographique : (1) maximiser le nombre de lieux visités,
    # (2) à égalité, minimiser le total de jours utilisés. Sans (2), la durée
    # d'un candidat retenu dans [jours_min, jours_max] n'est contrainte par
    # rien d'autre et CP-SAT peut renvoyer n'importe quelle valeur de la
    # fourchette — constaté non déterministe d'une machine à l'autre avec
    # l'objectif (1) seul. BIG doit dominer strictement le terme secondaire,
    # qui est borné par jours_disponibles via la contrainte ci-dessus.
    BIG = jours_disponibles + 1
    n_visites = sum(1 - skip_lit[idx[c["id"]]] for c in candidats)
    model.Maximize(n_visites * BIG - cp_model.LinearExpr.Sum(total_days))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    # reconstruit l'ordre du parcours en suivant les arcs retenus depuis depart
    ordre: list[str] = []
    current = depart_idx
    while current != arrivee_idx:
        nxt = next(j for (i, j), lit in arc_lit.items() if i == current and solver.Value(lit) == 1)
        if nxt != arrivee_idx:
            ordre.append(ids[nxt])
        current = nxt

    return [{"id": nom_id, "jours": solver.Value(duree_days[idx[nom_id]])} for nom_id in ordre]
