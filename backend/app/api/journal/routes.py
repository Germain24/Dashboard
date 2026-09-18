"""Routes module Journal / Humeur (#476)."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.journal.schemas import MoodEntryIn
from app.core.db import get_session
from app.services.journal import mood as mood_svc
from app.services.journal.correlations import compute_correlations

router = APIRouter()


def _serialize(e) -> dict:
    return {"id": e.id, "date": str(e.date), "humeur": e.humeur,
            "energie": e.energie, "tags": e.tags, "note": e.note}


@router.get("/entries")
def list_entries(session: Session = Depends(get_session),
                 from_: dt.date | None = None, to: dt.date | None = None):
    fin = to or dt.date.today()
    debut = from_ or (fin - dt.timedelta(days=30))
    return [_serialize(e) for e in mood_svc.list_entries(session, debut, fin)]


@router.get("/entries/{date}")
def get_entry(date: dt.date, session: Session = Depends(get_session)):
    e = mood_svc.get_entry(session, date)
    if e is None:
        raise HTTPException(404, "Aucune entrée pour ce jour")
    return _serialize(e)


@router.put("/entries/{date}")
def put_entry(date: dt.date, body: MoodEntryIn, session: Session = Depends(get_session)):
    try:
        e = mood_svc.upsert_entry(session, date, body.humeur, body.energie, body.tags, body.note)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return _serialize(e)


@router.delete("/entries/{date}", status_code=204)
def delete_entry(date: dt.date, session: Session = Depends(get_session)):
    mood_svc.delete_entry(session, date)


@router.get("/trends")
def trends(days: int = 30, session: Session = Depends(get_session)):
    fin = dt.date.today()
    debut = fin - dt.timedelta(days=days)
    entries = [_serialize(e) for e in mood_svc.list_entries(session, debut, fin)]
    return mood_svc.mood_trends(entries)


@router.get("/correlations")
def correlations(days: int = 90, session: Session = Depends(get_session)):
    return compute_correlations(session, days)
