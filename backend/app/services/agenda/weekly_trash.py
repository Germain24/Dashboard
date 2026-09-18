"""Planification hebdomadaire du rappel de changement des poubelles."""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session, select

from app.models.agenda import Evenement
from app.services.agenda.events import create_event, get_full_calendar
from app.services.agenda.slots import free_slots

TITLE = "Changer les poubelles"
SOURCE = "weekly_trash"
DURATION_MIN = 15
BUFFER_MIN = 15
PREFERRED_TIMES = ((20, 30), (18, 0), (10, 0))


def next_sunday(reference_date: dt.date) -> dt.date:
    """Retourne le dimanche courant ou le prochain dimanche."""
    return reference_date + dt.timedelta(days=(6 - reference_date.weekday()) % 7)


def source_id_for(day: dt.date) -> str:
    return f"weekly-trash:{day.isoformat()}"


def choose_free_slot(
    day: dt.date,
    events: list[dict],
) -> tuple[dt.datetime, dt.datetime] | None:
    """Choisit un créneau de 15 minutes, avec un tampon autour des événements."""
    pad = dt.timedelta(minutes=BUFFER_MIN)
    occupied = [
        (event["debut"] - pad, event["fin"] + pad)
        for event in events
        if event.get("debut") is not None and event.get("fin") is not None
    ]
    slots = free_slots(
        day,
        occupied,
        min_duration_min=DURATION_MIN,
        day_start_h=9,
        day_end_h=22,
    )
    duration = dt.timedelta(minutes=DURATION_MIN)
    for hour, minute in PREFERRED_TIMES:
        preferred = dt.datetime.combine(day, dt.time(hour, minute))
        for slot in slots:
            if slot["debut"] <= preferred and preferred + duration <= slot["fin"]:
                return preferred, preferred + duration
    if not slots:
        return None
    start = slots[0]["debut"]
    return start, start + duration


def ensure_weekly_trash_reminder(
    session: Session,
    reference_date: dt.date | None = None,
) -> tuple[Evenement | None, bool]:
    """Crée au plus un rappel pour le dimanche courant ou suivant.

    Retourne ``(événement, créé)``. Si aucun créneau n'est disponible, retourne
    ``(None, False)`` afin que le prochain lancement puisse réessayer.
    """
    sunday = next_sunday(reference_date or dt.date.today())
    source_id = source_id_for(sunday)
    existing = session.exec(select(Evenement).where(Evenement.source_id == source_id)).first()
    if existing is not None:
        return existing, False

    start_of_day = dt.datetime.combine(sunday, dt.time.min)
    end_of_day = dt.datetime.combine(sunday, dt.time.max)
    events = get_full_calendar(session, start_of_day, end_of_day)
    slot = choose_free_slot(sunday, events)
    if slot is None:
        return None, False

    event = create_event(
        session,
        {
            "titre": TITLE,
            "debut": slot[0],
            "fin": slot[1],
            "description": "Rappel hebdomadaire placé automatiquement dans un créneau libre.",
            "source": SOURCE,
            "source_id": source_id,
            "categorie": "autre",
            "couleur": "#536252",
        },
    )
    return event, True
