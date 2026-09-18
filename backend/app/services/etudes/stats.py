"""Statistiques d'étude (#94 temps/matière, #97 heatmap, #101 streak, #102 rapport).

Fonctions pures travaillant sur des sessions normalisées
(`{date: dt.date, duree_min: int, cours_id: int|None}`), donc testables sans base.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Iterable, Optional


def minutes_by_course(
    sessions: Iterable[dict[str, Any]],
    labels: Optional[dict[int, str]] = None,
) -> list[dict[str, Any]]:
    """Total de minutes par cours (trié décroissant). `labels` : cours_id -> code."""
    labels = labels or {}
    totals: dict[Optional[int], int] = {}
    for s in sessions:
        cid = s.get("cours_id")
        totals[cid] = totals.get(cid, 0) + int(s.get("duree_min") or 0)
    out = [
        {
            "cours_id": cid,
            "label": labels.get(cid, "Libre") if cid is not None else "Libre",
            "minutes": mins,
        }
        for cid, mins in totals.items()
    ]
    out.sort(key=lambda x: x["minutes"], reverse=True)
    return out


def daily_minutes(sessions: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Minutes étudiées par jour : {YYYY-MM-DD: minutes} (heatmap #97)."""
    out: dict[str, int] = {}
    for s in sessions:
        d = s.get("date")
        if d is None:
            continue
        key = d.isoformat() if isinstance(d, dt.date) else str(d)
        out[key] = out.get(key, 0) + int(s.get("duree_min") or 0)
    return out


def study_streak(dates: Iterable[dt.date], today: Optional[dt.date] = None) -> dict[str, int]:
    """Série de jours étudiés : {current, best} (#101).

    `current` compte les jours consécutifs se terminant aujourd'hui ou hier
    (tolère qu'on n'ait pas encore étudié aujourd'hui).
    """
    today = today or dt.date.today()
    day_set = {d for d in dates if isinstance(d, dt.date)}
    if not day_set:
        return {"current": 0, "best": 0}

    # Meilleure série
    best = cur = 1
    ordered = sorted(day_set)
    for prev, d in zip(ordered, ordered[1:]):
        if (d - prev).days == 1:
            cur += 1
        else:
            cur = 1
        best = max(best, cur)

    # Série courante (ancrée aujourd'hui ou hier)
    anchor = today if today in day_set else (today - dt.timedelta(days=1))
    current = 0
    d = anchor
    while d in day_set:
        current += 1
        d -= dt.timedelta(days=1)

    return {"current": current, "best": best}


def weekly_summary(
    sessions: Iterable[dict[str, Any]],
    labels: Optional[dict[int, str]] = None,
    week_start: Optional[dt.date] = None,
) -> dict[str, Any]:
    """Rapport de la semaine [week_start, +6j] : total, nb, par cours (#102)."""
    labels = labels or {}
    if week_start is None:
        today = dt.date.today()
        week_start = today - dt.timedelta(days=today.weekday())
    week_end = week_start + dt.timedelta(days=6)

    in_week = [
        s for s in sessions
        if isinstance(s.get("date"), dt.date) and week_start <= s["date"] <= week_end
    ]
    total = sum(int(s.get("duree_min") or 0) for s in in_week)
    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "total_minutes": total,
        "sessions": len(in_week),
        "by_course": minutes_by_course(in_week, labels),
    }
