"""Sous-routeur Entraînement : progression, 1RM, volume, corrélation, mésocycle (#505)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.api.entrainement.schemas import (
    CorrelationResponse,
    MesocycleResponse,
    MuscleVolumeOut,
    OneRMResponse,
    ProgressionPointOut,
    ProgressionResponse,
    WeekPointOut,
)
from app.core.db import get_session
from app.services.entrainement import (
    current_1rm,
    mesocycle,
    progression_for_exercice,
    training_weight_correlation,
    weekly_muscle_volume,
)
from app.services.entrainement.exercises import get_exercice

router = APIRouter()


@router.get("/progression/{exercice_id}", response_model=ProgressionResponse)
def get_progression(exercice_id: int, days: int = Query(90, ge=1, le=3650), session: Session = Depends(get_session)):
    e = get_exercice(session, exercice_id)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "exercice introuvable")
    summary = progression_for_exercice(session, exercice_id, days=days)
    return ProgressionResponse(
        exercice_id=exercice_id, nom=e.nom,
        points=[ProgressionPointOut(**vars(p)) for p in summary.points],
        current_1rm_kg=summary.current_1rm_kg, best_1rm_kg=summary.best_1rm_kg,
        delta_4w_pct=summary.delta_4w_pct,
    )


@router.get("/1rm/{exercice_id}", response_model=OneRMResponse)
def get_one_rm(exercice_id: int, session: Session = Depends(get_session)):
    e = get_exercice(session, exercice_id)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "exercice introuvable")
    return OneRMResponse(exercice_id=exercice_id, nom=e.nom, current_1rm_kg=current_1rm(session, exercice_id))


@router.get("/volume/muscles", response_model=list[MuscleVolumeOut])
def get_muscle_volume(days: int = Query(7, ge=1, le=90), session: Session = Depends(get_session)):
    """Volume hebdo (séries) par groupe musculaire + statut sous/optimal/sur (#107)."""
    return [MuscleVolumeOut(**vars(mv)) for mv in weekly_muscle_volume(session, days=days)]


@router.get("/correlation", response_model=CorrelationResponse)
def get_correlation(weeks: int = Query(12, ge=4, le=52), session: Session = Depends(get_session)):
    """Corrélation hebdo tonnage d'entraînement ↔ poids (lien Santé, #112)."""
    res = training_weight_correlation(session, weeks=weeks)
    return CorrelationResponse(
        weeks=[WeekPointOut(**vars(w)) for w in res["weeks"]],
        correlation=res["correlation"],
        n=res["n"],
    )


@router.get("/mesocycle", response_model=MesocycleResponse)
def get_mesocycle():
    """État du mésocycle périodisé courant (ou inactif) (#110)."""
    cur = mesocycle.current()
    return MesocycleResponse(**cur) if cur else MesocycleResponse(active=False)


@router.post("/mesocycle/start", response_model=MesocycleResponse)
def start_mesocycle(accumulation_weeks: int = Query(4, ge=2, le=8)):
    """Démarre un mésocycle aujourd'hui (ancré au lundi de la semaine)."""
    mesocycle.start_cycle(accumulation_weeks)
    cur = mesocycle.current()
    return MesocycleResponse(**cur) if cur else MesocycleResponse(active=False)


@router.post("/mesocycle/stop", response_model=MesocycleResponse)
def stop_mesocycle():
    mesocycle.stop_cycle()
    return MesocycleResponse(active=False)
