"""Orchestrateur du planificateur UNIQUE (#502/#210 fusionnés).

Un seul moteur (`plan_cycle`) et une seule source d'événements (`source="planner"`).
Rassemble les entrées (obstacles fixes, cours, jours de sport du programme
d'entraînement actif, objectif d'études hebdo), lance le planificateur de cycle,
et persiste les blocs. Utilisé à la fois par l'API Agenda (/plan/*) et par la
routine « semaine auto » — fini les deux planificateurs concurrents qui créaient
des doublons de sport.
"""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session

from app.services.agenda import (
    create_event,
    delete_event,
    get_full_calendar,
    list_events_for_window,
)
from app.services.agenda.planner import TYPE_META, Proposal, cycle_window, plan_cycle


def _program_sport_weekdays(session: Session) -> set[int] | None:
    """Jours de sport depuis le programme d'entraînement actif (None si aucun)."""
    try:
        from app.services.entrainement.programs import get_active_program, list_program_days
        prog = get_active_program(session)
        if not prog:
            return None
        wd = {pj.weekday for pj in list_program_days(session, prog.id) if pj.slots}
        return wd or None
    except Exception:
        return None


def _etudes_target_min(session: Session) -> int:
    """Minutes d'études à planifier sur le cycle (objectif hebdo)."""
    try:
        from app.services.etudes.goals import get_weekly_hours
        return int(get_weekly_hours() * 60)
    except Exception:
        return 0


def gather_inputs(
    session: Session, run_date: dt.date
) -> tuple[dict[dt.date, list[tuple[dt.datetime, dt.datetime]]], list[str]]:
    """Obstacles fixes (par jour) + cours du cycle. Ignore les blocs `planner`
    (idempotence : on ne planifie pas autour de ses propres blocs précédents)."""
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


def preview(session: Session, run_date: dt.date) -> Proposal:
    """Calcule le plan du cycle (lecture seule)."""
    fixed, courses = gather_inputs(session, run_date)
    return plan_cycle(
        run_date, fixed, courses,
        sport_weekdays=_program_sport_weekdays(session),
        etudes_target_min=_etudes_target_min(session),
    )


def commit(session: Session, run_date: dt.date) -> tuple[Proposal, int]:
    """Remplace les blocs `planner` du cycle et écrit le nouveau plan. Idempotent."""
    prop = preview(session, run_date)
    from_dt = dt.datetime.combine(prop.window_start, dt.time.min)
    to_dt = dt.datetime.combine(prop.window_end, dt.time.max)
    for ev in list_events_for_window(session, from_dt, to_dt):
        if ev.source == "planner" and ev.id is not None:
            delete_event(session, ev.id)
    created = 0
    for b in prop.blocks:
        meta = TYPE_META.get(b.type, {"categorie": "autre", "couleur": None})
        create_event(session, {
            "titre": b.titre, "debut": b.debut, "fin": b.fin,
            "categorie": meta["categorie"], "couleur": meta["couleur"],
            "source": "planner", "description": "Bloc planifié automatiquement.",
        })
        created += 1
    return prop, created
