"""Insights hebdomadaires auto-générés (#223).

Compare la semaine en cours à la précédente (depuis les DailySnapshot #212) et
classe les variations notables en réussites / points de vigilance / tendances.
Heuristique explicable ; pas de jugement sur les métriques neutres (poids…).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlmodel import Session

from app.services.automatisations.correlations import extract_metrics, load_snapshot_series

# label -> (agrégation "mean"|"sum", direction favorable "up"|"down"|None)
WEEK_METRICS: dict[str, tuple[str, str | None]] = {
    "Habitudes %": ("mean", "up"),
    "Séances": ("sum", "up"),
    "Tonnage": ("sum", "up"),
    "Humeur": ("mean", "up"),
    "Énergie": ("mean", "up"),
    "Dépenses": ("sum", "down"),
    "Poids": ("mean", None),
    "Calories": ("mean", None),
    "Événements": ("sum", None),
}


def aggregate_period(
    series: dict[str, dict[dt.date, float]], dates: set[dt.date],
) -> dict[str, float]:
    """Agrège chaque métrique sur la période (moyenne ou somme selon WEEK_METRICS)."""
    out: dict[str, float] = {}
    for label, (agg, _good) in WEEK_METRICS.items():
        vals = [v for d, v in series.get(label, {}).items() if d in dates]
        if not vals:
            continue
        out[label] = sum(vals) if agg == "sum" else sum(vals) / len(vals)
    return out


def _fmt(label: str, cur: float, prev: float, delta: float) -> str:
    arrow = "↑" if delta > 0 else "↓"
    return f"{label} {arrow} {abs(delta):.0f}% (cette sem. {cur:.0f} vs {prev:.0f})"


def summarize_week(
    current: dict[str, float], previous: dict[str, float], *, min_change_pct: float = 10,
) -> dict[str, list[str]]:
    """Classe les variations cette semaine vs la précédente.

    Réussites / vigilance selon la direction favorable de la métrique ; les
    métriques neutres (poids, calories, événements) -> simples tendances.
    """
    reussites: list[str] = []
    vigilance: list[str] = []
    tendances: list[str] = []
    for label, (_agg, good) in WEEK_METRICS.items():
        if label not in current or label not in previous:
            continue
        prev = previous[label]
        if prev == 0:
            continue
        cur = current[label]
        delta = (cur - prev) / abs(prev) * 100
        if abs(delta) < min_change_pct:
            continue
        msg = _fmt(label, cur, prev, delta)
        up = delta > 0
        if good is None:
            tendances.append(msg)
        elif (good == "up" and up) or (good == "down" and not up):
            reussites.append(msg)
        else:
            vigilance.append(msg)
    return {"reussites": reussites, "vigilance": vigilance, "tendances": tendances}


def build_weekly_insights(
    session: Session, *, today: dt.date | None = None, min_change_pct: float = 10,
) -> dict[str, Any]:
    """Insights de la semaine en cours vs la précédente (depuis les snapshots)."""
    today = today or dt.date.today()
    week_start = today - dt.timedelta(days=today.weekday())
    prev_start = week_start - dt.timedelta(days=7)
    this_week = {week_start + dt.timedelta(days=i) for i in range(7)}
    last_week = {prev_start + dt.timedelta(days=i) for i in range(7)}

    series = extract_metrics(load_snapshot_series(session, since=prev_start))

    current = aggregate_period(series, this_week)
    previous = aggregate_period(series, last_week)
    summary = summarize_week(current, previous, min_change_pct=min_change_pct)
    return {"week_start": week_start.isoformat(), **summary}
