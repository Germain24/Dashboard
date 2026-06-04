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

from app.core.config import settings
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
    list_events_for_window,
    list_recurrence_rules,
    list_tasks,
    mark_done,
    tasks_due_today,
    update_event,
    update_recurrence_rule,
    update_task,
)
from app.services.agenda.planner import TYPE_META, cycle_window, plan_cycle
from app.services.agenda.gcal import (
    create_event as gcal_create_event,
    is_configured as gcal_is_configured,
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


# ── Planificateur automatique ────────────────────────────────────────────────
# Voir docs/superpowers/specs/2026-06-04-agenda-auto-planner-design.md


def _gather_planner_inputs(session: Session, run_date: dt.date):
    """Construit les obstacles fixes (par jour) + les cours du cycle.

    Les blocs `source="planner"` sont ignorés (idempotence) : un nouveau calcul
    ne se planifie pas autour de ses propres blocs précédents.
    """
    start, end = cycle_window(run_date)
    from_dt = dt.datetime.combine(start, dt.time.min)
    to_dt = dt.datetime.combine(end, dt.time.max)
    cal = get_full_calendar(session, from_dt, to_dt)

    fixed_by_day: dict[dt.date, list[tuple[dt.datetime, dt.datetime]]] = {}
    courses: list[str] = []
    seen: set[str] = set()
    for it in cal:
        if it.get("source") == "planner" or not it.get("fin"):
            continue
        debut, fin = it["debut"], it["fin"]
        fixed_by_day.setdefault(debut.date(), []).append((debut, fin))
        if it.get("categorie") == "cours":
            name = it.get("titre") or "Cours"
            if name not in seen:
                seen.add(name)
                courses.append(name)
    return fixed_by_day, courses


def _serialize_plan(prop) -> dict:
    return {
        "fenetre": {
            "debut": prop.window_start.isoformat(),
            "fin": prop.window_end.isoformat(),
        },
        "blocs": [
            {
                "date": b.date.isoformat(),
                "debut": b.debut.isoformat(),
                "fin": b.fin.isoformat(),
                "type": b.type,
                "titre": b.titre,
            }
            for b in prop.blocks
        ],
        "non_places": prop.non_places,
    }


@router.get("/plan/preview")
def plan_preview(session: SessionDep, date: Optional[dt.date] = None) -> dict:
    """Calcule le planning du cycle. Lecture seule (aucune écriture)."""
    run_date = date or dt.date.today()
    fixed, courses = _gather_planner_inputs(session, run_date)
    return _serialize_plan(plan_cycle(run_date, fixed, courses))


@router.post("/plan/commit")
def plan_commit(session: SessionDep, date: Optional[dt.date] = None) -> dict:
    """Recalcule côté serveur, remplace les blocs planner du cycle, écrit en local."""
    run_date = date or dt.date.today()
    fixed, courses = _gather_planner_inputs(session, run_date)
    prop = plan_cycle(run_date, fixed, courses)

    from_dt = dt.datetime.combine(prop.window_start, dt.time.min)
    to_dt = dt.datetime.combine(prop.window_end, dt.time.max)
    for ev in list_events_for_window(session, from_dt, to_dt):
        if ev.source == "planner" and ev.id is not None:
            delete_event(session, ev.id)

    created = 0
    for b in prop.blocks:
        meta = TYPE_META.get(b.type, {"categorie": "autre", "couleur": None})
        create_event(
            session,
            {
                "titre": b.titre,
                "debut": b.debut,
                "fin": b.fin,
                "categorie": meta["categorie"],
                "couleur": meta["couleur"],
                "source": "planner",
                "description": "Bloc planifié automatiquement.",
            },
        )
        created += 1
    return {**_serialize_plan(prop), "created": created}


@router.post("/plan/push")
def plan_push(session: SessionDep, date: Optional[dt.date] = None) -> dict:
    """Pousse les blocs planner du cycle vers Google Calendar (#83).

    Ne pousse que les blocs `source="planner"` pas encore synchronisés (sans
    `source_id`) ; stocke l'id Google retourné pour éviter les doublons.
    """
    if not gcal_is_configured():
        raise HTTPException(
            503,
            "Google Calendar non configuré. Renseigne GOOGLE_* dans .env "
            "(voir scripts/google_oauth_setup.py).",
        )
    run_date = date or dt.date.today()
    start, end = cycle_window(run_date)
    from_dt = dt.datetime.combine(start, dt.time.min)
    to_dt = dt.datetime.combine(end, dt.time.max)

    pushed = 0
    for ev in list_events_for_window(session, from_dt, to_dt):
        if ev.source != "planner" or ev.source_id:
            continue
        res = gcal_create_event(
            {
                "titre": ev.titre,
                "debut": ev.debut,
                "fin": ev.fin,
                "lieu": ev.lieu,
                "description": ev.description,
            }
        )
        ev.source_id = res.get("id")
        session.add(ev)
        pushed += 1
    session.commit()
    return {"pushed": pushed}


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


# ── Bloc focus Études (#89) ───────────────────────────────────────────────────

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
    """Planifie un bloc focus Études dans le premier créneau libre suffisant."""
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


# ── Google Calendar (OAuth, #83) ──────────────────────────────────────────────

@router.get("/gcal/status")
def gcal_status():
    """Indique si l'intégration Google Calendar est configurée."""
    from app.services.agenda import gcal
    return {"configured": gcal.is_configured(), "calendar_id": settings.google_calendar_id}


@router.post("/gcal/pull", response_model=ImportIcalResponse)
def gcal_pull(
    session: SessionDep,
    from_: Optional[dt.datetime] = Query(None, alias="from"),
    to: Optional[dt.datetime] = Query(None),
):
    """Importe les événements Google Calendar de la fenêtre (Google → app, #83)."""
    from sqlmodel import select
    from app.services.agenda import gcal

    if not gcal.is_configured():
        raise HTTPException(503, "Google Calendar non configuré (cf. scripts/google_oauth_setup.py).")

    today = dt.date.today()
    from_dt = from_ or dt.datetime.combine(today - dt.timedelta(days=7), dt.time.min)
    to_dt = to or dt.datetime.combine(today + dt.timedelta(days=30), dt.time.max)
    try:
        events = gcal.list_events(from_dt, to_dt)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Lecture Google Calendar impossible : {e}")

    created = skipped = 0
    for item in events:
        uid = item.get("source_id")
        existing = session.exec(
            select(Evenement).where(Evenement.source_id == uid)
        ).first() if uid else None
        if existing:
            skipped += 1
            continue
        create_event(session, item)
        created += 1
    return ImportIcalResponse(created_events=created, skipped_duplicates=skipped, created_rules=0)


@router.post("/gcal/push/{event_id}", response_model=EvenementRead)
def gcal_push(event_id: int, session: SessionDep):
    """Pousse un événement local vers Google Calendar (app → Google, #83)."""
    from app.services.agenda import gcal

    if not gcal.is_configured():
        raise HTTPException(503, "Google Calendar non configuré.")
    ev = get_event(session, event_id)
    if ev is None:
        raise HTTPException(404, "Événement introuvable")
    payload = {
        "titre": ev.titre, "debut": ev.debut, "fin": ev.fin,
        "lieu": ev.lieu, "description": ev.description,
    }
    try:
        if ev.source == "gcal" and ev.source_id:
            gcal.update_event(ev.source_id, payload)
        else:
            created = gcal.create_event(payload)
            # On mémorise l'id Google pour éviter un doublon au prochain pull.
            updated = update_event(session, event_id, {"source": "gcal", "source_id": created.get("id")})
            ev = updated or ev
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Écriture Google Calendar impossible : {e}")
    return EvenementRead.model_validate(ev)


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
    from app.services.agenda.ical_import import import_ics_bytes
    counts = import_ics_bytes(session, await file.read())
    return ImportIcalResponse(**counts)


@router.post("/sync-ical-url", response_model=ImportIcalResponse)
def sync_ical_url(session: SessionDep, url: str = Query(..., description="URL .ics distante (ex. adresse secrète Google Calendar)")):
    """Sync entrante Google Calendar (et autres) via URL .ics (#83).

    Récupère un calendrier .ics distant et l'importe (dédup par UID). C'est la
    voie sans OAuth : coller l'« adresse secrète au format iCal » de Google
    Calendar. L'export #91 couvre le sens inverse (app → Google via import .ics).
    """
    import httpx
    from app.services.agenda.ical_import import import_ics_bytes

    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "URL invalide (http/https attendu).")
    try:
        resp = httpx.get(url, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Récupération du calendrier impossible : {e}")
    counts = import_ics_bytes(session, resp.content)
    return ImportIcalResponse(**counts)
