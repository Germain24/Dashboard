"""Sous-routeur Agenda : tâches (#502)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from app.api.agenda.common import SessionDep
from app.api.agenda.schemas import TacheCreate, TacheRead, TacheUpdate
from app.services.agenda import (
    create_task,
    delete_task,
    list_tasks,
    mark_done,
    update_task,
)

router = APIRouter()


@router.get("/tasks", response_model=list[TacheRead])
def list_taches(
    session: SessionDep,
    statut: Optional[str] = None,
    categorie: Optional[str] = None,
):
    return [TacheRead.model_validate(t) for t in list_tasks(session, statut, categorie)]


@router.post("/tasks", response_model=TacheRead, status_code=201)
def create_tache(payload: TacheCreate, session: SessionDep):
    t = create_task(session, payload.model_dump())
    return TacheRead.model_validate(t)


@router.patch("/tasks/{task_id}", response_model=TacheRead)
def update_tache(task_id: int, payload: TacheUpdate, session: SessionDep):
    t = update_task(session, task_id, payload.model_dump(exclude_none=True))
    if t is None:
        raise HTTPException(404, "Tâche introuvable")
    return TacheRead.model_validate(t)


@router.post("/tasks/{task_id}/done", response_model=TacheRead)
def done_tache(task_id: int, session: SessionDep):
    t = mark_done(session, task_id)
    if t is None:
        raise HTTPException(404, "Tâche introuvable")
    return TacheRead.model_validate(t)


@router.delete("/tasks/{task_id}", status_code=204)
def delete_tache(task_id: int, session: SessionDep):
    if not delete_task(session, task_id):
        raise HTTPException(404, "Tâche introuvable")
