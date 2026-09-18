"""Sous-routeur Entraînement : ping + catalogue d'exercices (#505)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.api.entrainement.schemas import ExerciceCreate, ExerciceRead, ExerciceUpdate
from app.core.db import get_session
from app.services.entrainement import create_exercice, ensure_catalogue, list_exercices
from app.services.entrainement.exercises import (
    delete_exercice as _delete_exercice,
    update_exercice as _update_exercice,
)

router = APIRouter()


@router.get("/ping")
def ping() -> dict:
    return {"module": "entrainement", "ready": True}


@router.get("/exercises", response_model=list[ExerciceRead])
def list_exercises_endpoint(categorie: Optional[str] = Query(None), session: Session = Depends(get_session)):
    ensure_catalogue(session)
    return [ExerciceRead.model_validate(e) for e in list_exercices(session, categorie)]


@router.post("/exercises", response_model=ExerciceRead, status_code=status.HTTP_201_CREATED)
def create_exercise(payload: ExerciceCreate, session: Session = Depends(get_session)):
    e = create_exercice(
        session, nom=payload.nom, categorie=payload.categorie, muscles=payload.muscles,
        type_mouvement=payload.type_mouvement, unilateral=payload.unilateral,
        source=payload.source, note=payload.note,
    )
    return ExerciceRead.model_validate(e)


@router.patch("/exercises/{exercice_id}", response_model=ExerciceRead)
def patch_exercise(exercice_id: int, payload: ExerciceUpdate, session: Session = Depends(get_session)):
    e = _update_exercice(session, exercice_id, **payload.model_dump(exclude_unset=True))
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "exercice introuvable")
    return ExerciceRead.model_validate(e)


@router.delete("/exercises/{exercice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exercise(exercice_id: int, session: Session = Depends(get_session)):
    if not _delete_exercice(session, exercice_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "exercice introuvable")
