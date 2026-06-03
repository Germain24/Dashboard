"""Alerte de déficit/surplus calorique trop agressif sur 7 jours (#70).

On compare la consommation réelle (`PlanNutrition.consumed["Calories"]`) à la
maintenance estimée (poids × 32) jour par jour, puis on moyenne l'écart sur la
fenêtre. Un déficit ou surplus moyen trop important (~1000 kcal/j ≈ 1 kg/sem)
signale un rythme risqué (fonte musculaire / prise de gras excessive).
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlmodel import Session, select

from app.models.sante import PlanNutrition

MAINTENANCE_FACTOR = 32.0
THRESH_WARNING = 750.0   # kcal/j moyen — rythme soutenu
THRESH_ALERT = 1000.0    # kcal/j moyen — trop agressif


def classify_balance(avg_balance: float) -> dict:
    """Niveau d'alerte pour un écart énergétique moyen (kcal/jour)."""
    mag = abs(avg_balance)
    direction = "surplus" if avg_balance > 0 else "déficit"
    if mag <= THRESH_WARNING:
        level = "ok"
    elif mag <= THRESH_ALERT:
        level = "warning"
    else:
        level = "alert"

    if level == "ok":
        msg = "Rythme énergétique soutenable."
    else:
        adj = "très agressif" if level == "alert" else "soutenu"
        msg = f"{direction.capitalize()} moyen {adj} (~{round(mag)} kcal/j sur la période)."
    return {"level": level, "direction": direction, "message": msg}


def weekly_energy_balance(
    session: Session,
    days: int = 7,
    end_date: Optional[dt.date] = None,
) -> dict:
    """Bilan énergétique moyen consommé − maintenance sur la fenêtre glissante."""
    end = end_date or dt.date.today()
    start = end - dt.timedelta(days=days - 1)
    plans = list(session.exec(
        select(PlanNutrition)
        .where(PlanNutrition.date >= start, PlanNutrition.date <= end)
        .order_by(PlanNutrition.date.asc())
    ).all())

    balances: list[float] = []
    consumed_vals: list[float] = []
    maint_vals: list[float] = []
    for p in plans:
        consumed = p.consumed or {}
        cals = consumed.get("Calories")
        poids = p.poids_used or 0.0
        if cals is None or poids <= 0:
            continue
        maint = poids * MAINTENANCE_FACTOR
        balances.append(float(cals) - maint)
        consumed_vals.append(float(cals))
        maint_vals.append(maint)

    if not balances:
        return {"days": 0, "avg_balance": None, "level": "ok", "direction": None, "message": None}

    avg = sum(balances) / len(balances)
    cls = classify_balance(avg)
    return {
        "days": len(balances),
        "avg_balance": round(avg),
        "avg_consumed": round(sum(consumed_vals) / len(consumed_vals)),
        "avg_maintenance": round(sum(maint_vals) / len(maint_vals)),
        **cls,
    }
