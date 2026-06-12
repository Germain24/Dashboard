"""Routes Routines (#201)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.core.db import get_session
from app.services.automatisations.engine import (
    create_routine,
    delete_routine,
    execute_routine,
    get_routine,
    get_routines,
    update_routine,
)

router = APIRouter()


class RoutineCreate(BaseModel):
    name: str
    description: str = ""
    trigger_type: str = "cron"
    trigger_value: str = ""
    actions: list[dict] = []
    enabled: bool = True


class RoutinePatch(BaseModel):
    name: str | None = None
    description: str | None = None
    trigger_type: str | None = None
    trigger_value: str | None = None
    actions: list[dict] | None = None
    enabled: bool | None = None


def _out(r) -> dict:
    import json
    d = r.model_dump()
    d["actions"] = json.loads(r.actions)
    return d


@router.get("/routines")
def list_routines(session: Session = Depends(get_session)):
    return [_out(r) for r in get_routines(session)]


@router.post("/routines", status_code=201)
def add_routine(body: RoutineCreate, session: Session = Depends(get_session)):
    r = create_routine(session, **body.model_dump())
    return _out(r)


@router.patch("/routines/{routine_id}")
def patch_routine(routine_id: int, body: RoutinePatch, session: Session = Depends(get_session)):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    r = update_routine(session, routine_id, patch)
    if not r:
        raise HTTPException(404)
    return _out(r)


@router.delete("/routines/{routine_id}", status_code=204)
def remove_routine(routine_id: int, session: Session = Depends(get_session)):
    if not delete_routine(session, routine_id):
        raise HTTPException(404)


@router.post("/routines/{routine_id}/run")
def run_routine(routine_id: int, session: Session = Depends(get_session)):
    r = get_routine(session, routine_id)
    if not r:
        raise HTTPException(404)
    result = execute_routine(session, routine_id)
    return {"result": result}
