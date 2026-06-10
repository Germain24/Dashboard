"""Sous-routeur Études : sessions d'étude, stats, objectif hebdo (#506)."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.etudes.schemas import SessionCreate, SessionPatch, SessionRead
from app.core.db import get_session
from app.services.etudes import courses, sessions

router = APIRouter()


@router.get("/sessions", response_model=list[SessionRead])
def get_sessions_list(
    cours_id: Optional[int] = Query(None),
    date_from: Optional[dt.date] = Query(None),
    date_to: Optional[dt.date] = Query(None),
    db=Depends(get_session),
):
    return sessions.list_sessions(db, cours_id=cours_id, date_from=date_from, date_to=date_to)


@router.post("/sessions", response_model=SessionRead, status_code=201)
def create_session(body: SessionCreate, db=Depends(get_session)):
    data = body.model_dump()
    if data.get("date") is None:
        data["date"] = dt.date.today()
    return sessions.create_session(db, data)


@router.patch("/sessions/{session_id}", response_model=SessionRead)
def patch_session(session_id: int, body: SessionPatch, db=Depends(get_session)):
    se = sessions.update_session(db, session_id, body.model_dump(exclude_none=True))
    if se is None:
        raise HTTPException(404, "Session introuvable")
    return se


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: int, db=Depends(get_session)):
    if not sessions.delete_session(db, session_id):
        raise HTTPException(404, "Session introuvable")


@router.get("/stats")
def get_stats(days: int = Query(120, ge=7, le=400), db=Depends(get_session)):
    """Analytics d'étude : temps/matière (#94), heatmap (#97), streak (#101),
    rapport hebdo (#102), objectif hebdo + progression (#95)."""
    from app.services.etudes import stats as st
    from app.services.etudes.goals import get_weekly_hours

    cutoff = dt.date.today() - dt.timedelta(days=days)
    rows = sessions.list_sessions(db, date_from=cutoff)
    norm = [{"date": s.date, "duree_min": s.duree_min, "cours_id": s.cours_id} for s in rows]
    labels = {c.id: c.code for c in courses.list_cours(db)}

    weekly_hours = get_weekly_hours()
    weekly = st.weekly_summary(norm, labels)
    progress_pct = round(min(100.0, (weekly["total_minutes"] / 60.0) / weekly_hours * 100), 1) if weekly_hours else 0.0

    return {
        "days": days,
        "by_course": st.minutes_by_course(norm, labels),
        "daily": st.daily_minutes(norm),
        "streak": st.study_streak([s.date for s in rows]),
        "weekly": weekly,
        "goal": {
            "weekly_hours": weekly_hours,
            "done_hours": round(weekly["total_minutes"] / 60.0, 1),
            "progress_pct": progress_pct,
        },
    }


@router.put("/goal")
def set_goal(weekly_hours: float = Query(..., ge=0, le=168)):
    """Définit l'objectif d'heures d'étude par semaine (#95)."""
    from app.services.etudes.goals import set_weekly_hours
    return {"weekly_hours": set_weekly_hours(weekly_hours)}
