"""Remplissage auto de la semaine (#210).

Place des événements agenda pour les séances de sport (depuis le programme
actif d'entraînement) et les sessions d'étude (depuis l'objectif hebdo),
en respectant les créneaux libres existants.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlmodel import Session, select

from app.models.agenda import Evenement
from app.services.agenda.events import list_events_for_window
from app.services.agenda.slots import free_slots


# ─── Sport ────────────────────────────────────────────────────────────────────

def _pick_sport_slot(slots: list[dict[str, Any]], duree_min: int) -> dt.datetime | None:
    """Choisit le début du sport parmi les créneaux libres.

    Préférence : matin (< 12 h), sinon après-midi (12-18 h), sinon soir, puis le
    plus tôt dans la tranche. Retourne None si aucun créneau ne tient `duree_min`.
    """
    def band(h: int) -> int:
        return 0 if h < 12 else 1 if h < 18 else 2

    fit = [s for s in slots if s["duree_min"] >= duree_min]
    if not fit:
        return None
    fit.sort(key=lambda s: (band(s["debut"].hour), s["debut"]))
    return fit[0]["debut"]


def suggest_sport_events(
    session: Session,
    week_start: dt.date,
    start_hour: int = 8,
    duree_min: int = 60,
) -> list[dict[str, Any]]:
    """Propose un événement sport pour chaque jour ayant des exercices planifiés
    dans le programme actif d'entraînement.

    Le sport est placé sur un CRÉNEAU LIBRE (matin de préférence, sinon
    après-midi/soir si la matinée est occupée — ex. travail), au lieu d'une heure
    fixe. Repli sur `start_hour` si aucun créneau libre n'est trouvé.
    """
    try:
        from app.services.entrainement.programs import get_active_program, list_program_days
    except ImportError:
        return []

    prog = get_active_program(session)
    if not prog:
        return []

    days = list_program_days(session, prog.id)
    sport_days = {
        pj.weekday: pj.label
        for pj in days
        if pj.slots  # Repos = slots vide
    }

    suggestions: list[dict] = []
    for offset, label in sport_days.items():
        day = week_start + dt.timedelta(days=offset)
        from_dt = dt.datetime.combine(day, dt.time(0, 0))
        to_dt = dt.datetime.combine(day, dt.time(23, 59))
        # On ignore les events auto_semaine existants (sport/études déjà posés) pour
        # que le placement reste STABLE au re-lancement (sinon doublons).
        occupied = [
            (e.debut, e.fin or e.debut + dt.timedelta(hours=1))
            for e in list_events_for_window(session, from_dt, to_dt)
            if e.source != "auto_semaine"
        ]
        slots = free_slots(day, occupied, min_duration_min=duree_min)
        debut = _pick_sport_slot(slots, duree_min) or dt.datetime.combine(day, dt.time(start_hour, 0))
        fin = debut + dt.timedelta(minutes=duree_min)
        suggestions.append({
            "titre": f"Sport — {label}",
            "debut": debut,
            "fin": fin,
            "duree_min": duree_min,
            "categorie": "sport",
            "couleur": "#10B981",
            "source": "auto_semaine",
        })
    return suggestions


# ─── Études ───────────────────────────────────────────────────────────────────

def suggest_etudes_events(
    session: Session,
    week_start: dt.date,
    session_min: int = 90,
    start_hour: int = 9,
) -> list[dict[str, Any]]:
    """Propose des sessions d'étude dans les créneaux libres de la semaine
    pour atteindre l'objectif hebdomadaire."""
    try:
        from app.services.etudes.goals import get_weekly_hours
    except ImportError:
        return []

    target_min = int(get_weekly_hours() * 60)
    if target_min <= 0:
        return []

    placed_min = 0
    suggestions: list[dict] = []

    for offset in range(7):
        if placed_min >= target_min:
            break
        day = week_start + dt.timedelta(days=offset)
        from_dt = dt.datetime.combine(day, dt.time(0, 0))
        to_dt = dt.datetime.combine(day, dt.time(23, 59))
        events = list_events_for_window(session, from_dt, to_dt)
        occupied = [
            (e.debut, e.fin or e.debut + dt.timedelta(hours=1))
            for e in events
        ]
        slots = free_slots(day, occupied, min_duration_min=session_min, day_start_h=start_hour)
        for slot in slots:
            if placed_min >= target_min:
                break
            remaining = target_min - placed_min
            dur = min(session_min, remaining, slot["duree_min"])
            if dur < 30:
                continue
            debut = slot["debut"]
            fin = debut + dt.timedelta(minutes=dur)
            suggestions.append({
                "titre": "Session études",
                "debut": debut,
                "fin": fin,
                "duree_min": dur,
                "categorie": "etudes",
                "couleur": "#6366F1",
                "source": "auto_semaine",
            })
            placed_min += dur

    return suggestions


# ─── Orchestration ────────────────────────────────────────────────────────────

def fill_week_auto(
    session: Session,
    week_start: dt.date,
    *,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Remplit la semaine avec des événements auto (sport + études).

    Si dry_run=True : retourne les suggestions sans les persister.
    Idempotent : ne crée pas de doublon sur le même debut.
    """
    all_suggestions = (
        suggest_sport_events(session, week_start)
        + suggest_etudes_events(session, week_start)
    )

    if dry_run or not all_suggestions:
        return all_suggestions

    # Récupère les debuts déjà présents (auto_semaine) pour idempotence
    from_dt = dt.datetime.combine(week_start, dt.time(0, 0))
    to_dt = dt.datetime.combine(week_start + dt.timedelta(days=7), dt.time(0, 0))
    existing = session.exec(
        select(Evenement)
        .where(Evenement.source == "auto_semaine")
        .where(Evenement.debut >= from_dt)
        .where(Evenement.debut < to_dt)
    ).all()
    existing_debuts = {e.debut for e in existing}

    created: list[dict] = []
    for s in all_suggestions:
        if s["debut"] in existing_debuts:
            continue
        ev = Evenement(
            titre=s["titre"],
            debut=s["debut"],
            fin=s["fin"],
            categorie=s["categorie"],
            couleur=s.get("couleur"),
            source="auto_semaine",
        )
        session.add(ev)
        created.append(s)
        existing_debuts.add(s["debut"])

    session.commit()
    return created
