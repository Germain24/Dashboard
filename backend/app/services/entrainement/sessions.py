"""CRUD des séances (Seance) + classification d'intensité."""

from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlmodel import Session, select

from app.models.entrainement import Seance, SetSerie
from app.services.entrainement.constants import (
    DUREE_HIGH_MIN_MIN,
    DUREE_LOW_MAX_MIN,
    PCT_1RM_HIGH,
)
from app.services.entrainement.one_rm import epley_1rm


def session_tonnage(sets) -> float:
    """Tonnage total d'une séance = somme(reps × poids) sur toutes les séries (#108)."""
    return round(sum((s.reps or 0) * (s.poids_kg or 0.0) for s in sets), 1)


def session_rpe(sets):
    """RPE moyen de la séance = moyenne des RPE renseignés sur ses séries, ou None (#111)."""
    vals = [s.rpe for s in sets if s.rpe is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


def list_sessions(
    session: Session,
    *,
    date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None,
) -> list[Seance]:
    stmt = select(Seance)
    if date_from:
        stmt = stmt.where(Seance.date >= dt.datetime.combine(date_from, dt.time.min))
    if date_to:
        stmt = stmt.where(Seance.date <= dt.datetime.combine(date_to, dt.time.max))
    stmt = stmt.order_by(Seance.date.desc())
    return list(session.exec(stmt).all())


def get_session_row(session: Session, seance_id: int) -> Optional[Seance]:
    return session.get(Seance, seance_id)


def get_sessions_for_date(session: Session, date: dt.date) -> list[Seance]:
    start = dt.datetime.combine(date, dt.time.min)
    end = dt.datetime.combine(date, dt.time.max)
    stmt = (
        select(Seance)
        .where(Seance.date >= start)
        .where(Seance.date <= end)
        .order_by(Seance.date.asc())
    )
    return list(session.exec(stmt).all())


def create_session(
    session: Session,
    *,
    date: dt.datetime,
    type: Optional[str] = None,
    duree_min: Optional[int] = None,
    note: Optional[str] = None,
    programme_jour_id: Optional[int] = None,
    intensite: Optional[str] = None,
    source: str = "manual",
) -> Seance:
    s = Seance(
        date=date,
        type=type,
        duree_min=duree_min,
        note=note,
        programme_jour_id=programme_jour_id,
        intensite=intensite,
        source=source,
    )
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


def update_session(session: Session, seance_id: int, **changes) -> Optional[Seance]:
    s = get_session_row(session, seance_id)
    if s is None:
        return None
    for k, v in changes.items():
        if v is None:
            continue
        if not hasattr(s, k):
            continue
        setattr(s, k, v)
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


def delete_session(session: Session, seance_id: int) -> bool:
    s = get_session_row(session, seance_id)
    if s is None:
        return False
    # Cascade manuel des séries (SQLite ne le fait pas via FK seul)
    rows = session.exec(select(SetSerie).where(SetSerie.seance_id == seance_id)).all()
    for r in rows:
        session.delete(r)
    session.delete(s)
    session.commit()
    return True


def classify_intensity_for_session(
    seance: Seance,
    sets: list[SetSerie],
    best_1rm_by_exercice: Optional[dict[int, float]] = None,
) -> str:
    """Retourne `low / medium / high` pour une séance donnée.

    Règles (cf. brief CONV 7, "Lien avec Nutrition") :
    - séance cardio → `low`
    - duree < 30 min → `low`
    - duree > 60 min OU charge moyenne > 80% du 1RM → `high`
    - sinon → `medium`

    Si `seance.intensite` est déjà fixée manuellement, on la respecte.
    """
    if seance.intensite in ("none", "low", "medium", "high"):
        return seance.intensite

    if (seance.type or "").lower() == "cardio":
        return "low"

    duree = seance.duree_min or 0
    if duree and duree < DUREE_LOW_MAX_MIN:
        return "low"
    if duree and duree > DUREE_HIGH_MIN_MIN:
        return "high"

    if best_1rm_by_exercice:
        ratios: list[float] = []
        for s in sets:
            ref = best_1rm_by_exercice.get(s.exercice_id, 0.0)
            if ref <= 0:
                continue
            est_now = epley_1rm(s.poids_kg, s.reps)
            if est_now <= 0:
                continue
            ratios.append(s.poids_kg / ref)
        if ratios and (sum(ratios) / len(ratios)) > PCT_1RM_HIGH:
            return "high"

    return "medium"
