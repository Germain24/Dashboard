"""Sous-routeur Agenda : ping, vue jour, slots libres, bloc focus (#502)."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.api.agenda.common import SessionDep, ev_to_read
from app.api.agenda.schemas import AgendaJourResponse, EvenementRead, SlotLibre, TacheRead
from app.services.agenda import (
    create_event,
    free_slots,
    get_full_calendar,
    get_training_block_for_date,
    tasks_due_today,
)

router = APIRouter()


@router.get("/ping")
def ping() -> dict:
    return {"module": "agenda", "ready": True}


@router.get("/today", response_model=AgendaJourResponse)
def today(session: SessionDep):
    """Vue complète du jour : events + séance entraînement + slots + tâches."""
    today_date = dt.date.today()
    from_dt = dt.datetime.combine(today_date, dt.time.min)
    to_dt = dt.datetime.combine(today_date, dt.time.max)

    raw_events = get_full_calendar(session, from_dt, to_dt)
    training = get_training_block_for_date(session, today_date)
    if training:
        raw_events.append(training)
        raw_events.sort(key=lambda x: x["debut"])

    occupied = [
        (e["debut"], e["fin"] or e["debut"] + dt.timedelta(hours=1))
        for e in raw_events if e.get("fin")
    ]
    slots = free_slots(today_date, occupied)
    urgentes = tasks_due_today(session)

    return AgendaJourResponse(
        date=today_date,
        evenements=[ev_to_read(e) for e in raw_events if e.get("source") != "entrainement"],
        seance_entrainement=ev_to_read(training) if training else None,
        slots_libres=[SlotLibre(**s) for s in slots],
        taches_urgentes=[TacheRead.model_validate(t) for t in urgentes],
    )


@router.get("/slots", response_model=list[SlotLibre])
def slots_endpoint(
    session: SessionDep,
    date: Optional[dt.date] = Query(None),
    min_duration: int = Query(60, ge=15),
    day_start_h: int = Query(7, ge=0, le=23),
    day_end_h: int = Query(23, ge=1, le=24),
):
    target = date or dt.date.today()
    from_dt = dt.datetime.combine(target, dt.time.min)
    to_dt = dt.datetime.combine(target, dt.time.max)

    items = get_full_calendar(session, from_dt, to_dt)
    blk = get_training_block_for_date(session, target)
    if blk:
        items.append(blk)

    occupied = [
        (e["debut"], e["fin"] or e["debut"] + dt.timedelta(hours=1))
        for e in items if e.get("fin")
    ]
    raw = free_slots(target, occupied, min_duration, day_start_h, day_end_h)
    return [SlotLibre(**s) for s in raw]


@router.post("/focus", response_model=EvenementRead, status_code=201)
def plan_focus(
    session: SessionDep,
    duree_min: int = Query(60, ge=15, le=480),
    date: Optional[dt.date] = Query(None),
    titre: Optional[str] = Query(None),
    cours: Optional[str] = Query(None, description="Code/nom du cours à réviser"),
    day_start_h: int = Query(8, ge=0, le=23),
    day_end_h: int = Query(23, ge=1, le=24),
):
    """Planifie un bloc focus Études dans le premier créneau libre suffisant (#89)."""
    from app.services.agenda.focus import pick_slot

    target = date or dt.date.today()
    from_dt = dt.datetime.combine(target, dt.time.min)
    to_dt = dt.datetime.combine(target, dt.time.max)
    items = get_full_calendar(session, from_dt, to_dt)
    blk = get_training_block_for_date(session, target)
    if blk:
        items.append(blk)
    occupied = [
        (e["debut"], e["fin"] or e["debut"] + dt.timedelta(hours=1))
        for e in items if e.get("fin")
    ]
    slots = free_slots(target, occupied, duree_min, day_start_h, day_end_h)
    chosen = pick_slot(slots, duree_min)
    if chosen is None:
        raise HTTPException(409, f"Aucun créneau libre de {duree_min} min le {target}.")

    label = titre or (f"Focus — {cours}" if cours else "Focus études")
    ev = create_event(session, {
        "titre": label,
        "debut": chosen["debut"],
        "fin": chosen["fin"],
        "categorie": "etudes",
        "source": "etudes_focus",
        "description": cours,
    })
    return EvenementRead.model_validate(ev)
