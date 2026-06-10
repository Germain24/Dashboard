"""Sous-routeur Agenda : synchronisation Google Calendar + import/export iCal (#502)."""
from __future__ import annotations

import datetime as dt
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response, UploadFile
from sqlmodel import select

from app.api.agenda.common import SessionDep, dates_in_range
from app.api.agenda.schemas import EvenementRead, ImportIcalResponse
from app.core.config import settings
from app.models.agenda import Evenement
from app.services.agenda import (
    create_event,
    get_event,
    get_full_calendar,
    get_training_block_for_date,
    update_event,
)

log = logging.getLogger(__name__)
router = APIRouter()


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
    from app.services.agenda.ical_adapter import serialize_ics

    today = dt.date.today()
    from_dt = from_ or dt.datetime.combine(today - dt.timedelta(days=7), dt.time.min)
    to_dt = to or dt.datetime.combine(today + dt.timedelta(days=30), dt.time.max)

    items = get_full_calendar(session, from_dt, to_dt)
    for single_date in dates_in_range(from_dt.date(), to_dt.date()):
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
    from app.services.agenda.ical_import import import_ics_from_url

    try:
        counts = import_ics_from_url(session, url)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return ImportIcalResponse(**counts)
