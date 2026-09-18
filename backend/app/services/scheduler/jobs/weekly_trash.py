"""Job dominical: place le rappel des poubelles dans un créneau libre."""

from __future__ import annotations

from app.services.agenda.weekly_trash import ensure_weekly_trash_reminder


def run(session) -> str:
    event, created = ensure_weekly_trash_reminder(session)
    if event is None:
        return "Rappel poubelles non placé: aucun créneau libre le dimanche"
    if not created:
        return f"Rappel poubelles déjà planifié à {event.debut:%H:%M}"
    return f"Rappel poubelles planifié à {event.debut:%H:%M}"
