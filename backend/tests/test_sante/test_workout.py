"""Intégration Entraînement → Santé : calories dépensées (#67)."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.services.sante.workout import burned_kcal_for_date


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_no_session_returns_zero(session):
    r = burned_kcal_for_date(session, dt.date(2026, 6, 3))
    assert r["total_kcal"] == 0.0
    assert r["available"] is True  # Entraînement importable, juste pas de séance


def test_counts_logged_muscu(session):
    from app.models.entrainement import Exercice, Seance, SetSerie

    ex = Exercice(nom="Squat", categorie="jambes")
    session.add(ex)
    session.commit()
    session.refresh(ex)

    d = dt.date(2026, 6, 3)
    seance = Seance(date=dt.datetime(2026, 6, 3, 18, 0), type="muscu")
    session.add(seance)
    session.commit()
    session.refresh(seance)
    # 5 reps × 100 kg → tonnage 500 → 0.05 × 500 = 25 kcal
    session.add(SetSerie(seance_id=seance.id, exercice_id=ex.id, reps=5, poids_kg=100))
    session.commit()

    r = burned_kcal_for_date(session, d)
    assert r["total_kcal"] > 0
    assert r["kcal_muscu"] == 25.0
