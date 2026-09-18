"""Placement automatique des corvées hebdomadaires et mensuelles."""

from __future__ import annotations

import calendar
import datetime as dt
from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.agenda import Evenement
from app.services.agenda.events import create_event, get_full_calendar
from app.services.agenda.slots import free_slots

DURATION_MIN = 120
BUFFER_MIN = 15
SOURCE = "housekeeping"
COLOR = "#536252"
PREFERRED_TIMES = {
    "matin": ((9, 0), (10, 30), (7, 30)),
    "aprem": ((14, 0), (16, 0), (12, 30)),
    "soir": ((18, 0), (20, 0)),
}


@dataclass(frozen=True)
class Chore:
    title: str
    source_id: str
    start_date: dt.date
    end_date: dt.date


def _periods(day: dt.date) -> list[Chore]:
    month_end = dt.date(day.year, day.month, calendar.monthrange(day.year, day.month)[1])
    iso = day.isocalendar()
    week_end = day + dt.timedelta(days=6 - day.weekday())
    # Le mensuel passe d'abord pour lui garantir une place dans le mois.
    return [
        Chore(
            "Laver la chambre et le linge de lit",
            f"housekeeping:bedroom:{day:%Y-%m}",
            day,
            month_end,
        ),
        Chore(
            "Linge à la machine et pliage",
            f"housekeeping:laundry:{iso.year}-W{iso.week:02d}",
            day,
            week_end,
        ),
    ]


def choose_free_slot(
    start_date: dt.date,
    end_date: dt.date,
    events: list[dict],
    moment: str = "aprem",
    not_before: dt.datetime | None = None,
) -> tuple[dt.datetime, dt.datetime] | None:
    duration = dt.timedelta(minutes=DURATION_MIN)
    padding = dt.timedelta(minutes=BUFFER_MIN)
    preferences = PREFERRED_TIMES.get(moment, PREFERRED_TIMES["aprem"])
    slots_by_day: list[tuple[dt.date, list[dict]]] = []
    day = start_date
    while day <= end_date:
        occupied = [
            (event["debut"] - padding, event["fin"] + padding)
            for event in events
            if event.get("debut") is not None
            and event.get("fin") is not None
            and event["debut"].date() == day
        ]
        if not_before is not None and day == not_before.date():
            occupied.append((dt.datetime.combine(day, dt.time(7, 0)), not_before))
        slots = free_slots(
            day,
            occupied,
            min_duration_min=DURATION_MIN,
            day_start_h=7,
            day_end_h=23,
        )
        slots_by_day.append((day, slots))
        for hour, minute in preferences:
            preferred = dt.datetime.combine(day, dt.time(hour, minute))
            if any(slot["debut"] <= preferred and preferred + duration <= slot["fin"] for slot in slots):
                return preferred, preferred + duration
        day += dt.timedelta(days=1)
    # Aucune préférence n'entre dans la période : prendre seulement alors le
    # premier créneau libre, au lieu de sacrifier l'après-midi dès le jour 1.
    for _day, slots in slots_by_day:
        if slots:
            return slots[0]["debut"], slots[0]["debut"] + duration
    return None


def _moment_preference() -> str:
    try:
        from app.services.agenda.preferences import get_preferences

        return get_preferences().get("moments", {}).get("menage", "aprem")
    except Exception:
        return "aprem"


def ensure_housekeeping_events(
    session: Session,
    reference_date: dt.date | None = None,
) -> dict[str, list[str]]:
    """Crée au plus une occurrence par période et réessaie si aucune place."""
    now = dt.datetime.now() if reference_date is None else None
    day = reference_date or now.date()
    created: list[str] = []
    existing: list[str] = []
    unplaced: list[str] = []
    moment = _moment_preference()

    for chore in _periods(day):
        found = session.exec(
            select(Evenement).where(Evenement.source_id == chore.source_id)
        ).first()
        if found is not None:
            existing.append(chore.title)
            continue
        from_dt = dt.datetime.combine(chore.start_date, dt.time.min)
        to_dt = dt.datetime.combine(chore.end_date, dt.time.max)
        events = get_full_calendar(session, from_dt, to_dt)
        slot = choose_free_slot(
            chore.start_date,
            chore.end_date,
            events,
            moment,
            not_before=now,
        )
        if slot is None:
            unplaced.append(chore.title)
            continue
        create_event(
            session,
            {
                "titre": chore.title,
                "debut": slot[0],
                "fin": slot[1],
                "description": "Corvée récurrente placée automatiquement dans un créneau libre.",
                "source": SOURCE,
                "source_id": chore.source_id,
                "categorie": "autre",
                "couleur": COLOR,
            },
        )
        created.append(chore.title)
    return {"created": created, "existing": existing, "unplaced": unplaced}
