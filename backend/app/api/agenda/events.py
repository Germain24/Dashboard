"""Sous-routeur Agenda : événements (liste, conflits, CRUD) (#502)."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.api.agenda.common import SessionDep, dates_in_range, ev_to_read
from app.api.agenda.schemas import EvenementCreate, EvenementRead, EvenementUpdate
from app.services.agenda import (
    create_event,
    delete_event,
    get_full_calendar,
    get_training_block_for_date,
    update_event,
)

router = APIRouter()


@router.get("/events", response_model=list[EvenementRead])
def list_events(
    session: SessionDep,
    from_: Optional[dt.datetime] = Query(None, alias="from"),
    to: Optional[dt.datetime] = Query(None),
    include_recurrences: bool = True,
    include_training: bool = True,
):
    today = dt.date.today()
    from_dt = from_ or dt.datetime.combine(today, dt.time.min)
    to_dt = to or dt.datetime.combine(today + dt.timedelta(days=7), dt.time.max)

    items = get_full_calendar(session, from_dt, to_dt)
    if include_training:
        for single_date in dates_in_range(from_dt.date(), to_dt.date()):
            blk = get_training_block_for_date(session, single_date)
            # Seules les séances loggées (horaire réel) sont des événements ;
            # une séance planifiée (fin=None) reste flexible, hors timeline.
            if blk and blk.get("fin"):
                items.append(blk)
    items.sort(key=lambda x: x["debut"])
    return [ev_to_read(e) for e in items]


@router.get("/events/conflicts", response_model=list[EvenementRead])
def check_conflicts(
    session: SessionDep,
    debut: dt.datetime = Query(...),
    fin: Optional[dt.datetime] = Query(None),
    ignore_id: Optional[int] = Query(None),
):
    """Événements qui chevauchent l'intervalle [debut, fin) (#87)."""
    from app.services.agenda.conflicts import find_conflicts

    end = fin or debut + dt.timedelta(hours=1)
    # On élargit la fenêtre d'1h de chaque côté pour capter les chevauchements aux bords.
    from_dt = dt.datetime.combine(debut.date(), dt.time.min)
    to_dt = dt.datetime.combine(end.date(), dt.time.max)
    items = get_full_calendar(session, from_dt, to_dt)
    for single_date in dates_in_range(from_dt.date(), to_dt.date()):
        blk = get_training_block_for_date(session, single_date)
        if blk and blk.get("fin"):  # une séance flexible n'entre en conflit avec rien
            items.append(blk)
    conflicts = find_conflicts(debut, fin, items, ignore_id=ignore_id)
    return [ev_to_read(e) for e in conflicts]


@router.post("/events", response_model=EvenementRead, status_code=201)
def create_ev(payload: EvenementCreate, session: SessionDep):
    ev = create_event(session, payload.model_dump())
    return EvenementRead.model_validate(ev)


@router.patch("/events/{event_id}", response_model=EvenementRead)
def update_ev(event_id: int, payload: EvenementUpdate, session: SessionDep):
    ev = update_event(session, event_id, payload.model_dump(exclude_none=True))
    if ev is None:
        raise HTTPException(404, "Événement introuvable")
    return EvenementRead.model_validate(ev)


@router.delete("/events/{event_id}", status_code=204)
def delete_ev(event_id: int, session: SessionDep):
    if not delete_event(session, event_id):
        raise HTTPException(404, "Événement introuvable")
