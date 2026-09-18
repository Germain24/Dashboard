"""Module Cardio — course à pied V1.

Décision CONV 7 : course à pied uniquement, on note distance + temps.
Le pace est dérivé (sec/km). `source` permet d'accepter plus tard les
imports Garmin sans casser l'API.
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlmodel import Session, select

from app.models.entrainement import CourseCardio


def list_courses(
    session: Session,
    *,
    date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None,
) -> list[CourseCardio]:
    stmt = select(CourseCardio)
    if date_from:
        stmt = stmt.where(CourseCardio.date >= date_from)
    if date_to:
        stmt = stmt.where(CourseCardio.date <= date_to)
    stmt = stmt.order_by(CourseCardio.date.desc(), CourseCardio.id.desc())
    return list(session.exec(stmt).all())


def get_course(session: Session, course_id: int) -> Optional[CourseCardio]:
    return session.get(CourseCardio, course_id)


def create_course(
    session: Session,
    *,
    date: dt.date,
    distance_km: float,
    duree_sec: int,
    note: Optional[str] = None,
    source: str = "manual",
) -> CourseCardio:
    c = CourseCardio(
        date=date,
        distance_km=float(distance_km),
        duree_sec=int(duree_sec),
        note=note,
        source=source,
    )
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def delete_course(session: Session, course_id: int) -> bool:
    c = get_course(session, course_id)
    if c is None:
        return False
    session.delete(c)
    session.commit()
    return True


def pace_sec_per_km(distance_km: float, duree_sec: int) -> Optional[float]:
    """Allure en secondes par km. None si distance invalide."""
    if not distance_km or distance_km <= 0:
        return None
    return round(duree_sec / distance_km, 2)


def format_pace(distance_km: float, duree_sec: int) -> Optional[str]:
    """Allure formattée mm:ss/km."""
    p = pace_sec_per_km(distance_km, duree_sec)
    if p is None:
        return None
    minutes = int(p // 60)
    seconds = int(round(p - minutes * 60))
    if seconds == 60:
        minutes += 1
        seconds = 0
    return f"{minutes}:{seconds:02d}/km"


def get_courses_for_date(session: Session, date: dt.date) -> list[CourseCardio]:
    return list(
        session.exec(
            select(CourseCardio).where(CourseCardio.date == date)
        ).all()
    )
