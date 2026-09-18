"""Intensité d'entraînement pour une date — contrat figé avec Santé (CONV 3).

Le brief CONV 7 spécifie :

    Endpoint : GET /entrainement/intensity/{date}  (format YYYY-MM-DD)
    Retour   : { "date": "YYYY-MM-DD",
                 "intensity": "none" | "low" | "medium" | "high" }

Sémantique :
    none   : pas de séance prévue ce jour
    low    : récup active / mobilité (< 30 min, faible charge)
    medium : séance normale (~ 45-60 min)
    high   : séance lourde (> 60 min OU charge > 80% du 1RM moyen)

Priorités de résolution (1 = plus fort) :
    1. Séance réelle loggée ce jour-là → classify_intensity_for_session
    2. Programme actif : si le jour weekday() a un label != "Repos" → "medium"
       (séance planifiée ; on adoptera "low" si label == "Cardio")
    3. Fallback date-based identique au placeholder Santé pour ne rien casser
       si Entraînement est vide (cf. PLAN.md, note 11) :
       sport_days [0,1,2,4,5] → "medium", sinon "none".
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlmodel import Session, select

from app.models.entrainement import Seance, SetSerie
from app.services.entrainement.constants import (
    INTENSITY_LEVELS,
    SPORT_WEEKDAYS_DEFAULT,
)
from app.services.entrainement.one_rm import epley_1rm
from app.services.entrainement.programs import (
    get_active_program,
    program_day_for_date,
)
from app.services.entrainement.sessions import (
    classify_intensity_for_session,
    get_sessions_for_date,
)
from app.services.entrainement.sets import list_sets_for_seance

__all__ = [
    "INTENSITY_LEVELS",
    "default_intensity_for_date",
    "compute_intensity_for_date",
]


def default_intensity_for_date(
    date: dt.date,
    sport_days: Optional[list[int]] = None,
) -> str:
    """Fallback identique à celui de Santé (cf. services/sante/intensity.py)."""
    days = list(sport_days) if sport_days is not None else list(SPORT_WEEKDAYS_DEFAULT)
    return "medium" if date.weekday() in days else "none"


def _intensity_from_program_day(label: str) -> str:
    l = (label or "").strip().lower()
    if l in ("repos", "rest", ""):
        return "none"
    if l in ("cardio",):
        return "low"
    return "medium"


def _best_intensity(*candidates: str) -> str:
    order = {lvl: i for i, lvl in enumerate(INTENSITY_LEVELS)}
    best = "none"
    for c in candidates:
        c2 = c if c in order else "none"
        if order[c2] > order[best]:
            best = c2
    return best


def _best_1rm_before(
    session: Session,
    exercice_id: int,
    cutoff_dt: dt.datetime,
) -> float:
    """Meilleur 1RM estimé sur les séances strictement antérieures à cutoff.

    On exclut la séance en cours pour éviter qu'elle ne se compare à
    elle-même (ratio toujours 1.0 → faux positif "high").
    """
    stmt = (
        select(SetSerie)
        .join(Seance, Seance.id == SetSerie.seance_id)
        .where(SetSerie.exercice_id == exercice_id)
        .where(Seance.date < cutoff_dt)
    )
    best = 0.0
    for s in session.exec(stmt).all():
        e = epley_1rm(s.poids_kg, s.reps)
        if e > best:
            best = e
    return best


def compute_intensity_for_date(
    session: Session,
    date: dt.date,
    *,
    sport_days_fallback: Optional[list[int]] = None,
) -> str:
    """Intensité officielle de la date (contrat avec Santé).

    Priorité : séance loggée > programme planifié > fallback date-based.
    """
    seances: list[Seance] = get_sessions_for_date(session, date)
    if seances:
        levels: list[str] = []
        for s in seances:
            sets = list_sets_for_seance(session, s.id)
            ref_1rm: dict[int, float] = {}
            for st in sets:
                if st.exercice_id not in ref_1rm:
                    ref_1rm[st.exercice_id] = _best_1rm_before(
                        session, st.exercice_id, s.date,
                    )
            levels.append(classify_intensity_for_session(s, sets, ref_1rm))
        return _best_intensity(*levels)

    if get_active_program(session) is not None:
        pj = program_day_for_date(session, date)
        if pj is not None:
            return _intensity_from_program_day(pj.label)

    return default_intensity_for_date(date, sport_days_fallback)
