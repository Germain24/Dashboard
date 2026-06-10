"""Sous-routeur Études : évaluations, deadlines, GPA (#506)."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.etudes.common import enrich_eval
from app.api.etudes.schemas import (
    CoursGradeRead,
    EvaluationCreate,
    EvaluationPatch,
    EvaluationRead,
    GpaRead,
)
from app.core.db import get_session
from app.services.etudes import courses, evaluations, grades

router = APIRouter()


@router.post("/evaluations", response_model=EvaluationRead, status_code=201)
def create_eval(body: EvaluationCreate, db=Depends(get_session)):
    if courses.get_cours(db, body.cours_id) is None:
        raise HTTPException(404, "Cours introuvable")
    ev = evaluations.create_evaluation(db, body.model_dump())
    return enrich_eval(ev)


@router.get("/evaluations/{eval_id}", response_model=EvaluationRead)
def get_one_eval(eval_id: int, db=Depends(get_session)):
    ev = evaluations.get_evaluation(db, eval_id)
    if ev is None:
        raise HTTPException(404, "Évaluation introuvable")
    return enrich_eval(ev)


@router.patch("/evaluations/{eval_id}", response_model=EvaluationRead)
def patch_eval(eval_id: int, body: EvaluationPatch, db=Depends(get_session)):
    ev = evaluations.update_evaluation(db, eval_id, body.model_dump(exclude_none=True))
    if ev is None:
        raise HTTPException(404, "Évaluation introuvable")
    return enrich_eval(ev)


@router.delete("/evaluations/{eval_id}", status_code=204)
def delete_eval(eval_id: int, db=Depends(get_session)):
    if not evaluations.delete_evaluation(db, eval_id):
        raise HTTPException(404, "Évaluation introuvable")


@router.get("/deadlines", response_model=list[EvaluationRead])
def get_deadlines(
    days: int = Query(30, description="Horizon en jours"),
    db=Depends(get_session),
):
    """Évaluations à venir dans les N prochains jours."""
    horizon = dt.date.today() + dt.timedelta(days=days)
    evs = evaluations.list_evaluations(db, upcoming_only=True)
    evs = [ev for ev in evs if ev.date_limite is not None and ev.date_limite <= horizon]
    return [enrich_eval(ev) for ev in evs]


@router.get("/gpa", response_model=GpaRead)
def get_gpa(
    semestre: Optional[str] = Query(None),
    db=Depends(get_session),
):
    """GPA semestriel (si semestre fourni) ou cumulatif."""
    cours_list = courses.list_cours(db)
    dicts = [
        {
            "id": c.id,
            "code": c.code,
            "nom": c.nom,
            "semestre": c.semestre,
            "note_finale": c.note_finale,
        }
        for c in cours_list
    ]

    if semestre:
        result = grades.gpa_pour_semestre(dicts, semestre)
    else:
        result = grades.gpa_cumulatif(dicts)

    return GpaRead(
        semestre=result.semestre,
        nb_cours=result.nb_cours,
        nb_cours_notes=result.nb_cours_notes,
        gpa=result.gpa,
        detail=[
            CoursGradeRead(
                cours_id=cg.cours_id,
                code=cg.code,
                nom=cg.nom,
                semestre=cg.semestre,
                note_finale=cg.note_finale,
                lettre=cg.lettre,
                points_gpa=cg.points_gpa,
            )
            for cg in result.detail
        ],
    )
