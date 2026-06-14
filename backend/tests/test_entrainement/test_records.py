"""Tests TDD — records personnels par exercice (PR board, #282)."""

from __future__ import annotations

import datetime as dt
import math

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.services.entrainement import add_set, create_exercice, create_session
from app.services.entrainement.records import personal_records


@pytest.fixture
def session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/r.db", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _seance(session, day_offset, *sets):
    """Crée une séance à J-offset avec des (exercice_id, reps, poids)."""
    d = dt.datetime.combine(dt.date.today() - dt.timedelta(days=day_offset), dt.time(18, 0))
    se = create_session(session, date=d, type="muscu")
    for ex_id, reps, poids in sets:
        add_set(session, seance_id=se.id, exercice_id=ex_id, reps=reps, poids_kg=poids)


def test_records_per_exercise(session):
    squat = create_exercice(session, nom="Squat", categorie="legs", source="manual")
    bench = create_exercice(session, nom="Développé couché", categorie="push", source="manual")
    # Squat : 80×5 (1RM 93.3) puis 100×3 (1RM 110, heaviest 100)
    _seance(session, 14, (squat.id, 5, 80.0))
    _seance(session, 0, (squat.id, 3, 100.0), (bench.id, 8, 60.0))

    recs = {r.exercice_nom: r for r in personal_records(session)}
    assert set(recs) == {"Squat", "Développé couché"}

    sq = recs["Squat"]
    assert math.isclose(sq.best_1rm_kg, 100 * (1 + 3 / 30), abs_tol=0.01)  # 110
    assert sq.best_1rm_poids_kg == 100.0
    assert sq.best_1rm_reps == 3
    assert sq.heaviest_kg == 100.0
    assert sq.best_1rm_date == dt.date.today()

    bp = recs["Développé couché"]
    assert math.isclose(bp.best_1rm_kg, 60 * (1 + 8 / 30), abs_tol=0.01)  # 76
    assert bp.heaviest_kg == 60.0


def test_records_empty_when_no_sets(session):
    create_exercice(session, nom="Vide", categorie="x", source="manual")
    # Aucun set -> l'exercice n'apparaît pas (pas de record).
    assert personal_records(session) == []


def test_records_sorted_by_best_1rm_desc(session):
    a = create_exercice(session, nom="A", categorie="x", source="manual")
    b = create_exercice(session, nom="B", categorie="x", source="manual")
    _seance(session, 0, (a.id, 1, 50.0), (b.id, 1, 120.0))
    recs = personal_records(session)
    assert [r.exercice_nom for r in recs] == ["B", "A"]
