"""Tests du module suggested_weight (progressive overload + baseline)."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.services.entrainement import (
    add_set,
    create_exercice,
    create_session,
)
from app.services.entrainement.suggested_weight import (
    BASELINE_RATIO,
    baseline_weight,
    suggested_weight,
)


@pytest.fixture
def session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/test.db",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_baseline_squat_for_51kg_germain():
    class _E:
        nom = "Squat barre"
    w = baseline_weight(_E(), poids_corps_kg=51.0)
    assert w == 61.0


def test_baseline_bench_for_51kg():
    class _E:
        nom = "Developpe couche barre"
    w = baseline_weight(_E(), poids_corps_kg=51.0)
    assert w == 43.5


def test_baseline_bodyweight_exercice():
    class _E:
        nom = "Pull-ups (poids du corps)"
    assert baseline_weight(_E(), poids_corps_kg=70.0) == 0.0


def test_baseline_default_for_unknown_exo():
    class _E:
        nom = "Exercice exotique invente"
    w = baseline_weight(_E(), poids_corps_kg=70.0, default_ratio=0.30)
    assert w == 21.0


def test_suggested_uses_baseline_without_history(session):
    sq = create_exercice(session, nom="Squat barre", categorie="legs", source="manual")
    w = suggested_weight(session, sq.id, poids_corps_kg=51.0)
    assert w == 61.0


def test_suggested_progressive_overload_with_history(session):
    sq = create_exercice(session, nom="Squat hist", categorie="legs", source="manual")
    seance = create_session(
        session,
        date=dt.datetime.combine(
            dt.date.today() - dt.timedelta(days=7), dt.time(18, 0)
        ),
        type="legs",
    )
    add_set(session, seance_id=seance.id, exercice_id=sq.id, reps=5, poids_kg=100.0)
    add_set(session, seance_id=seance.id, exercice_id=sq.id, reps=5, poids_kg=90.0)
    w = suggested_weight(session, sq.id, poids_corps_kg=70.0)
    assert w == 102.5


def test_suggested_uses_pdc_fallback_when_sante_empty(session):
    """Sans MesureSante : on retombe sur POIDS_CORPS_FALLBACK_KG (70 kg)."""
    sq = create_exercice(session, nom="Squat barre", categorie="legs", source="manual")
    w = suggested_weight(session, sq.id)
    assert w == 84.0


def test_suggested_none_for_unknown_exercice(session):
    w = suggested_weight(session, 99999, poids_corps_kg=70.0)
    assert w is None


def test_baseline_ratios_well_formed():
    for nom, ratio in BASELINE_RATIO.items():
        assert isinstance(ratio, (int, float))
        assert ratio >= 0
        assert nom == nom.lower()
