"""Sous-routeur Santé : score de forme quotidien (sommeil + sport + nutrition)."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.core.db import get_session

router = APIRouter()


@router.get("/score")
def get_score(date: dt.date | None = Query(None), session: Session = Depends(get_session)):
    """Score du jour + composantes (sommeil, sport, nutrition) + valeurs brutes."""
    from app.services.sante.score import compute_score
    return compute_score(session, date or dt.date.today())


@router.get("/score/history")
def get_score_history(days: int = Query(90, ge=2, le=365), session: Session = Depends(get_session)):
    """Série du score sur les `days` derniers jours (pour la courbe)."""
    from app.services.sante.score import score_history
    return {"days": days, "points": score_history(session, days=days)}
