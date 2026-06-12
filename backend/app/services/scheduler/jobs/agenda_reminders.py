"""Job de rappels d'agenda (#85) : notifie les événements imminents.

Exécuté périodiquement (toutes les 15 min). Pour chaque événement débutant
dans les ~30 prochaines minutes et pas encore rappelé, crée une Notification.
"""

from __future__ import annotations

import datetime as dt

from app.models.scheduler import Notification
from app.services.agenda.reminders import (
    due_events,
    load_reminded,
    reminder_key,
    save_reminded,
)


def run(session) -> str:
    from app.services.settings import get_preferences
    if get_preferences().get("mode_vacances"):
        return "Mode vacances actif — rappels suspendus"

    from app.services.agenda.entrainement_bridge import get_training_block_for_date
    from app.services.agenda.events import get_full_calendar

    now = dt.datetime.now().replace(second=0, microsecond=0)
    today = now.date()
    from_dt = dt.datetime.combine(today, dt.time.min)
    to_dt = dt.datetime.combine(today, dt.time.max)

    events = get_full_calendar(session, from_dt, to_dt)
    blk = get_training_block_for_date(session, today)
    if blk:
        events.append(blk)

    due = due_events(events, now)
    reminded = load_reminded()

    created = 0
    for e in due:
        key = reminder_key(e.get("titre", "Événement"), e["debut"])
        if key in reminded:
            continue
        heure = e["debut"].strftime("%H:%M")
        lieu = e.get("lieu")
        message = f"À {heure}" + (f" · {lieu}" if lieu else "")
        session.add(Notification(
            source="agenda_reminder",
            level="info",
            titre=f"⏰ {e.get('titre', 'Événement')}",
            message=message,
        ))
        reminded.add(key)
        created += 1

    if created:
        session.commit()
        save_reminded(reminded)

    return f"{created} rappel(s) créé(s)"
