"""Prédiction de tendances par régression linéaire (#228).

Ajuste une droite des moindres carrés sur une série temporelle (poids, dépenses,
humeur…) issue des DailySnapshot (#212) et projette la valeur à un horizon donné.
Modèle volontairement simple et explicable (tendance linéaire), pas une boîte noire.

linear_regression / forecast_series sont purs ; compute_forecasts charge la base.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

from sqlmodel import Session, select

from app.models.snapshot import DailySnapshot
from app.services.automatisations.correlations import extract_metrics


def linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float] | None:
    """Pente et ordonnée à l'origine (moindres carrés). None si < 2 pts ou x constant."""
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    return slope, my - slope * mx


def forecast_series(
    points: list[tuple[dt.date, float]], *, horizon_days: int = 30,
) -> dict[str, Any] | None:
    """Projette la valeur à `horizon_days` après le dernier point (tendance linéaire)."""
    if len(points) < 2:
        return None
    points = sorted(points)
    d0 = points[0][0]
    xs = [float((d - d0).days) for d, _ in points]
    ys = [v for _, v in points]
    reg = linear_regression(xs, ys)
    if reg is None:
        return None
    slope, intercept = reg
    cur = ys[-1]
    proj = slope * (xs[-1] + horizon_days) + intercept
    return {
        "slope_per_day": round(slope, 4),
        "courant": round(cur, 2),
        "horizon_days": horizon_days,
        "prevision": round(proj, 2),
        "variation": round(proj - cur, 2),
        "direction": "hausse" if slope > 0 else "baisse" if slope < 0 else "stable",
        "n": len(points),
    }


def compute_forecasts(
    session: Session, *, days: int = 90, horizon_days: int = 30, min_points: int = 5,
) -> list[dict[str, Any]]:
    """Prévisions par métrique (depuis les snapshots récents)."""
    cutoff = dt.date.today() - dt.timedelta(days=days)
    rows = session.exec(select(DailySnapshot).where(DailySnapshot.date >= cutoff)).all()
    snaps: list[tuple[dt.date, dict]] = []
    for row in rows:
        try:
            snaps.append((row.date, json.loads(row.data)))
        except (ValueError, TypeError):
            continue
    metrics = extract_metrics(snaps)
    out: list[dict[str, Any]] = []
    for label, series in metrics.items():
        if len(series) < min_points:
            continue
        fc = forecast_series(list(series.items()), horizon_days=horizon_days)
        if fc:
            out.append({"metric": label, **fc})
    out.sort(key=lambda f: -abs(f["variation"]))
    return out
