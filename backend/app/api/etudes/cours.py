"""Sous-routeur Études : ping + cours (#506)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.etudes.common import enrich_cours, enrich_eval
from app.api.etudes.schemas import CoursCreate, CoursPatch, CoursRead, EvaluationRead
from app.core.db import get_session
from app.services.etudes import courses, evaluations

router = APIRouter()


@router.get("/ping")
def ping() -> dict:
    return {"module": "etudes", "ready": True}


@router.get("/cours", response_model=list[CoursRead])
def get_cours_list(
    semestre: Optional[str] = Query(None),
    actif: Optional[bool] = Query(None),
    db=Depends(get_session),
):
    cours_list = courses.list_cours(db, semestre=semestre, actif=actif)
    return [enrich_cours(c, db) for c in cours_list]


@router.post("/cours", response_model=CoursRead, status_code=201)
def create_cours(body: CoursCreate, db=Depends(get_session)):
    c = courses.create_cours(db, body.model_dump())
    return enrich_cours(c, db)


@router.get("/cours/{cours_id}", response_model=CoursRead)
def get_one_cours(cours_id: int, db=Depends(get_session)):
    c = courses.get_cours(db, cours_id)
    if c is None:
        raise HTTPException(404, "Cours introuvable")
    return enrich_cours(c, db)


@router.patch("/cours/{cours_id}", response_model=CoursRead)
def patch_cours(cours_id: int, body: CoursPatch, db=Depends(get_session)):
    c = courses.update_cours(db, cours_id, body.model_dump(exclude_none=True))
    if c is None:
        raise HTTPException(404, "Cours introuvable")
    return enrich_cours(c, db)


@router.delete("/cours/{cours_id}", status_code=204)
def delete_cours(cours_id: int, db=Depends(get_session)):
    if not courses.delete_cours(db, cours_id):
        raise HTTPException(404, "Cours introuvable")


@router.get("/cours/{cours_id}/evaluations", response_model=list[EvaluationRead])
def get_evals_for_cours(
    cours_id: int,
    upcoming_only: bool = Query(False),
    db=Depends(get_session),
):
    return [
        enrich_eval(ev)
        for ev in evaluations.list_evaluations(db, cours_id=cours_id, upcoming_only=upcoming_only)
    ]
