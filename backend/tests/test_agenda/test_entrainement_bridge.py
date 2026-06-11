"""Bloc Entraînement dans l'agenda : une séance planifiée (non loggée) est
flexible — pas d'horaire inventé à 9h, pas de créneau bloqué."""
from __future__ import annotations

import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.services.agenda.entrainement_bridge import get_training_block_for_date
from app.services.entrainement import create_session as create_seance
from app.services.entrainement import ensure_active_program, update_program_day


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_planned_seance_is_flexible(session):
    """Programme planifié sans séance loggée : bloc sans horaire (fin=None, début minuit)."""
    date = dt.date(2026, 6, 10)  # mercredi -> weekday 2
    prog = ensure_active_program(session)
    update_program_day(session, prog.id, date.weekday(), label="Push", slots=[])

    blk = get_training_block_for_date(session, date)

    assert blk is not None
    assert blk["fin"] is None, "une séance non loggée ne doit pas inventer une heure de fin"
    assert blk["debut"].time() == dt.time.min, "pas d'horaire arbitraire (9h)"
    assert "horaire libre" in blk["description"]


def test_logged_seance_keeps_real_time(session):
    """Séance réellement loggée : l'heure réelle est conservée."""
    date = dt.date(2026, 6, 10)
    create_seance(session, date=dt.datetime(2026, 6, 10, 17, 30), type="push", duree_min=45)

    blk = get_training_block_for_date(session, date)

    assert blk is not None
    assert blk["debut"] == dt.datetime(2026, 6, 10, 17, 30)
    assert blk["fin"] == dt.datetime(2026, 6, 10, 18, 15)
