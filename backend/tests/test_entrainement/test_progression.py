"""Tests de la progression (courbe 1RM + volume)."""

from __future__ import annotations

import datetime as dt
import math

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.services.entrainement import (
    add_set,
    create_exercice,
    create_session,
    current_1rm,
    progression_for_exercice,
)
from app.services.entrainement.progression import last_performance


@pytest.fixture
def session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/test.db",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _seed_progress(session: Session) -> int:
    """Crée un exercice + 4 séances étalées sur 8 semaines avec progression."""
    sq = create_exercice(session, nom="Squat barre test", categorie="legs", source="manual")
    today = dt.date.today()
    # 4 séances : -56j (80×5), -28j (90×5), -14j (95×5), aujourd'hui (100×5)
    plan = [(56, 80.0), (28, 90.0), (14, 95.0), (0, 100.0)]
    for delta_days, poids in plan:
        d = dt.datetime.combine(today - dt.timedelta(days=delta_days), dt.time(18, 0))
        seance = create_session(session, date=d, type="legs", duree_min=50)
        add_set(session, seance_id=seance.id, exercice_id=sq.id, reps=5, poids_kg=poids)
    return sq.id


def test_progression_returns_4_points(session):
    ex_id = _seed_progress(session)
    summary = progression_for_exercice(session, ex_id, days=90)
    assert len(summary.points) == 4


def test_progression_current_is_highest_recent(session):
    ex_id = _seed_progress(session)
    summary = progression_for_exercice(session, ex_id, days=90)
    # Dernier point = 100×5 → 1RM ≈ 116.67
    assert math.isclose(summary.current_1rm_kg, 100 * (1 + 5 / 30), abs_tol=0.01)


def test_progression_delta_4w_pct_positive(session):
    ex_id = _seed_progress(session)
    summary = progression_for_exercice(session, ex_id, days=90)
    # Il y a 4 semaines : 90×5. Maintenant 100×5. Delta > 0.
    assert summary.delta_4w_pct is not None
    assert summary.delta_4w_pct > 0


def test_current_1rm_zero_when_no_data(session):
    """Pas de séance → 1RM courant = 0.0 (pas d'erreur)."""
    sq = create_exercice(session, nom="Squat vide", categorie="legs", source="manual")
    assert current_1rm(session, sq.id) == 0.0


def test_progression_empty_when_no_data(session):
    sq = create_exercice(session, nom="Squat vide 2", categorie="legs", source="manual")
    summary = progression_for_exercice(session, sq.id, days=90)
    assert summary.points == []
    assert summary.current_1rm_kg == 0.0
    assert summary.best_1rm_kg == 0.0
    assert summary.delta_4w_pct is None


def test_last_performance_none_when_no_history(session):
    sq = create_exercice(session, nom="Squat vide 3", categorie="legs", source="manual")
    assert last_performance(session, sq.id) is None


def test_last_performance_summarises_most_recent_session(session):
    ex_id = _seed_progress(session)  # dernière séance = aujourd'hui (100×5)
    # « avant aujourd'hui » → la séance d'il y a 14j (95×5)
    lp = last_performance(session, ex_id, before=dt.date.today())
    assert lp is not None
    assert lp.date == dt.date.today() - dt.timedelta(days=14)
    assert lp.resume == "5×95kg"
