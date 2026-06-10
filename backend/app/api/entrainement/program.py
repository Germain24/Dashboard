"""Sous-routeur Entraînement : programme hebdo + seed Garmin (#505)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.entrainement.schemas import (
    GarminSeedRequest,
    GarminSeedResponse,
    ProgrammeJourRead,
    ProgrammeJourUpdate,
    ProgrammeRead,
    ProgrammeUpdate,
)
from app.core.db import get_session
from app.services.entrainement import (
    ensure_active_program,
    list_program_days,
    update_program_day,
)
from app.services.entrainement.garmin_seed import seed_garmin_programs
from app.services.entrainement.programs import update_program as _update_program

router = APIRouter()


def _program_to_read(prog, jours) -> ProgrammeRead:
    return ProgrammeRead(
        id=prog.id, nom=prog.nom, description=prog.description, actif=prog.actif,
        jours=[ProgrammeJourRead.model_validate(j) for j in jours],
    )


@router.get("/program", response_model=ProgrammeRead)
def get_program(session: Session = Depends(get_session)):
    prog = ensure_active_program(session)
    return _program_to_read(prog, list_program_days(session, prog.id))


@router.patch("/program", response_model=ProgrammeRead)
def patch_program(payload: ProgrammeUpdate, session: Session = Depends(get_session)):
    prog = ensure_active_program(session)
    _update_program(session, prog.id, **payload.model_dump(exclude_unset=True))
    return _program_to_read(prog, list_program_days(session, prog.id))


@router.patch("/program/jours/{weekday}", response_model=ProgrammeJourRead)
def patch_program_day(weekday: int, payload: ProgrammeJourUpdate, session: Session = Depends(get_session)):
    if weekday < 0 or weekday > 6:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "weekday doit être 0..6")
    prog = ensure_active_program(session)
    pj = update_program_day(session, prog.id, weekday, label=payload.label, slots=payload.slots)
    if pj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "jour introuvable")
    return ProgrammeJourRead.model_validate(pj)


@router.post("/program/seed-garmin", response_model=GarminSeedResponse)
def seed_garmin(
    payload: GarminSeedRequest = GarminSeedRequest(),
    session: Session = Depends(get_session),
):
    """Peuple le programme actif avec les 4 séances Garmin de Germain.

    Idempotent : par défaut, n'écrase pas les jours déjà configurés.
    Passe `force=true` pour réinitialiser depuis le dump Garmin.

    Note : samedi (Lower) reste à définir — pas dans le dump Garmin partagé.
    """
    return seed_garmin_programs(session, force=payload.force)
