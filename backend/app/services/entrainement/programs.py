"""Programme hebdomadaire (singleton actif) + helpers."""

from __future__ import annotations

import datetime as dt
import logging
from typing import Optional

from sqlmodel import Session, select

from app.models.entrainement import Programme, ProgrammeJour
from app.services.entrainement.constants import (
    DEFAULT_PROGRAMME_DESCRIPTION,
    DEFAULT_PROGRAMME_NAME,
    DEFAULT_WEEKDAY_LABELS,
)

logger = logging.getLogger(__name__)


def get_active_program(session: Session) -> Optional[Programme]:
    rows = session.exec(
        select(Programme).where(Programme.actif == True).order_by(Programme.id.desc())  # noqa: E712
    ).all()
    if len(rows) > 1:
        logger.warning("Plusieurs Programmes actifs (%d) — on prend le plus récent", len(rows))
    return rows[0] if rows else None


def ensure_active_program(session: Session) -> Programme:
    """Retourne le programme actif. Crée le défaut PPL/UL s'il n'y en a pas."""
    prog = get_active_program(session)
    if prog:
        return prog
    prog = Programme(
        nom=DEFAULT_PROGRAMME_NAME,
        description=DEFAULT_PROGRAMME_DESCRIPTION,
        actif=True,
    )
    session.add(prog)
    session.commit()
    session.refresh(prog)
    # Crée les 7 jours par défaut
    for weekday in range(7):
        pj = ProgrammeJour(
            programme_id=prog.id,
            weekday=weekday,
            label=DEFAULT_WEEKDAY_LABELS[weekday],
            slots=[],
        )
        session.add(pj)
    session.commit()
    return prog


def list_program_days(session: Session, programme_id: int) -> list[ProgrammeJour]:
    return list(
        session.exec(
            select(ProgrammeJour)
            .where(ProgrammeJour.programme_id == programme_id)
            .order_by(ProgrammeJour.weekday)
        ).all()
    )


def get_program_day(
    session: Session,
    programme_id: int,
    weekday: int,
) -> Optional[ProgrammeJour]:
    return session.exec(
        select(ProgrammeJour)
        .where(ProgrammeJour.programme_id == programme_id)
        .where(ProgrammeJour.weekday == weekday)
    ).first()


def update_program_day(
    session: Session,
    programme_id: int,
    weekday: int,
    *,
    label: Optional[str] = None,
    slots: Optional[list[dict]] = None,
) -> Optional[ProgrammeJour]:
    pj = get_program_day(session, programme_id, weekday)
    if pj is None:
        return None
    if label is not None:
        pj.label = label
    if slots is not None:
        pj.slots = slots
    session.add(pj)
    session.commit()
    session.refresh(pj)
    return pj


def update_program(
    session: Session,
    programme_id: int,
    *,
    nom: Optional[str] = None,
    description: Optional[str] = None,
) -> Optional[Programme]:
    prog = session.get(Programme, programme_id)
    if prog is None:
        return None
    if nom is not None:
        prog.nom = nom
    if description is not None:
        prog.description = description
    prog.updated_at = dt.datetime.utcnow()
    session.add(prog)
    session.commit()
    session.refresh(prog)
    return prog


def program_day_for_date(
    session: Session,
    date: dt.date,
    programme_id: Optional[int] = None,
) -> Optional[ProgrammeJour]:
    """Retourne le ProgrammeJour qui correspond au weekday de `date`."""
    prog_id = programme_id
    if prog_id is None:
        prog = get_active_program(session)
        if prog is None:
            return None
        prog_id = prog.id
    return get_program_day(session, prog_id, date.weekday())
