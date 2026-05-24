"""Tests du module calories (tonnage muscu + Niemann course)."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.services.entrainement import (
    add_set,
    create_course,
    create_exercice,
    create_session,
)
from app.services.entrainement.calories import (
    K_MUSCU_KCAL_PER_KG_REP,
    NIEMANN_RUN_K,
    POIDS_CORPS_FALLBACK_KG,
    estimate_calories_seance,
    kcal_for_date,
    kcal_muscu_from_sets,
    kcal_run_from_course,
    resolve_poids_corps,
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


def test_muscu_tonnage_formula(session):
    sq = create_exercice(session, nom="Squat test", categorie="legs", source="manual")
    seance = create_session(session, date=dt.datetime(2026, 5, 18, 18, 0), type="legs")
    add_set(session, seance_id=seance.id, exercice_id=sq.id, reps=5, poids_kg=100.0)
    add_set(session, seance_id=seance.id, exercice_id=sq.id, reps=5, poids_kg=100.0)
    # Tonnage = 2 * 5 * 100 = 1000 ; kcal = 1000 * 0.05 = 50
    from app.services.entrainement import list_sets_for_seance
    sets = list_sets_for_seance(session, seance.id)
    assert kcal_muscu_from_sets(sets) == round(K_MUSCU_KCAL_PER_KG_REP * 1000, 1)


def test_niemann_course_basic():
    """Course 5 km avec 70 kg → ≈ 362.6 kcal (1.036 * 70 * 5)."""
    class _C:
        distance_km = 5.0
    expected = round(NIEMANN_RUN_K * 70 * 5.0, 1)
    assert kcal_run_from_course(_C(), 70.0) == expected


def test_niemann_zero_distance():
    class _C:
        distance_km = 0.0
    assert kcal_run_from_course(_C(), 70.0) == 0.0


def test_estimate_seance_muscu_uses_tonnage(session):
    bench = create_exercice(session, nom="Bench cal test", categorie="push", source="manual")
    seance = create_session(session, date=dt.datetime(2026, 5, 19, 18, 0), type="push", duree_min=45)
    add_set(session, seance_id=seance.id, exercice_id=bench.id, reps=8, poids_kg=60.0)
    from app.services.entrainement import list_sets_for_seance
    sets = list_sets_for_seance(session, seance.id)
    agg = estimate_calories_seance(seance, sets, poids_corps_kg=70.0)
    assert agg["kcal_muscu"] > 0
    assert agg["kcal_cardio"] == 0
    assert agg["total_kcal"] == agg["kcal_muscu"]


def test_estimate_seance_cardio_uses_warmup_met(session):
    seance = create_session(session, date=dt.datetime(2026, 5, 20, 8, 0), type="cardio", duree_min=30)
    agg = estimate_calories_seance(seance, [], poids_corps_kg=70.0)
    # 5 METS * 70kg * 0.5h = 175 kcal
    assert agg["kcal_cardio"] == 175.0


def test_kcal_for_date_combines_muscu_and_course(session):
    today = dt.date(2026, 5, 21)
    sq = create_exercice(session, nom="Sq combo", categorie="legs", source="manual")
    seance = create_session(session, date=dt.datetime.combine(today, dt.time(18, 0)), type="legs")
    add_set(session, seance_id=seance.id, exercice_id=sq.id, reps=5, poids_kg=100.0)
    create_course(session, date=today, distance_km=5.0, duree_sec=1500)
    agg = kcal_for_date(session, today, poids_corps_kg=70.0)
    assert agg["kcal_muscu"] > 0
    assert agg["kcal_cardio"] > 0
    assert agg["total_kcal"] == round(agg["kcal_muscu"] + agg["kcal_cardio"], 1)
    assert agg["date"] == today


def test_resolve_poids_corps_fallback_without_sante(session):
    """Sans MesureSante, on retombe sur le fallback 70kg."""
    pdc = resolve_poids_corps(session)
    assert pdc == POIDS_CORPS_FALLBACK_KG


def test_resolve_poids_corps_uses_sante_when_available(session):
    """Avec une MesureSante, on prend la dernière."""
    from app.models.sante import MesureSante
    session.add(MesureSante(date=dt.date(2026, 5, 15), poids=51.0))
    session.commit()
    pdc = resolve_poids_corps(session, before=dt.date(2026, 5, 20))
    assert pdc == 51.0
