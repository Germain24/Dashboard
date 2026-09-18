"""Projection du poids cible via régression linéaire 30 jours.

Donne : tendance 7j et 30j, date estimée d'atteinte du poids cible,
confiance approximative. Pure Python (sans scipy) pour tests rapides.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class WeightTrend:
    days: int
    slope_kg_per_day: float
    slope_kg_per_week: float
    last_weight: float
    samples: int


@dataclass
class ProjectionResult:
    target_weight: float
    current_weight: float
    delta_kg: float
    days_to_target: Optional[int]
    target_date: Optional[dt.date]
    slope_kg_per_week: float
    confidence: str
    note: str
    trend_7d: Optional[WeightTrend] = None
    trend_30d: Optional[WeightTrend] = None


def _linregress(xs, ys):
    n = len(xs)
    if n < 2:
        return 0.0, ys[0] if ys else 0.0, 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    syy = sum((y - mean_y) ** 2 for y in ys)
    if sxx == 0:
        return 0.0, mean_y, 0.0
    slope = sxy / sxx
    intercept = mean_y - slope * mean_x
    r2 = (sxy ** 2) / (sxx * syy) if syy > 0 else 0.0
    return slope, intercept, r2


def _compute_trend(measures, days, today):
    cutoff = today - dt.timedelta(days=days)
    window = [(d, w) for d, w in measures if d >= cutoff and w is not None]
    if len(window) < 2:
        return None
    xs = [(d - window[0][0]).days for d, _ in window]
    ys = [w for _, w in window]
    slope, _, _ = _linregress(xs, ys)
    return WeightTrend(
        days=days,
        slope_kg_per_day=slope,
        slope_kg_per_week=slope * 7.0,
        last_weight=window[-1][1],
        samples=len(window),
    )


def project_weight_to_target(measures, target_weight, today=None):
    today = today or dt.date.today()
    clean = sorted(
        ((d, w) for d, w in measures if w is not None and w > 0),
        key=lambda t: t[0],
    )
    if not clean:
        return None

    trend_7d = _compute_trend(clean, 7, today)
    trend_30d = _compute_trend(clean, 30, today)

    if trend_30d is None or trend_30d.samples < 2:
        if len(clean) < 2:
            return ProjectionResult(
                target_weight=target_weight,
                current_weight=clean[-1][1],
                delta_kg=target_weight - clean[-1][1],
                days_to_target=None,
                target_date=None,
                slope_kg_per_week=0.0,
                confidence="low",
                note="Pas assez de mesures pour projeter (minimum 2 points).",
                trend_7d=trend_7d,
                trend_30d=trend_30d,
            )
        xs = [(d - clean[0][0]).days for d, _ in clean]
        ys = [w for _, w in clean]
        slope, _, _ = _linregress(xs, ys)
        samples = len(clean)
    else:
        slope = trend_30d.slope_kg_per_day
        samples = trend_30d.samples

    current = clean[-1][1]
    delta = target_weight - current

    if samples >= 20:
        confidence = "high"
    elif samples >= 7:
        confidence = "medium"
    else:
        confidence = "low"
    if trend_7d and trend_30d and trend_7d.slope_kg_per_day * trend_30d.slope_kg_per_day < 0:
        confidence = "low"

    # Poids stable AVANT le check direction (sinon slope=0 traité comme mauvais sens)
    if abs(slope) < 1e-4:
        return ProjectionResult(
            target_weight=target_weight,
            current_weight=current,
            delta_kg=delta,
            days_to_target=None,
            target_date=None,
            slope_kg_per_week=0.0,
            confidence=confidence,
            note="Poids stable - pas de progression mesurable sur 30j.",
            trend_7d=trend_7d,
            trend_30d=trend_30d,
        )

    if delta != 0 and ((delta > 0 and slope < 0) or (delta < 0 and slope > 0)):
        return ProjectionResult(
            target_weight=target_weight,
            current_weight=current,
            delta_kg=delta,
            days_to_target=None,
            target_date=None,
            slope_kg_per_week=slope * 7.0,
            confidence="low",
            note=f"Tendance actuelle ({slope * 7:.2f} kg/sem) ne mene pas vers l'objectif.",
            trend_7d=trend_7d,
            trend_30d=trend_30d,
        )

    days = int(math.ceil(delta / slope)) if slope != 0 else None
    target_date = today + dt.timedelta(days=days) if days is not None else None

    if target_date:
        note = f"Au rythme actuel de {slope * 7:+.2f} kg/sem, tu atteins {target_weight:.1f} kg le {target_date.isoformat()}."
    else:
        note = "Projection indisponible."

    return ProjectionResult(
        target_weight=target_weight,
        current_weight=current,
        delta_kg=delta,
        days_to_target=days,
        target_date=target_date,
        slope_kg_per_week=slope * 7.0,
        confidence=confidence,
        note=note,
        trend_7d=trend_7d,
        trend_30d=trend_30d,
    )
