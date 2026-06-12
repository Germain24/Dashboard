"""Job rappels habitudes manquantes (#136).

Exécuté à 20h chaque jour. Si des habitudes n'ont pas été cochées et qu'aucun
rappel n'a encore été envoyé aujourd'hui, crée une Notification consolidée.
"""

from __future__ import annotations

import datetime as dt

from app.models.scheduler import Notification
from app.services.habitudes.entries import get_today_checklist
from app.services.habitudes.reminders import unchecked_habits, should_remind, mark_reminded


def run(session) -> str:
    from app.services.settings import get_preferences
    if get_preferences().get("mode_vacances"):
        return "Mode vacances actif — rappels suspendus"

    today = dt.date.today()
    if not should_remind(today):
        return "Rappel déjà envoyé aujourd'hui"

    checklist = get_today_checklist(session)
    missing = unchecked_habits(checklist)
    if not missing:
        return "Toutes les habitudes complétées"

    if len(missing) == 1:
        titre = f"🔔 Habitude à faire : {missing[0]}"
        message = "Tu n'as pas encore coché cette habitude aujourd'hui."
    else:
        titre = f"🔔 {len(missing)} habitudes non cochées"
        message = "Reste à faire : " + ", ".join(missing[:3]) + ("…" if len(missing) > 3 else "")

    session.add(Notification(
        source="habit_reminder",
        level="info",
        titre=titre,
        message=message,
    ))
    session.commit()
    mark_reminded(today)
    return f"Rappel créé ({len(missing)} habitude(s) manquante(s))"
