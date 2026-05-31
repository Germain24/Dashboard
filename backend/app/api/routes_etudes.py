"""Router FastAPI — module Études (CONV 6).

Endpoints :
  GET  /etudes/ping
  GET  /etudes/cours
  POST /etudes/cours
  GET  /etudes/cours/{id}
  PATCH /etudes/cours/{id}
  DELETE /etudes/cours/{id}
  GET  /etudes/cours/{id}/evaluations
  POST /etudes/evaluations
  GET  /etudes/evaluations/{id}
  PATCH /etudes/evaluations/{id}
  DELETE /etudes/evaluations/{id}
  GET  /etudes/deadlines
  GET  /etudes/gpa
  GET  /etudes/sessions
  POST /etudes/sessions
  PATCH /etudes/sessions/{id}
  DELETE /etudes/sessions/{id}
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.schemas_etudes import (
    CoursCreate,
    CoursPatch,
    CoursRead,
    EvaluationCreate,
    EvaluationPatch,
    EvaluationRead,
    GpaRead,
    SessionCreate,
    SessionPatch,
    SessionRead,
)
from app.core.db import get_session
from app.services.etudes import constants as cst
from app.services.etudes import courses, evaluations, grades, sessions

router = APIRouter()


# ───────────────────────────── Ping ──────────────────────────────

@router.get("/ping")
def ping() -> dict:
    return {"module": "etudes", "ready": True}


# ───────────────────────────── Cours ─────────────────────────────

def _enrich_cours(c, db) -> CoursRead:
    """Injecte lettre, points GPA et total minutes dans le schema."""
    r = CoursRead.model_validate(c)
    if c.note_finale is not None:
        r.lettre = cst.note_to_lettre(c.note_finale)
        r.points_gpa = cst.note_to_gpa(c.note_finale)
    r.total_minutes_etude = sessions.total_minutes_par_cours(db, c.id)
    return r


@router.get("/cours", response_model=list[CoursRead])
def get_cours_list(
    semestre: Optional[str] = Query(None),
    actif: Optional[bool] = Query(None),
    db=Depends(get_session),
):
    cours_list = courses.list_cours(db, semestre=semestre, actif=actif)
    return [_enrich_cours(c, db) for c in cours_list]


@router.post("/cours", response_model=CoursRead, status_code=201)
def create_cours(body: CoursCreate, db=Depends(get_session)):
    c = courses.create_cours(db, body.model_dump())
    return _enrich_cours(c, db)


@router.get("/cours/{cours_id}", response_model=CoursRead)
def get_one_cours(cours_id: int, db=Depends(get_session)):
    c = courses.get_cours(db, cours_id)
    if c is None:
        raise HTTPException(404, "Cours introuvable")
    return _enrich_cours(c, db)


@router.patch("/cours/{cours_id}", response_model=CoursRead)
def patch_cours(cours_id: int, body: CoursPatch, db=Depends(get_session)):
    c = courses.update_cours(db, cours_id, body.model_dump(exclude_none=True))
    if c is None:
        raise HTTPException(404, "Cours introuvable")
    return _enrich_cours(c, db)


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
        _enrich_eval(ev)
        for ev in evaluations.list_evaluations(db, cours_id=cours_id, upcoming_only=upcoming_only)
    ]


# ───────────────────────────── Evaluations ───────────────────────

def _enrich_eval(ev) -> EvaluationRead:
    r = EvaluationRead.model_validate(ev)
    if ev.date_limite is not None:
        r.jours_restants = (ev.date_limite - dt.date.today()).days
    return r


@router.post("/evaluations", response_model=EvaluationRead, status_code=201)
def create_eval(body: EvaluationCreate, db=Depends(get_session)):
    if courses.get_cours(db, body.cours_id) is None:
        raise HTTPException(404, "Cours introuvable")
    ev = evaluations.create_evaluation(db, body.model_dump())
    return _enrich_eval(ev)


@router.get("/evaluations/{eval_id}", response_model=EvaluationRead)
def get_one_eval(eval_id: int, db=Depends(get_session)):
    ev = evaluations.get_evaluation(db, eval_id)
    if ev is None:
        raise HTTPException(404, "Évaluation introuvable")
    return _enrich_eval(ev)


@router.patch("/evaluations/{eval_id}", response_model=EvaluationRead)
def patch_eval(eval_id: int, body: EvaluationPatch, db=Depends(get_session)):
    ev = evaluations.update_evaluation(db, eval_id, body.model_dump(exclude_none=True))
    if ev is None:
        raise HTTPException(404, "Évaluation introuvable")
    return _enrich_eval(ev)


@router.delete("/evaluations/{eval_id}", status_code=204)
def delete_eval(eval_id: int, db=Depends(get_session)):
    if not evaluations.delete_evaluation(db, eval_id):
        raise HTTPException(404, "Évaluation introuvable")


# ───────────────────────────── Deadlines ─────────────────────────

@router.get("/deadlines", response_model=list[EvaluationRead])
def get_deadlines(
    days: int = Query(30, description="Horizon en jours"),
    db=Depends(get_session),
):
    """Évaluations à venir dans les N prochains jours."""
    horizon = dt.date.today() + dt.timedelta(days=days)
    evs = evaluations.list_evaluations(db, upcoming_only=True)
    evs = [ev for ev in evs if ev.date_limite is not None and ev.date_limite <= horizon]
    return [_enrich_eval(ev) for ev in evs]


# ───────────────────────────── GPA ───────────────────────────────

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

    from app.api.schemas_etudes import CoursGradeRead
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


# ───────────────────────────── Sessions ──────────────────────────

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
