"""Sous-routeur Santé : mesures corporelles, photos de progression, projection (#504)."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlmodel import Session, select

from app.api.sante.schemas import (
    MesureSanteCreate,
    MesureSanteRead,
    MesureSanteUpdate,
    ProjectionResponse,
    WeightTrendOut,
)
from app.core.db import get_session
from app.models.sante import MesureSante
from app.services.sante import ensure_active_goal, project_weight_to_target

router = APIRouter()


@router.get("/ping")
def ping() -> dict:
    return {"module": "sante", "ready": True}


@router.get("/mesures", response_model=list[MesureSanteRead])
def list_mesures(days: int = Query(180, ge=1, le=3650), session: Session = Depends(get_session)):
    cutoff = dt.date.today() - dt.timedelta(days=days)
    stmt = select(MesureSante).where(MesureSante.date >= cutoff).order_by(MesureSante.date.asc())
    return [MesureSanteRead.model_validate(m) for m in session.exec(stmt).all()]


@router.post("/mesures", response_model=MesureSanteRead, status_code=status.HTTP_201_CREATED)
def upsert_mesure(payload: MesureSanteCreate, session: Session = Depends(get_session)):
    existing = session.exec(select(MesureSante).where(MesureSante.date == payload.date)).first()
    if existing:
        if payload.poids is not None:
            existing.poids = payload.poids
        if payload.photo_url is not None:
            existing.photo_url = payload.photo_url
        if payload.note is not None:
            existing.note = payload.note
        if payload.extra is not None:
            existing.extra = payload.extra
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return MesureSanteRead.model_validate(existing)
    m = MesureSante(**payload.model_dump())
    session.add(m)
    session.commit()
    session.refresh(m)
    return MesureSanteRead.model_validate(m)


@router.patch("/mesures/{date}", response_model=MesureSanteRead)
def update_mesure(date: dt.date, payload: MesureSanteUpdate, session: Session = Depends(get_session)):
    existing = session.exec(select(MesureSante).where(MesureSante.date == date)).first()
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"mesure du {date} introuvable")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(existing, k, v)
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return MesureSanteRead.model_validate(existing)


@router.delete("/mesures/{date}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mesure(date: dt.date, session: Session = Depends(get_session)):
    existing = session.exec(select(MesureSante).where(MesureSante.date == date)).first()
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"mesure du {date} introuvable")
    session.delete(existing)
    session.commit()


@router.post("/photo", response_model=MesureSanteRead)
async def upload_progress_photo(
    file: UploadFile = File(...),
    date: dt.date | None = None,
    session: Session = Depends(get_session),
):
    """Téléverse une photo de progression pour une date (#69)."""
    from app.services.sante.photos import save_progress_photo

    content = await file.read()
    try:
        m = save_progress_photo(session, date or dt.date.today(), file.filename or "photo.jpg", content)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return MesureSanteRead.model_validate(m)


@router.get("/photos")
def list_photos(session: Session = Depends(get_session)):
    """Liste les mesures avec photo, triées par date (avant/après, #69)."""
    from app.services.sante.photos import list_progress_photos
    return list_progress_photos(session)


@router.get("/projection", response_model=ProjectionResponse)
def get_projection(
    target_weight: Optional[float] = Query(None),
    session: Session = Depends(get_session),
):
    goal = ensure_active_goal(session)
    if target_weight is None:
        target_weight = goal.poids_cible
    if target_weight is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Aucun poids cible defini.")
    rows = session.exec(
        select(MesureSante).where(MesureSante.poids.isnot(None)).order_by(MesureSante.date.asc())
    ).all()
    measures = [(m.date, float(m.poids)) for m in rows if m.poids is not None]
    result = project_weight_to_target(measures, target_weight)
    if result is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Aucune mesure de poids disponible.")
    return ProjectionResponse(
        target_weight=result.target_weight,
        current_weight=result.current_weight,
        delta_kg=result.delta_kg,
        days_to_target=result.days_to_target,
        target_date=result.target_date,
        slope_kg_per_week=result.slope_kg_per_week,
        confidence=result.confidence,
        note=result.note,
        trend_7d=WeightTrendOut(**vars(result.trend_7d)) if result.trend_7d else None,
        trend_30d=WeightTrendOut(**vars(result.trend_30d)) if result.trend_30d else None,
    )
