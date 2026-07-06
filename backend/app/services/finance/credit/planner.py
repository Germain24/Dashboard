"""Simulation mois par mois de la marge de crédit totale (#marge-credit).

Fonction pure : ne touche pas la DB. `build_plan` prend l'état courant
(comptes, historique de pointage, profil) et un catalogue de produits
candidats, et simule mois par mois de `today` à `profile.date_cible` pour
produire une feuille de route d'actions recommandées + une projection de la
marge totale. Aucune extrapolation du pointage : on utilise le dernier
pointage connu à chaque mois (pas de prédiction de progression).
"""

from __future__ import annotations

import datetime as dt

from app.services.finance.credit.catalog import DEFAULT_HAUSSE_RULE, CreditProduct

ANTI_INQUIRY_COOLDOWN_MOIS = 4  # au plus 1 nouvelle demande d'ouverture tous les N mois
HAUSSE_PCT = 0.5  # heuristique : +50% de la limite courante à chaque hausse accordée


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


def _score_at(score_history: list, on_date: dt.date) -> int | None:
    """Dernier pointage connu à une date <= on_date, sinon None."""
    known = [s for s in score_history if s.date <= on_date]
    if not known:
        return None
    return max(known, key=lambda s: s.date).score


def _match_rule(catalog: list[CreditProduct], institution: str, produit: str) -> CreditProduct:
    for p in catalog:
        if p.institution.strip().lower() == institution.strip().lower() and p.produit.strip().lower() == produit.strip().lower():
            return p
    return DEFAULT_HAUSSE_RULE


def build_plan(accounts, score_history, profile, catalog: list[CreditProduct], today: dt.date) -> dict:
    sim = [
        {
            "institution": a.institution,
            "produit": a.produit,
            "limite": a.limite_actuelle,
            "date_ouverture": a.date_ouverture,
            "derniere_hausse": a.derniere_augmentation,
        }
        for a in accounts
        if a.statut == "actif"
    ]
    opened = {(a["institution"].strip().lower(), a["produit"].strip().lower()) for a in sim}
    marge_actuelle = sum(a["limite"] for a in sim)

    actions: list[dict] = []
    projection: list[dict] = []
    last_new_account_month: dt.date | None = None

    for month in _month_range(today, profile.date_cible):
        score = _score_at(score_history, month)
        anciennete_canada = _months_between(profile.date_arrivee_canada, month)

        # 1. Demandes de hausse sur les comptes existants (simulés).
        for acc in sim:
            rule = _match_rule(catalog, acc["institution"], acc["produit"])
            reference = acc["derniere_hausse"] or acc["date_ouverture"]
            months_since = _months_between(reference, month)
            seuil = rule.cooldown_hausse_mois if acc["derniere_hausse"] else rule.anciennete_min_avant_1ere_hausse_mois
            score_ok = rule.score_min_requis is None or (score is not None and score >= rule.score_min_requis)
            if months_since >= seuil and score_ok:
                delta = round(acc["limite"] * HAUSSE_PCT, 2)
                reference_label = "la dernière hausse" if acc["derniere_hausse"] else "l'ouverture"
                actions.append({
                    "date": month,
                    "type": "hausse",
                    "institution": acc["institution"],
                    "produit": acc["produit"],
                    "delta_limite": delta,
                    "justification": (
                        f"{months_since} mois depuis {reference_label} (seuil {seuil}), "
                        f"score {'inconnu' if score is None else score} (minimum {rule.score_min_requis or 'aucun'})"
                    ),
                })
                acc["limite"] += delta
                acc["derniere_hausse"] = month

        # 2. Ouverture d'un nouveau produit (au plus 1 tous les ANTI_INQUIRY_COOLDOWN_MOIS).
        can_open = (
            last_new_account_month is None
            or _months_between(last_new_account_month, month) >= ANTI_INQUIRY_COOLDOWN_MOIS
        )
        if can_open:
            candidats = [
                p for p in catalog
                if (p.institution.strip().lower(), p.produit.strip().lower()) not in opened
                and anciennete_canada >= p.anciennete_min_mois
                and (p.score_min_requis is None or (score is not None and score >= p.score_min_requis))
            ]
            if candidats:
                meilleur = max(candidats, key=lambda p: (p.limite_min + p.limite_max) / 2)
                limite_depart = min(meilleur.limite_max, max(meilleur.limite_min, profile.revenu_annuel * 0.1))
                actions.append({
                    "date": month,
                    "type": "ouverture",
                    "institution": meilleur.institution,
                    "produit": meilleur.produit,
                    "delta_limite": round(limite_depart, 2),
                    "justification": (
                        f"éligible : {anciennete_canada} mois au Canada, "
                        f"score {'inconnu' if score is None else score} (minimum {meilleur.score_min_requis or 'aucun'})"
                    ),
                })
                sim.append({
                    "institution": meilleur.institution,
                    "produit": meilleur.produit,
                    "limite": limite_depart,
                    "date_ouverture": month,
                    "derniere_hausse": None,
                })
                opened.add((meilleur.institution.strip().lower(), meilleur.produit.strip().lower()))
                last_new_account_month = month

        projection.append({"date": month, "marge_totale": round(sum(a["limite"] for a in sim), 2)})

    return {
        "marge_actuelle": round(marge_actuelle, 2),
        "marge_projetee_a_date_cible": projection[-1]["marge_totale"] if projection else round(marge_actuelle, 2),
        "actions": actions,
        "projection": projection,
    }
