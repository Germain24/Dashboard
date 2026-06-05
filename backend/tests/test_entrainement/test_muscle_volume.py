"""Volume hebdomadaire par groupe musculaire + détection sous/sur-entraînement (#107)."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.services.entrainement import (
    add_set,
    create_exercice,
    create_session,
)
from app.services.entrainement.muscle_volume import (
    SETS_MEV,
    SETS_MRV,
    classify_volume,
    weekly_muscle_volume,
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


def _seance(session: Session, day_offset: int):
    d = dt.datetime.combine(dt.date.today() - dt.timedelta(days=day_offset), dt.time(18, 0))
    return create_session(session, date=d, type="push", duree_min=50)


def test_classify_thresholds():
    assert classify_volume(SETS_MEV - 1) == "sous"
    assert classify_volume(SETS_MEV) == "optimal"
    assert classify_volume(SETS_MRV) == "optimal"
    assert classify_volume(SETS_MRV + 1) == "sur"


def test_set_counts_for_each_targeted_muscle(session):
    """Une série compte pour chaque muscle ciblé par l'exercice."""
    dc = create_exercice(session, nom="Développé couché", categorie="push",
                         muscles=["pectoraux", "triceps"], source="manual")
    seance = _seance(session, 0)
    add_set(session, seance_id=seance.id, exercice_id=dc.id, reps=8, poids_kg=60.0)

    vols = {v.muscle: v for v in weekly_muscle_volume(session)}
    assert vols["pectoraux"].sets == 1
    assert vols["triceps"].sets == 1
    assert vols["pectoraux"].tonnage_kg == 8 * 60.0


def test_aggregates_over_window_and_sorts_desc(session):
    dc = create_exercice(session, nom="DC", categorie="push", muscles=["pectoraux"], source="manual")
    ext = create_exercice(session, nom="Extension triceps", categorie="push",
                          muscles=["triceps"], source="manual")
    s_recent = _seance(session, 1)
    for _ in range(12):
        add_set(session, seance_id=s_recent.id, exercice_id=dc.id, reps=8, poids_kg=60.0)
    add_set(session, seance_id=s_recent.id, exercice_id=ext.id, reps=12, poids_kg=20.0)

    vols = weekly_muscle_volume(session)
    # Trié par nb de séries décroissant
    assert [v.muscle for v in vols] == ["pectoraux", "triceps"]
    assert vols[0].sets == 12


def test_window_excludes_old_sessions(session):
    dc = create_exercice(session, nom="DC2", categorie="push", muscles=["pectoraux"], source="manual")
    old = _seance(session, 30)  # hors fenêtre 7j
    add_set(session, seance_id=old.id, exercice_id=dc.id, reps=8, poids_kg=60.0)
    assert weekly_muscle_volume(session, days=7) == []


def test_status_detection(session):
    dc = create_exercice(session, nom="DC3", categorie="push", muscles=["pectoraux"], source="manual")
    seance = _seance(session, 0)
    for _ in range(SETS_MRV + 2):  # au-delà de MRV → sur-entraînement
        add_set(session, seance_id=seance.id, exercice_id=dc.id, reps=8, poids_kg=60.0)
    vols = {v.muscle: v for v in weekly_muscle_volume(session)}
    assert vols["pectoraux"].status == "sur"
