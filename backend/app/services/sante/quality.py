"""Score de qualité nutritionnelle (#65).

Compare la consommation réelle (`PlanNutrition.consumed`) aux cibles
(`PlanNutrition.targets`) sur plusieurs jours et en tire un score 0-100.

Logique pure (`score_day`) testable sans base, + agrégation hebdomadaire.
Critères :
  - Protéines / Fibres : on récompense l'atteinte de la cible (ratio plafonné à 1).
  - Calories : on pénalise l'écart dans les deux sens.
  - clés `*_Max` (Sucres_Max, Sodium_Max…) : limites — on pénalise le dépassement.
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlmodel import Session, select

from app.models.sante import PlanNutrition

# Critères "atteinte" : plus on s'approche de la cible (sans pénaliser l'excès), mieux c'est.
_HIT_KEYS = ("Protéines", "Fibres")
# Critère "proximité" : tout écart (sur ou sous) pénalise.
_NEAR_KEYS = ("Calories",)


def _sub_score(key: str, consumed: float, target: float) -> Optional[float]:
    if target <= 0:
        return None
    if key.endswith("_Max"):
        # limite à ne pas dépasser
        return 1.0 if consumed <= target else max(0.0, 1.0 - (consumed - target) / target)
    if key in _NEAR_KEYS:
        return max(0.0, 1.0 - abs(consumed - target) / target)
    # atteinte (protéines, fibres, et tout autre nutriment "à viser")
    return min(1.0, consumed / target)


def score_day(consumed: dict, targets: dict) -> dict:
    """Score d'un jour (0-100) + détail par critère. ``score`` None si pas de conso."""
    criteria: dict[str, int] = {}
    subs: list[float] = []
    if consumed:
        for key, target in targets.items():
            if not isinstance(target, (int, float)):
                continue
            # on ne note que les critères "intéressants" (macros clés + limites)
            if key not in _HIT_KEYS and key not in _NEAR_KEYS and not key.endswith("_Max"):
                continue
            c = float(consumed.get(key, 0.0))
            sub = _sub_score(key, c, float(target))
            if sub is None:
                continue
            criteria[key] = round(sub * 100)
            subs.append(sub)
    if not subs:
        return {"score": None, "criteria": {}}
    return {"score": round(sum(subs) / len(subs) * 100), "criteria": criteria}


def _has_consumed(consumed: Optional[dict]) -> bool:
    return bool(consumed) and any(
        isinstance(v, (int, float)) and not str(k).endswith("_g")
        for k, v in consumed.items()
    )


def weekly_nutrition_quality(
    session: Session,
    end_date: Optional[dt.date] = None,
    days: int = 7,
) -> dict:
    """Score nutritionnel moyen sur la fenêtre [end_date-days+1, end_date]."""
    end = end_date or dt.date.today()
    start = end - dt.timedelta(days=days - 1)
    plans = list(session.exec(
        select(PlanNutrition)
        .where(PlanNutrition.date >= start, PlanNutrition.date <= end)
        .order_by(PlanNutrition.date.asc())
    ).all())

    daily: list[dict] = []
    crit_acc: dict[str, list[int]] = {}
    for p in plans:
        if not _has_consumed(p.consumed):
            continue
        d = score_day(p.consumed or {}, p.targets or {})
        if d["score"] is None:
            continue
        daily.append({"date": str(p.date), "score": d["score"], "criteria": d["criteria"]})
        for k, v in d["criteria"].items():
            crit_acc.setdefault(k, []).append(v)

    if not daily:
        return {"days": 0, "score": None, "daily": [], "worst": None, "best": None}

    crit_avg = {k: round(sum(v) / len(v)) for k, v in crit_acc.items()}
    worst = min(crit_avg, key=crit_avg.get) if crit_avg else None
    best = max(crit_avg, key=crit_avg.get) if crit_avg else None
    return {
        "days": len(daily),
        "score": round(sum(d["score"] for d in daily) / len(daily)),
        "daily": daily,
        "criteria_avg": crit_avg,
        "worst": worst,
        "best": best,
    }
