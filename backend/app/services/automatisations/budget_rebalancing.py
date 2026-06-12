"""Rééquilibrage budgétaire auto en fin de mois (#211).

Analyse les enveloppes du mois écoulé et :
- notifie les catégories en dépassement ou avec beaucoup de reste
- propose d'ajuster les enveloppes du mois suivant
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlmodel import Session, select

from app.models.scheduler import Notification

OVER_PCT = 100.0       # Dépassé
UNDER_MIN_PCT = 30.0   # Usage minimum pour qualifier de "sous-utilisé" (élimine les cat. jamais touchées)
UNDER_MAX_PCT = 75.0   # Usage max pour qualifier de "sous-utilisé" (reste significatif)


def compute_rebalancing(statuts: list[dict]) -> list[dict[str, Any]]:
    """Pur : analyse les statuts d'enveloppes et retourne les catégories à ajuster.

    `over`  : dépassement (depense > budget)
    `under` : fortement sous-utilisé (pct < UNDER_PCT et reste > 20€)
    """
    out: list[dict] = []
    for s in statuts:
        budget = s.get("budget", 0.0)
        if budget <= 0:
            continue
        pct = s.get("pct", 0.0)
        reste = s.get("reste", 0.0)
        depense = s.get("depense", 0.0)
        if pct > OVER_PCT:
            out.append({
                "category_id": s["category_id"],
                "action": "over",
                "depense": depense,
                "budget": budget,
                "ecart": depense - budget,
                "suggestion_mois_suivant": round(depense * 1.1, 2),
            })
        elif UNDER_MIN_PCT <= pct < UNDER_MAX_PCT and reste > 20.0:
            out.append({
                "category_id": s["category_id"],
                "action": "under",
                "depense": depense,
                "budget": budget,
                "reste": reste,
                "suggestion_mois_suivant": round(depense * 1.15, 2),
            })
    return out


def _next_month(mois: str) -> str:
    year, month = int(mois[:4]), int(mois[5:])
    if month == 12:
        return f"{year + 1}-01"
    return f"{year}-{month + 1:02d}"


def run_monthly_rebalancing(
    session: Session,
    mois: str | None = None,
) -> list[dict[str, Any]]:
    """Analyse les enveloppes du mois, crée une Notification de synthèse
    et retourne les suggestions d'ajustement.

    mois : format 'YYYY-MM' (défaut = mois courant)
    """
    if mois is None:
        mois = dt.date.today().strftime("%Y-%m")

    try:
        from app.services.budget.envelopes import get_envelope_status
        from app.models.budget import BudgetCategory
    except ImportError:
        return []

    statuts = get_envelope_status(session, mois)
    if not statuts:
        return []

    suggestions = compute_rebalancing(statuts)
    if not suggestions:
        return []

    # Enrichit les suggestions avec le nom de catégorie
    cats = {c.id: c.nom for c in session.exec(select(BudgetCategory)).all()}
    over_names = [cats.get(s["category_id"], f"#{s['category_id']}") for s in suggestions if s["action"] == "over"]
    under_names = [cats.get(s["category_id"], f"#{s['category_id']}") for s in suggestions if s["action"] == "under"]

    parts = []
    if over_names:
        parts.append(f"Depasse : {', '.join(over_names)}")
    if under_names:
        parts.append(f"Sous-utilise : {', '.join(under_names)}")

    session.add(Notification(
        source="budget_rebalancing",
        level="info",
        titre=f"Bilan budget {mois}",
        message=" | ".join(parts),
    ))
    session.commit()
    return suggestions
