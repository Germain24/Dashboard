"""Router FastAPI — module Agenda (CONV 5).

Endpoints :
  GET  /agenda/ping
  GET  /agenda/today
  GET  /agenda/events?from=&to=
  POST /agenda/events
  PATCH /agenda/events/{id}
  DELETE /agenda/events/{id}
  GET  /agenda/recurrences
  POST /agenda/recurrences
  PATCH /agenda/recurrences/{id}
  DELETE /agenda/recurrences/{id}
  GET  /agenda/tasks
  POST /agenda/tasks
  PATCH /agenda/tasks/{id}
  POST /agenda/tasks/{id}/done
  DELETE /agenda/tasks/{id}
  GET  /agenda/slots?date=&min_duration=
  POST /agenda/import-ical
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlmodel import Session

from app.api.schemas_agenda import (
    AgendaJourResponse,
    EvenementCreate,
    EvenementRead,
    EvenementUpdate,
    ImportIcalResponse,
    RegleRecurrenceCreate,
    RegleRecurrenceRead,
    RegleRecurrenceUpdate,
    SlotLibre,
    TacheCreate,
    TacheRead,
    TacheUpdate,
)
from app.core.db import get_session
from app.services.agenda import (
    create_event,
    create_recurrence_rule,
    create_task,
    delete_event,
    delete_recurrence_rule,
    delete_task,
    free_slots,
    get_event,
    get_full_calendar,
    get_recurrence_rule,
    get_task,
    get_training_block_for_date,
    list_recurrence_rules,
    list_tasks,
    mark_done,
    parse_ics,
    tasks_due_today,
    update_event,
    update_recurrence_rule,
    update_task,
)
from app.models.agenda import Evenement

log = logging.getLogger(__name__)
router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


def _ev_to_read(d: dict) -> EvenementRead:
    return EvenementRead(**d)


# ── Ping ─────────────────────────────────────────────────────────────────────

@router.get("/ping")
def ping() -> dict:
    return {"module": "agenda", "ready": True}


# ── Vue Jour ─────────────────────────────────────────────────────────────────

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
        evenements=[_ev_to_read(e) for e in raw_events if e.get("source") != "entrainement"],
        seance_entrainement=_ev_to_read(training) if training else None,
        slots_libres=[SlotLibre(**s) for s in slots],
        taches_urgentes=[TacheRead.model_validate(t) for t in urgentes],
    )


# ── Événements ───────────────────────────────────────────────────────────────

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
        for single_date in _dates_in_range(from_dt.date(), to_dt.date()):
            blk = get_training_block_for_date(session, single_date)
            if blk:
                items.append(blk)
    items.sort(key=lambda x: x["debut"])
    return [_ev_to_read(e) for e in items]


def _dates_in_range(start: dt.date, end: dt.date) -> list[dt.date]:
    result = []
    cur = start
    while cur <= end:
        result.append(cur)
        cur += dt.timedelta(days=1)
    return result


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
    for single_date in _dates_in_range(from_dt.date(), to_dt.date()):
        blk = get_training_block_for_date(session, single_date)
        if blk:
            items.append(blk)
    conflicts = find_conflicts(debut, fin, items, ignore_id=ignore_id)
    return [_ev_to_read(e) for e in conflicts]


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


# ── Récurrences ───────────────────────────────────────────────────────────────

@router.get("/recurrences", response_model=list[RegleRecurrenceRead])
def list_rules(session: SessionDep):
    return [RegleRecurrenceRead.model_validate(r) for r in list_recurrence_rules(session)]


@router.post("/recurrences", response_model=RegleRecurrenceRead, status_code=201)
def create_rule(payload: RegleRecurrenceCreate, session: SessionDep):
    rule = create_recurrence_rule(session, payload.model_dump())
    return RegleRecurrenceRead.model_validate(rule)


@router.patch("/recurrences/{rule_id}", response_model=RegleRecurrenceRead)
def update_rule(rule_id: int, payload: RegleRecurrenceUpdate, session: SessionDep):
    rule = update_recurrence_rule(session, rule_id, payload.model_dump(exclude_none=True))
    if rule is None:
        raise HTTPException(404, "Règle introuvable")
    return RegleRecurrenceRead.model_validate(rule)


@router.delete("/recurrences/{rule_id}", status_code=204)
def delete_rule(rule_id: int, session: SessionDep):
    if not delete_recurrence_rule(session, rule_id):
        raise HTTPException(404, "Règle introuvable")


# ── Tâches ───────────────────────────────────────────────────────────────────

@router.get("/tasks", response_model=list[TacheRead])
def list_taches(
    session: SessionDep,
    statut: Optional[str] = None,
    categorie: Optional[str] = None,
):
    return [TacheRead.model_validate(t) for t in list_tasks(session, statut, categorie)]


@router.post("/tasks", response_model=TacheRead, status_code=201)
def create_tache(payload: TacheCreate, session: SessionDep):
    t = create_task(session, payload.model_dump())
    return TacheRead.model_validate(t)


@router.patch("/tasks/{task_id}", response_model=TacheRead)
def update_tache(task_id: int, payload: TacheUpdate, session: SessionDep):
    t = update_task(session, task_id, payload.model_dump(exclude_none=True))
    if t is None:
        raise HTTPException(404, "Tâche introuvable")
    return TacheRead.model_validate(t)


@router.post("/tasks/{task_id}/done", response_model=TacheRead)
def done_tache(task_id: int, session: SessionDep):
    t = mark_done(session, task_id)
    if t is None:
        raise HTTPException(404, "Tâche introuvable")
    return TacheRead.model_validate(t)


@router.delete("/tasks/{task_id}", status_code=204)
def delete_tache(task_id: int, session: SessionDep):
    if not delete_task(session, task_id):
        raise HTTPException(404, "Tâche introuvable")


# ── Slots libres ─────────────────────────────────────────────────────────────

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


# ── Export iCal ───────────────────────────────────────────────────────────────

@router.get("/export-ical")
def export_ical(
    session: SessionDep,
    from_: Optional[dt.datetime] = Query(None, alias="from"),
    to: Optional[dt.datetime] = Query(None),
):
    """Exporte les événements de la fenêtre au format .ics (#91)."""
    from fastapi import Response
    from app.services.agenda.ical_adapter import serialize_ics

    today = dt.date.today()
    from_dt = from_ or dt.datetime.combine(today - dt.timedelta(days=7), dt.time.min)
    to_dt = to or dt.datetime.combine(today + dt.timedelta(days=30), dt.time.max)

    items = get_full_calendar(session, from_dt, to_dt)
    for single_date in _dates_in_range(from_dt.date(), to_dt.date()):
        blk = get_training_block_for_date(session, single_date)
        if blk:
            items.append(blk)
    ics = serialize_ics(items)
    return Response(
        content=ics,
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="mission-control.ics"'},
    )


# ── Import iCal ───────────────────────────────────────────────────────────────

@router.post("/import-ical", response_model=ImportIcalResponse)
async def import_ical(file: UploadFile, session: SessionDep):
    content = await file.read()
    parsed = parse_ics(content)

    created_events = skipped = created_rules = 0
    for item in parsed:
        rrule = item.pop("_rrule", None)
        uid = item.get("source_id", "")

        # Déduplication par UID iCal
        from sqlmodel import select
        existing = session.exec(
            select(Evenement).where(Evenement.source_id == uid).where(Evenement.source == "ical")
        ).first() if uid else None

        if existing:
            skipped += 1
            continue

        rule_id = None
        if rrule:
            rule_data = {
                "titre": item["titre"],
                "weekdays": rrule["weekdays"],
                "start_time": rrule["start_time"],
                "end_time": rrule["end_time"],
                "until": rrule["until"],
                "categorie": item.get("categorie"),
                "lieu": item.get("lieu"),
            }
            rule = create_recurrence_rule(session, rule_data)
            rule_id = rule.id
            created_rules += 1

        item["recurrence_id"] = rule_id
        create_event(session, item)
        created_events += 1

    return ImportIcalResponse(
        created_events=created_events,
        skipped_duplicates=skipped,
        created_rules=created_rules,
    )
