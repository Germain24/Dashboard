"""Sous-routeur Livres : stats, recommandations, objectif annuel (#510)."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.livres.schemas import GoalUpdate
from app.core.db import get_session
from app.services.livres import analytics as analytics_svc
from app.services.livres import books as books_svc
from app.services.livres import goals as goals_svc

router = APIRouter()


@router.get("/stats")
def stats(session: Session = Depends(get_session)):
    return books_svc.get_stats(session)


@router.get("/stats/annual")
def annual_stats(year: int | None = None, session: Session = Depends(get_session)):
    """Stats annuelles + challenge lecture (#146/#151)."""
    y = year or dt.date.today().year
    data = analytics_svc.annual_stats(session, y)
    goal = goals_svc.get_annual_goal()
    data["challenge"] = goals_svc.goal_progress(data["livres_lus"], goal)
    return data


@router.get("/recommendations")
def recommendations(limit: int = 5, session: Session = Depends(get_session)):
    """Recommandations basées sur les genres lus (#149)."""
    return analytics_svc.recommend_books(session, limit)


@router.get("/reading-goal")
def get_reading_goal():
    """Objectif annuel de lecture (#151)."""
    return {"annual_goal": goals_svc.get_annual_goal()}


@router.post("/reading-goal")
def set_reading_goal(body: GoalUpdate):
    try:
        goal = goals_svc.set_annual_goal(body.annual_goal)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"annual_goal": goal}
