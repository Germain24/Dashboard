"""Sous-routeur Garde-robe : planificateur de tenues de la semaine (#503, #79)."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.api.garderobe.common import vetement_to_read
from app.api.garderobe.schemas import PlannerDayUpdate
from app.core.db import get_session
from app.models.garderobe import Vetement

router = APIRouter()


@router.get("/planner")
def get_planner(start: Optional[dt.date] = None, session: Session = Depends(get_session)) -> dict:
    """Plan de tenues de la semaine + événements d'agenda par jour (#79).

    `start` = premier jour (par défaut le lundi de la semaine courante).
    """
    from app.services.agenda.events import list_events_for_window
    from app.services.garderobe.planner import get_day, monday_of, week_dates

    start = monday_of(start or dt.date.today())
    rows = list(session.exec(select(Vetement)).all())
    by_id = {v.id: v for v in rows}

    days = []
    for d in week_dates(start):
        tenue_ids = get_day(d)
        tenue = {
            slot: (vetement_to_read(by_id[vid]) if vid in by_id else None)
            for slot, vid in tenue_ids.items()
        }
        # Lien agenda : événements du jour (titre + catégorie)
        day_start = dt.datetime.combine(d, dt.time.min)
        day_end = day_start + dt.timedelta(days=1)
        try:
            evs = list_events_for_window(session, day_start, day_end)
            events = [{"titre": e.titre, "categorie": e.categorie, "heure": e.debut.strftime("%H:%M")} for e in evs]
        except Exception:  # pragma: no cover — défensif si agenda indispo
            events = []
        days.append({"date": str(d), "weekday": d.weekday(), "tenue": tenue, "events": events})

    return {"start": str(start), "days": days}


@router.put("/planner/{date}")
def set_planner_day(date: dt.date, payload: PlannerDayUpdate, session: Session = Depends(get_session)) -> dict:
    """Enregistre la tenue planifiée d'un jour (#79)."""
    from app.services.garderobe.planner import set_day

    rows = session.exec(select(Vetement)).all()
    by_id = {v.id: v for v in rows}
    cleaned = set_day(date, payload.tenue)
    tenue = {
        slot: (vetement_to_read(by_id[vid]) if vid in by_id else None)
        for slot, vid in cleaned.items()
    }
    return {"date": str(date), "tenue": tenue}
