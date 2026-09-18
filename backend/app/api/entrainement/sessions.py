"""Sous-routeur Entraînement : séances + séries (#505)."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.api.entrainement.common import seance_to_read
from app.api.entrainement.schemas import (
    SeanceCreate,
    SeanceRead,
    SeanceUpdate,
    SetSerieCreate,
    SetSerieRead,
    SetSerieUpdate,
)
from app.core.db import get_session
from app.services.entrainement import (
    add_set,
    create_session,
    delete_session,
    delete_set,
    list_sessions,
    list_sets_for_seance,
)
from app.services.entrainement.sessions import (
    get_session_row,
    update_session as _update_session,
)
from app.services.entrainement.sets import update_set as _update_set

router = APIRouter()


@router.get("/sessions", response_model=list[SeanceRead])
def list_sessions_endpoint(
    date_from: Optional[dt.date] = Query(None, alias="from"),
    date_to: Optional[dt.date] = Query(None, alias="to"),
    session: Session = Depends(get_session),
):
    rows = list_sessions(session, date_from=date_from, date_to=date_to)
    return [seance_to_read(s, list_sets_for_seance(session, s.id)) for s in rows]


@router.post("/sessions", response_model=SeanceRead, status_code=status.HTTP_201_CREATED)
def create_session_endpoint(payload: SeanceCreate, session: Session = Depends(get_session)):
    s = create_session(
        session, date=payload.date, type=payload.type, duree_min=payload.duree_min,
        note=payload.note, programme_jour_id=payload.programme_jour_id,
        intensite=payload.intensite, source=payload.source,
    )
    for sp in payload.sets:
        add_set(
            session, seance_id=s.id, exercice_id=sp.exercice_id, reps=sp.reps,
            poids_kg=sp.poids_kg, rpe=sp.rpe, echec=sp.echec, ordre=sp.ordre,
        )
    return seance_to_read(s, list_sets_for_seance(session, s.id))


@router.get("/sessions/{seance_id}", response_model=SeanceRead)
def get_session_endpoint(seance_id: int, session: Session = Depends(get_session)):
    s = get_session_row(session, seance_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "séance introuvable")
    return seance_to_read(s, list_sets_for_seance(session, s.id))


@router.patch("/sessions/{seance_id}", response_model=SeanceRead)
def patch_session_endpoint(seance_id: int, payload: SeanceUpdate, session: Session = Depends(get_session)):
    s = _update_session(session, seance_id, **payload.model_dump(exclude_unset=True))
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "séance introuvable")
    return seance_to_read(s, list_sets_for_seance(session, s.id))


@router.delete("/sessions/{seance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session_endpoint(seance_id: int, session: Session = Depends(get_session)):
    if not delete_session(session, seance_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "séance introuvable")


@router.post("/sessions/{seance_id}/sets", response_model=SetSerieRead, status_code=status.HTTP_201_CREATED)
def add_set_endpoint(seance_id: int, payload: SetSerieCreate, session: Session = Depends(get_session)):
    if get_session_row(session, seance_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "séance introuvable")
    s = add_set(
        session, seance_id=seance_id, exercice_id=payload.exercice_id,
        reps=payload.reps, poids_kg=payload.poids_kg, rpe=payload.rpe,
        echec=payload.echec, ordre=payload.ordre,
    )
    return SetSerieRead.model_validate(s)


@router.patch("/sessions/{seance_id}/sets/{set_id}", response_model=SetSerieRead)
def patch_set_endpoint(seance_id: int, set_id: int, payload: SetSerieUpdate, session: Session = Depends(get_session)):
    s = _update_set(session, set_id, **payload.model_dump(exclude_unset=True))
    if s is None or s.seance_id != seance_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "série introuvable")
    return SetSerieRead.model_validate(s)


@router.delete("/sessions/{seance_id}/sets/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_set_endpoint(seance_id: int, set_id: int, session: Session = Depends(get_session)):
    if not delete_set(session, set_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "série introuvable")
