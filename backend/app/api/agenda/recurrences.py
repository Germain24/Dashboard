"""Sous-routeur Agenda : règles de récurrence (#502)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.agenda.common import SessionDep
from app.api.agenda.schemas import (
    RegleRecurrenceCreate,
    RegleRecurrenceRead,
    RegleRecurrenceUpdate,
)
from app.services.agenda import (
    create_recurrence_rule,
    delete_recurrence_rule,
    list_recurrence_rules,
    update_recurrence_rule,
)

router = APIRouter()


@router.get("/recurrences", response_model=list[RegleRecurrenceRead])
def list_rules(session: SessionDep):
    return [RegleRecurrenceRead.model_validate(r) for r in list_recurrence_rules(session)]


@router.post("/recurrences", response_model=RegleRecurrenceRead, status_code=201)
def create_rule(payload: RegleRecurrenceCreate, session: SessionDep):
    rule = create_recurrence_rule(session, payload.model_dump())
    return RegleRecurrenceRead.model_validate(rule)


@router.patch("/recurrences/{rule_id}", response_model=RegleRecurrenceRead)
def update_rule(rule_id: int, payload: RegleRecurrenceUpdate, session: SessionDep):
    rule = update_recurrence_rule(session, rule_id, payload.model_dump(exclude_none=True))
    if rule is None:
        raise HTTPException(404, "Règle introuvable")
    return RegleRecurrenceRead.model_validate(rule)


@router.delete("/recurrences/{rule_id}", status_code=204)
def delete_rule(rule_id: int, session: SessionDep):
    if not delete_recurrence_rule(session, rule_id):
        raise HTTPException(404, "Règle introuvable")
