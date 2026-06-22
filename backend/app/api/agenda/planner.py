"""Sous-routeur Agenda : planificateur automatique de cycle (#502).

Voir docs/superpowers/specs/2026-06-04-agenda-auto-planner-design.md
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.api.agenda.common import SessionDep
from app.services.agenda import auto_plan, list_events_for_window
from app.services.agenda.planner import cycle_window
from app.services.agenda.gcal import (
    create_event as gcal_create_event,
    is_configured as gcal_is_configured,
)

router = APIRouter()


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


@router.get("/preferences")
def get_preferences() -> dict:
    """Préférences de planification (moment préféré par activité)."""
    from app.services.agenda.preferences import get_preferences as _get
    return _get()


@router.post("/preferences")
def set_preferences(patch: dict) -> dict:
    """Met à jour les préférences ; le prochain plan en tient compte."""
    from app.services.agenda.preferences import set_preferences as _set
    return _set(patch or {})


@router.get("/plan/preview")
def plan_preview(session: SessionDep, date: Optional[dt.date] = None) -> dict:
    """Calcule le planning du cycle. Lecture seule (aucune écriture)."""
    run_date = date or dt.date.today()
    return _serialize_plan(auto_plan.preview(session, run_date))


@router.post("/plan/commit")
def plan_commit(session: SessionDep, date: Optional[dt.date] = None) -> dict:
    """Recalcule côté serveur, remplace les blocs planner du cycle, écrit en local."""
    run_date = date or dt.date.today()
    prop, created = auto_plan.commit(session, run_date)
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
