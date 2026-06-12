"""Jobs de briefings quotidiens (#203 matin, #204 soir)."""

from __future__ import annotations

from app.models.scheduler import Notification
from app.services.automatisations.briefing import build_morning_briefing, build_evening_recap


def run_briefing_matin(session) -> str:
    message = build_morning_briefing(session)
    session.add(Notification(
        source="briefing_matin",
        level="info",
        titre="☀️ Briefing matin",
        message=message,
    ))
    session.commit()
    return "briefing matin créé"


def run_recap_soir(session) -> str:
    message = build_evening_recap(session)
    session.add(Notification(
        source="recap_soir",
        level="info",
        titre="🌙 Récap du soir",
        message=message,
    ))
    session.commit()
    return "récap soir créé"
