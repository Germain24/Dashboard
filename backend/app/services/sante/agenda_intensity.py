"""Charge journalière dérivée de l'Agenda pour les cibles nutritionnelles.

Les minutes planifiées ne sont pas toutes équivalentes : une heure de sport
pèse davantage qu'une heure de travail ou d'études. Le score reste volontairement
simple et explicable, puis est combiné avec l'intensité du module Entraînement.
"""

from __future__ import annotations

import datetime as dt
import unicodedata
from typing import Any

from app.services.agenda.events import get_full_calendar

_CATEGORY_WEIGHTS: dict[str, float] = {
    "sport": 1.0,
    "entrainement": 1.0,
    "travail": 0.45,
    "work": 0.45,
    "cours": 0.35,
    "etudes": 0.35,
    "study": 0.35,
    "cuisine": 0.20,
    "rdv": 0.15,
}
_LEVEL_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3}


def _normalise(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", (value or "").strip().lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _event_minutes(event: dict[str, Any], date: dt.date) -> float:
    start = event.get("debut")
    end = event.get("fin")
    if not isinstance(start, dt.datetime) or not isinstance(end, dt.datetime):
        return 0.0
    day_start = dt.datetime.combine(date, dt.time.min, tzinfo=start.tzinfo)
    day_end = day_start + dt.timedelta(days=1)
    clipped_start = max(start, day_start)
    clipped_end = min(end, day_end)
    return max(0.0, (clipped_end - clipped_start).total_seconds() / 60.0)


def classify_agenda_events(events: list[dict[str, Any]], date: dt.date) -> dict[str, Any]:
    """Retourne le niveau et un résumé explicable de la charge Agenda."""
    weighted_minutes = 0.0
    scheduled_minutes = 0.0
    categories: dict[str, float] = {}

    for event in events:
        minutes = min(_event_minutes(event, date), 12 * 60.0)
        if minutes <= 0:
            continue
        category = _normalise(event.get("categorie")) or "autre"
        weight = _CATEGORY_WEIGHTS.get(category, 0.10)
        scheduled_minutes += minutes
        weighted_minutes += minutes * weight
        categories[category] = categories.get(category, 0.0) + minutes

    if weighted_minutes >= 420:
        level = "high"
    elif weighted_minutes >= 240:
        level = "medium"
    elif weighted_minutes >= 60:
        level = "low"
    else:
        level = "none"

    sport_minutes = categories.get("sport", 0.0) + categories.get("entrainement", 0.0)
    if sport_minutes >= 90:
        level = "high"
    elif sport_minutes >= 45 and _LEVEL_ORDER[level] < _LEVEL_ORDER["medium"]:
        level = "medium"

    return {
        "intensity": level,
        "scheduled_minutes": round(scheduled_minutes),
        "weighted_minutes": round(weighted_minutes),
        "categories_minutes": {k: round(v) for k, v in sorted(categories.items())},
    }


def resolve_day_intensity(
    session: Any,
    date: dt.date,
    workout_intensity: str,
) -> tuple[str, dict[str, Any]]:
    """Combine Entraînement et Agenda; le niveau le plus exigeant gagne."""
    start = dt.datetime.combine(date, dt.time.min)
    end = start + dt.timedelta(days=1)
    events = get_full_calendar(session, start, end)
    agenda = classify_agenda_events(events, date)
    workout = workout_intensity if workout_intensity in _LEVEL_ORDER else "none"
    combined = max((workout, agenda["intensity"]), key=_LEVEL_ORDER.get)
    return combined, {
        "source": "agenda+entrainement",
        "workout_intensity": workout,
        "agenda_intensity": agenda["intensity"],
        "scheduled_minutes": agenda["scheduled_minutes"],
        "weighted_minutes": agenda["weighted_minutes"],
        "categories_minutes": agenda["categories_minutes"],
    }
