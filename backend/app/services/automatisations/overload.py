"""Détection de surcharge (#231).

Repère les journées trop denses (agenda + études + sport cumulés dépassent un
seuil d'heures d'engagements) et suggère d'alléger. assess_overload est pur ;
detect_overload construit la charge par jour depuis l'agenda.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlmodel import Session

from app.services.agenda.events import list_events_for_window

DEFAULT_THRESHOLD_MIN = 600  # 10 h d'engagements sur la journée


def assess_overload(
    days: list[dict[str, Any]], *, threshold_min: int = DEFAULT_THRESHOLD_MIN,
) -> list[dict[str, Any]]:
    """Garde les journées dont la charge (minutes) atteint le seuil, triées desc."""
    out: list[dict[str, Any]] = []
    for d in days:
        if d["load_min"] >= threshold_min:
            h = d["load_min"] / 60
            out.append({
                "date": d["date"],
                "load_min": d["load_min"],
                "load_h": round(h, 1),
                "n_events": d.get("n_events", 0),
                "suggestion": f"Journée chargée ({h:.1f} h d'engagements) — "
                              "envisage d'alléger ou de reporter une activité.",
            })
    out.sort(key=lambda x: -x["load_min"])
    return out


def detect_overload(
    session: Session, week_start: dt.date, *,
    threshold_min: int = DEFAULT_THRESHOLD_MIN,
    day_start_h: int = 7, day_end_h: int = 23,
) -> list[dict[str, Any]]:
    """Évalue la surcharge de chaque jour de la semaine depuis l'agenda."""
    days: list[dict[str, Any]] = []
    for offset in range(7):
        day = week_start + dt.timedelta(days=offset)
        win_start = dt.datetime.combine(day, dt.time(day_start_h, 0))
        win_end = dt.datetime.combine(day, dt.time(day_end_h, 0))
        events = list_events_for_window(
            session, dt.datetime.combine(day, dt.time.min), dt.datetime.combine(day, dt.time.max)
        )
        load_min = 0
        for e in events:
            d0 = e.debut
            f0 = e.fin or (e.debut + dt.timedelta(hours=1))
            lo, hi = max(d0, win_start), min(f0, win_end)
            if hi > lo:
                load_min += int((hi - lo).total_seconds() // 60)
        days.append({"date": day, "load_min": load_min, "n_events": len(events)})
    return assess_overload(days, threshold_min=threshold_min)
