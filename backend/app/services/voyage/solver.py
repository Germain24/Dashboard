"""Solveur d'itinéraire — circuit optionnel (OR-Tools CP-SAT).

Modélise le choix des lieux à visiter + leur ordre comme un TSP à sélection
de nœuds (proche d'un « Orienteering Problem ») : chaque candidat a une
boucle sur lui-même (non retenu) ou fait partie du chemin
depart -> ... -> arrivee. Un arc virtuel arrivee -> depart (coût/durée nuls)
ferme le circuit pour satisfaire la contrainte `AddCircuit` de CP-SAT — ce
n'est pas un vrai trajet, juste un artifice de modélisation.

Algorithme en deux temps :
  1. CP-SAT choisit le sous-ensemble de candidats à visiter, objectif
     lexicographique (a) maximiser le nombre de lieux retenus sous contrainte
     de jours disponibles et de budget total (transport + subsistance pendant
     les jours de trajet, cf. `transit_cost` + coût/jour × durée du séjour),
     (b) à nombre égal, minimiser le total de jours utilisés (chaque lieu
     retenu reçoit sa durée minimale).
  2. S'il reste du budget ET des jours de vacances non utilisés après (1), on
     les comble entièrement en restant plus longtemps dans le lieu déjà
     retenu le MOINS CHER (pas de nouveau trajet, juste profiter sans rien
     visiter de spécial -- donc SANS plafond de jours_max, qui borne la durée
     d'intérêt touristique, pas celle d'un simple séjour de détente) -- jusqu'à
     épuiser le budget ou les jours restants, l'un des deux servant de limite.

`solve_top_k_itineraries` génère plusieurs itinéraires visitant des
COMBINAISONS DE PAYS DISTINCTES (pas juste des choix de lieux différents au
sein des 2-3 mêmes pays les plus avantageux, ce qui donnait des résultats
quasi identiques) à nombre maximal de lieux égal, chacun complété par (2),
puis les classe par coût total croissant.
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

    return model, ids, idx, depart_idx, arrivee_idx, skip_lit, duree_days, arc_lit, pays_lit


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
    """S'il reste du budget ET des jours après le choix des lieux à visiter,
    prolonge le séjour dans le lieu déjà retenu le MOINS CHER (pas de trajet
    supplémentaire) pour épuiser le budget/temps de vacances plutôt que de le
    laisser inutilisé -- SANS plafond de jours_max (on ne visite plus rien de
    spécial à ce stade, juste se reposer au meilleur prix)."""
    if not resultat:
        return resultat
    cout_actuel, jours_actuels = _cout_et_jours(resultat, candidats_by_id, trajets, depart_id, arrivee_id)
    reste_jours = jours_disponibles - jours_actuels
    reste_budget = budget_total - cout_actuel
    if reste_jours <= 0 or reste_budget <= 0:
        return resultat

    moins_cher = min(resultat, key=lambda e: candidats_by_id[e["id"]]["cout_jour"])
    cout_jour = candidats_by_id[moins_cher["id"]]["cout_jour"]
    extra = reste_jours if cout_jour <= 0 else min(reste_jours, int(reste_budget // cout_jour))
    if extra <= 0:
        return resultat
    return [{**e, "jours": e["jours"] + extra} if e is moins_cher else dict(e) for e in resultat]


def solve_itinerary(
    candidats: list[dict],
    trajets: dict[tuple[str, str], dict],
    budget_total: float,
    jours_disponibles: int,
    depart_id: str = "DEPART",
    arrivee_id: str = "ARRIVEE",
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
    model, ids, idx, depart_idx, arrivee_idx, skip_lit, duree_days, arc_lit, _pays_lit = _build_model(
        candidats, trajets, budget_total, jours_disponibles, depart_id, arrivee_id,
    )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10
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
) -> list[list[dict]]:
    """Comme `solve_itinerary`, mais renvoie jusqu'à `k` itinéraires visitant
    des COMBINAISONS DE PAYS DISTINCTES. Après chaque solution, on interdit de
    reproduire EXACTEMENT le même ensemble de pays visités (peu importe quels
    lieux précis dans chaque pays) et on resolve -- s'arrête dès que le modèle
    devient infaisable (plus aucune combinaison de pays distincte sous
    budget/temps) ou que `k` est atteint. Chaque résultat est ensuite complété
    (jours restants comblés au lieu le moins cher) et la liste est reclassée :
    nombre de lieux décroissant, puis coût total croissant (à nombre égal, le
    moins cher gagne)."""
    model, ids, idx, depart_idx, arrivee_idx, skip_lit, duree_days, arc_lit, pays_lit = _build_model(
        candidats, trajets, budget_total, jours_disponibles, depart_id, arrivee_id,
    )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 8

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
        not_visited_pays = [p for p in pays_lit if p not in visited_pays]
        # Interdit EXACTEMENT le même ensemble de pays visités/écartés (au
        # moins un pays doit changer, peu importe les lieux précis dedans).
        model.AddBoolOr(
            [pays_lit[p].Not() for p in visited_pays] + [pays_lit[p] for p in not_visited_pays]
        )

    candidats_by_id = {c["id"]: c for c in candidats}
    remplis = [
        _remplir_jours_restants(r, candidats_by_id, trajets, budget_total, jours_disponibles, depart_id, arrivee_id)
        for r in bruts
    ]
    remplis.sort(key=lambda r: (
        -len(r), _cout_et_jours(r, candidats_by_id, trajets, depart_id, arrivee_id)[0],
    ))
    return remplis
