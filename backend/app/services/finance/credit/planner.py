"""Simulation mois par mois du score de crédit et de la marge totale (#marge-credit v2).

Fonction pure : ne touche pas la DB. `build_plan` prend l'état courant
(comptes actifs, historique réel de score, règles de seuils définies par
l'utilisateur) et simule mois par mois de `today` à `date_cible` : le score
projeté avance selon la pente déduite des 2 points extrêmes de l'historique
réel, et dès qu'il franchit un seuil non consommé (dans l'ordre croissant),
l'action correspondante s'applique (marge += montant_estime, score -=
SCORE_IMPACT_PAR_ACTION). Aucune notion de banque : les règles ne portent
que sur un seuil de score, un type d'action et un montant estimé.
"""

from __future__ import annotations

import datetime as dt

SCORE_IMPACT_PAR_ACTION = 10  # points perdus après chaque action déclenchée (hausse ou nouvelle carte)


def _months_between(d1: dt.date, d2: dt.date) -> int:
    """Nombre de mois pleins entre d1 et d2 (d2 >= d1 attendu)."""
    return (d2.year - d1.year) * 12 + (d2.month - d1.month)


def _month_range(start: dt.date, end: dt.date) -> list[dt.date]:
    """Premier jour de chaque mois, de start (mois inclus) à end (mois inclus)."""
    cur = dt.date(start.year, start.month, 1)
    last = dt.date(end.year, end.month, 1)
    months = []
    while cur <= last:
        months.append(cur)
        cur = dt.date(cur.year + 1, 1, 1) if cur.month == 12 else dt.date(cur.year, cur.month + 1, 1)
    return months


def build_plan(accounts, score_history, rules, date_cible: dt.date, today: dt.date) -> dict:
    marge_actuelle = round(sum(a.limite_actuelle for a in accounts if a.statut == "actif"), 2)
    historique_score = [{"date": s.date, "score": s.score} for s in sorted(score_history, key=lambda s: s.date)]
    historique_marge = [{"date": today, "marge_totale": marge_actuelle}]

    if len(historique_score) < 2:
        return {
            "marge_actuelle": marge_actuelle,
            "historique_score": historique_score,
            "historique_marge": historique_marge,
            "projection_score": [],
            "projection_marge": [],
            "actions": [],
            "projection_possible": False,
        }

    premier, dernier = historique_score[0], historique_score[-1]
    mois_ecoules = _months_between(premier["date"], dernier["date"])
    pente = (dernier["score"] - premier["score"]) / mois_ecoules if mois_ecoules > 0 else 0.0

    rules_triees = sorted(rules, key=lambda r: r.seuil_score)
    consumed = [False] * len(rules_triees)

    score = float(dernier["score"])
    marge = marge_actuelle
    actions: list[dict] = []
    projection_score: list[dict] = []
    projection_marge: list[dict] = []

    for month in _month_range(today, date_cible):
        score += pente
        while True:
            next_idx = next(
                (i for i, r in enumerate(rules_triees) if not consumed[i] and score >= r.seuil_score),
                None,
            )
            if next_idx is None:
                break
            rule = rules_triees[next_idx]
            marge += rule.montant_estime
            score -= SCORE_IMPACT_PAR_ACTION
            consumed[next_idx] = True
            actions.append({
                "date": month,
                "type": rule.type,
                "seuil_score": rule.seuil_score,
                "montant_estime": rule.montant_estime,
            })
        projection_score.append({"date": month, "score": round(score, 1)})
        projection_marge.append({"date": month, "marge_totale": round(marge, 2)})

    return {
        "marge_actuelle": marge_actuelle,
        "historique_score": historique_score,
        "historique_marge": historique_marge,
        "projection_score": projection_score,
        "projection_marge": projection_marge,
        "actions": actions,
        "projection_possible": True,
    }
