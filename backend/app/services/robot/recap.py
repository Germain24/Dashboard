"""Récapitulatif quotidien (#159) — assemble les données réelles via les outils.

Déterministe (aucun appel LLM) : fonctionne même sans clé API. L'agent peut
ensuite résumer ce récap en langage naturel s'il le souhaite.
"""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session

from app.services.robot.tools import dispatch


def daily_recap(session: Session, *, today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    return {
        "date": today.isoformat(),
        "sections": {
            "agenda": dispatch(session, "get_agenda_today", {}),
            "habitudes": dispatch(session, "get_habitudes_today", {}),
            "budget": dispatch(session, "get_budget_month", {}),
            "finance": dispatch(session, "get_finance_portfolio", {}),
            "livres": dispatch(session, "get_livres_stats", {}),
        },
    }
