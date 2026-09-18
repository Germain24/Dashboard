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
from app.services.agenda.planner import SPORT_WEEKDAYS, TYPE_META, Proposal, cycle_window, plan_cycle


def _moments() -> dict[str, str]:
    """Moment préféré par activité (page Préférences)."""
    try:
        from app.services.agenda.preferences import get_preferences

        return get_preferences().get("moments") or {}
    except Exception:
        return {}


def gather_inputs(
    session: Session, run_date: dt.date
) -> tuple[
    dict[dt.date, list[tuple[dt.datetime, dt.datetime]]],
    dict[dt.date, list[tuple[dt.datetime, dt.datetime]]],
]:
    """Obstacles fixes et révisions existantes. Ignore les blocs `planner`
    (idempotence : on ne planifie pas autour de ses propres blocs précédents).
    Inclut les shifts de travail du module Travail comme obstacles fixes."""
    start, end = cycle_window(run_date)
    from_dt = dt.datetime.combine(start, dt.time.min)
    # Le dernier sommeil du cycle traverse la nuit vers end + 1 jour : inclure
    # les obligations matinales du lendemain pour réserver la marge de réveil.
    to_dt = dt.datetime.combine(end + dt.timedelta(days=1), dt.time.max)
    cal = get_full_calendar(session, from_dt, to_dt)

    fixed_by_day: dict[dt.date, list[tuple[dt.datetime, dt.datetime]]] = {}
    revisions_by_day: dict[dt.date, list[tuple[dt.datetime, dt.datetime]]] = {}

    # Shifts de travail : obstacles fixes.
    try:
        from app.services.travail.shifts import list_shifts_for_window

        work_shifts = list_shifts_for_window(session, from_dt, to_dt)
        for s in work_shifts:
            debut = s.get("debut")
            fin = s.get("fin")
            if debut and fin:
                fixed_by_day.setdefault(debut.date(), []).append((debut, fin))
    except Exception:
        pass  # module travail non initialisé ou sans shifts

    for it in cal:
        if it.get("source") == "planner" or not it.get("fin"):
            continue
        debut, fin = it["debut"], it["fin"]
        fixed_by_day.setdefault(debut.date(), []).append((debut, fin))
        if it.get("source") == "revision_planner":
            revisions_by_day.setdefault(debut.date(), []).append((debut, fin))
            continue
    return fixed_by_day, revisions_by_day


def preview(session: Session, run_date: dt.date) -> Proposal:
    """Calcule le plan du cycle (lecture seule)."""
    fixed, revisions_by_day = gather_inputs(session, run_date)
    return plan_cycle(
        # Les révisions par cours sont gérées une fois par semaine par
        # `weekly_revisions`, qui peut utiliser Shopify le dimanche et compte
        # les shifts de toute la semaine avant de choisir les créneaux.
        run_date,
        fixed,
        [],
        sport_weekdays=SPORT_WEEKDAYS,
        moments=_moments(),
        revisions_by_day=revisions_by_day,
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
    from app.services.agenda.weekly_revisions import replan_future_revisions_for_window

    replan_future_revisions_for_window(session, prop.window_start, prop.window_end)
    return prop, created
