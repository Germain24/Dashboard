"""Corrélation entraînement ↔ poids (#112)."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.sante import MesureSante
from app.services.entrainement import add_set, create_exercice, create_session
from app.services.entrainement.correlation import pearson, training_weight_correlation


@pytest.fixture
def session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/test.db",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_pearson_perfect_positive():
    assert pearson([(1, 2), (2, 4), (3, 6)]) == 1.0


def test_pearson_none_when_too_few_or_flat():
    assert pearson([(1, 1), (2, 2)]) is None        # < 3 points
    assert pearson([(5, 1), (5, 2), (5, 3)]) is None  # variance x nulle


def test_correlation_series_length_and_positive_sign(session):
    today = dt.date(2026, 6, 1)  # un lundi
    sq = create_exercice(session, nom="Squat corr", categorie="legs", source="manual")
    # 4 semaines : tonnage et poids croissants ensemble → corrélation ≈ +1
    plan = [(3, 100.0, 70.0), (2, 110.0, 70.5), (1, 120.0, 71.0), (0, 130.0, 71.5)]
    for wk_back, poids, weight in plan:
        d = today - dt.timedelta(days=7 * wk_back)
        seance = create_session(session, date=dt.datetime.combine(d, dt.time(18, 0)), type="legs", duree_min=50)
        add_set(session, seance_id=seance.id, exercice_id=sq.id, reps=10, poids_kg=poids)
        session.add(MesureSante(date=d, poids=weight))
        session.commit()

    res = training_weight_correlation(session, weeks=4, today=today)
    assert len(res["weeks"]) == 4
    assert res["n"] == 4
    assert res["correlation"] is not None and res["correlation"] > 0.9
    # la dernière semaine porte le plus gros tonnage
    assert res["weeks"][-1].tonnage_kg == 1300.0
    assert res["weeks"][-1].poids_kg == 71.5


def test_correlation_none_without_enough_overlap(session):
    today = dt.date(2026, 6, 1)
    res = training_weight_correlation(session, weeks=8, today=today)
    assert len(res["weeks"]) == 8
    assert res["correlation"] is None
    assert res["n"] == 0
