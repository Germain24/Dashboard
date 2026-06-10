"""Sous-routeur Agenda : planificateur automatique de cycle (#502).

Voir docs/superpowers/specs/2026-06-04-agenda-auto-planner-design.md
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, HTTPException
from sqlmodel import Session

from app.api.agenda.common import SessionDep
from app.services.agenda import create_event, delete_event, list_events_for_window
from app.services.agenda.planner import TYPE_META, cycle_window, plan_cycle
from app.services.agenda.gcal import (
    create_event as gcal_create_event,
    is_configured as gcal_is_configured,
)

router = APIRouter()


def _gather_planner_inputs(session: Session, run_date: dt.date):
    """Construit les obstacles fixes (par jour) + les cours du cycle.

    Les blocs `source="planner"` sont ignorés (idempotence) : un nouveau calcul
    ne se planifie pas autour de ses propres blocs précédents.
    """
    from app.services.agenda import get_full_calendar

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
