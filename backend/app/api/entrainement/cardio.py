"""Sous-routeur Entraînement : courses cardio (#505)."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.api.entrainement.schemas import CourseCardioCreate, CourseCardioRead
from app.core.db import get_session
from app.services.entrainement import cardio, create_course, list_courses, pace_sec_per_km

router = APIRouter()


def _course_to_read(c) -> CourseCardioRead:
    return CourseCardioRead(
        id=c.id, date=c.date, distance_km=c.distance_km, duree_sec=c.duree_sec,
        pace_sec_per_km=pace_sec_per_km(c.distance_km, c.duree_sec),
        pace_str=cardio.format_pace(c.distance_km, c.duree_sec),
        note=c.note, source=c.source,
    )


@router.get("/cardio", response_model=list[CourseCardioRead])
def list_cardio(
    date_from: Optional[dt.date] = Query(None, alias="from"),
    date_to: Optional[dt.date] = Query(None, alias="to"),
    session: Session = Depends(get_session),
):
    return [_course_to_read(c) for c in list_courses(session, date_from=date_from, date_to=date_to)]


@router.post("/cardio", response_model=CourseCardioRead, status_code=status.HTTP_201_CREATED)
def post_cardio(payload: CourseCardioCreate, session: Session = Depends(get_session)):
    c = create_course(
        session, date=payload.date, distance_km=payload.distance_km,
        duree_sec=payload.duree_sec, note=payload.note, source=payload.source,
    )
    return _course_to_read(c)


@router.delete("/cardio/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cardio(course_id: int, session: Session = Depends(get_session)):
    if not cardio.delete_course(session, course_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "course introuvable")
