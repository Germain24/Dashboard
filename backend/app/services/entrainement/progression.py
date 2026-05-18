"""Progression sur un exercice : courbe 1RM estimé + volume.

Tendance par défaut sur 90 jours, agrégation par séance.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Optional

from sqlmodel import Session, select

from app.models.entrainement import Seance, SetSerie
from app.services.entrainement.one_rm import best_1rm_from_sets, epley_1rm


@dataclass
class ProgressionPoint:
    date: dt.date
    best_1rm_kg: float
    volume_kg: float    # somme(poids × reps) sur la séance
    top_set_kg: float   # poids de la série la plus lourde
    nb_sets: int


@dataclass
class ProgressionSummary:
    exercice_id: int
    points: list[ProgressionPoint]
    current_1rm_kg: float
    best_1rm_kg: float
    delta_4w_pct: Optional[float]  # variation 1RM vs il y a 4 semaines


def _sets_grouped_by_seance(
    session: Session, exercice_id: int, since: dt.date
) -> dict[int, tuple[dt.date, list[SetSerie]]]:
    """Récupère les séries d'un exercice depuis `since`, groupées par séance."""
    cutoff = dt.datetime.combine(since, dt.time.min)
    stmt = (
        select(SetSerie, Seance)
        .where(SetSerie.exercice_id == exercice_id)
        .join(Seance, Seance.id == SetSerie.seance_id)
        .where(Seance.date >= cutoff)
        .order_by(Seance.date.asc(), SetSerie.ordre.asc())
    )
    grouped: dict[int, tuple[dt.date, list[SetSerie]]] = {}
    for s, seance in session.exec(stmt).all():
        grouped.setdefault(seance.id, (seance.date.date(), []))[1].append(s)
    return grouped


def progression_for_exercice(
    session: Session,
    exercice_id: int,
    *,
    days: int = 90,
) -> ProgressionSummary:
    """Retourne la progression sur `days` jours pour un exercice."""
    since = dt.date.today() - dt.timedelta(days=days)
    grouped = _sets_grouped_by_seance(session, exercice_id, since)

    points: list[ProgressionPoint] = []
    for _, (date, sets) in sorted(grouped.items(), key=lambda kv: kv[1][0]):
        as_dicts = [{"reps": s.reps, "poids_kg": s.poids_kg} for s in sets]
        best = best_1rm_from_sets(as_dicts)
        volume = sum((s.reps or 0) * (s.poids_kg or 0.0) for s in sets)
        top_set = max((s.poids_kg or 0.0) for s in sets) if sets else 0.0
        points.append(ProgressionPoint(
            date=date,
            best_1rm_kg=round(best, 2),
            volume_kg=round(volume, 2),
            top_set_kg=round(top_set, 2),
            nb_sets=len(sets),
        ))

    current = points[-1].best_1rm_kg if points else 0.0
    best_overall = max((p.best_1rm_kg for p in points), default=0.0)

    delta_4w: Optional[float] = None
    if points:
        four_weeks_ago = points[-1].date - dt.timedelta(days=28)
        # Prend le point le plus proche ≤ four_weeks_ago
        anchor = None
        for p in points:
            if p.date <= four_weeks_ago:
                anchor = p
        if anchor and anchor.best_1rm_kg > 0:
            delta_4w = round((current - anchor.best_1rm_kg) / anchor.best_1rm_kg * 100, 2)

    return ProgressionSummary(
        exercice_id=exercice_id,
        points=points,
        current_1rm_kg=current,
        best_1rm_kg=best_overall,
        delta_4w_pct=delta_4w,
    )


def current_1rm(session: Session, exercice_id: int, *, days: int = 90) -> float:
    """1RM estimé courant : meilleure série Epley sur les `days` derniers jours."""
    since = dt.date.today() - dt.timedelta(days=days)
    cutoff = dt.datetime.combine(since, dt.time.min)
    stmt = (
        select(SetSerie)
        .where(SetSerie.exercice_id == exercice_id)
        .join(Seance, Seance.id == SetSerie.seance_id)
        .where(Seance.date >= cutoff)
    )
    rows = session.exec(stmt).all()
    best = 0.0
    for s in rows:
        e = epley_1rm(s.poids_kg, s.reps)
        if e > best:
            best = e
    return round(best, 2)
