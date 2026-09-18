"""Tests du contrat Entraînement ↔ Santé sur l'intensité.

Le brief CONV 7 fige la signature : retour `{date, intensity in
none/low/medium/high}`. Santé importe `compute_intensity_for_date` et
retombe sur `default_intensity_for_date` en cas d'erreur.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.entrainement import Seance, SetSerie
from app.services.entrainement import (
    INTENSITY_LEVELS,
    add_set,
    compute_intensity_for_date,
    create_exercice,
    create_session,
    default_intensity_for_date,
    ensure_active_program,
    update_program_day,
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


def test_intensity_levels_match_contract():
    assert INTENSITY_LEVELS == ("none", "low", "medium", "high")


def test_default_intensity_germain_sport_days():
    """Lun/Mar/Mer/Ven/Sam = medium ; Jeu/Dim = none (fallback)."""
    assert default_intensity_for_date(dt.date(2026, 5, 18)) == "medium"  # lundi
    assert default_intensity_for_date(dt.date(2026, 5, 21)) == "none"    # jeudi
    assert default_intensity_for_date(dt.date(2026, 5, 24)) == "none"    # dimanche


def test_compute_no_data_falls_back_to_default(session):
    """Sans programme actif ni séance, on tombe sur le défaut date-based."""
    monday = dt.date(2026, 5, 18)
    thursday = dt.date(2026, 5, 21)
    assert compute_intensity_for_date(session, monday) == "medium"
    assert compute_intensity_for_date(session, thursday) == "none"


def test_compute_uses_program_label_when_no_session(session):
    """Programme actif PPL/UL : jeudi=Repos → none, lundi=Push → medium."""
    ensure_active_program(session)
    monday = dt.date(2026, 5, 18)
    thursday = dt.date(2026, 5, 21)
    assert compute_intensity_for_date(session, monday) == "medium"
    assert compute_intensity_for_date(session, thursday) == "none"


def test_compute_logged_session_dominates_program(session):
    """Si une séance est loggée, elle prime sur le programme."""
    prog = ensure_active_program(session)
    # On force le jeudi à "Repos" (déjà le cas par défaut)
    update_program_day(session, prog.id, 3, label="Repos", slots=[])

    thursday_dt = dt.datetime(2026, 5, 21, 18, 0)
    bench = create_exercice(session, nom="Bench test", categorie="push", source="manual")
    seance = create_session(session, date=thursday_dt, type="push", duree_min=45)
    add_set(session, seance_id=seance.id, exercice_id=bench.id, reps=5, poids_kg=60.0)

    # 45 min, pas de 1RM ref → medium
    assert compute_intensity_for_date(session, dt.date(2026, 5, 21)) == "medium"


def test_compute_short_session_is_low(session):
    """Séance < 30 min → low."""
    bench = create_exercice(session, nom="Bench short", categorie="push", source="manual")
    seance = create_session(
        session,
        date=dt.datetime(2026, 5, 19, 12, 0),
        type="push",
        duree_min=20,
    )
    add_set(session, seance_id=seance.id, exercice_id=bench.id, reps=10, poids_kg=20.0)
    assert compute_intensity_for_date(session, dt.date(2026, 5, 19)) == "low"


def test_compute_long_session_is_high(session):
    """Séance > 60 min → high."""
    sq = create_exercice(session, nom="Squat long", categorie="legs", source="manual")
    seance = create_session(
        session,
        date=dt.datetime(2026, 5, 20, 12, 0),
        type="legs",
        duree_min=75,
    )
    add_set(session, seance_id=seance.id, exercice_id=sq.id, reps=5, poids_kg=100.0)
    assert compute_intensity_for_date(session, dt.date(2026, 5, 20)) == "high"


def test_cardio_session_is_low(session):
    """Une séance de type 'cardio' → low (récup active)."""
    run = create_exercice(session, nom="Run test", categorie="cardio", source="manual")
    seance = create_session(
        session,
        date=dt.datetime(2026, 5, 22, 8, 0),
        type="cardio",
        duree_min=45,
    )
    add_set(session, seance_id=seance.id, exercice_id=run.id, reps=1, poids_kg=0.0)
    assert compute_intensity_for_date(session, dt.date(2026, 5, 22)) == "low"


def test_manual_intensity_is_respected(session):
    """`seance.intensite` saisie manuellement prime sur la classification auto."""
    bench = create_exercice(session, nom="Bench manual", categorie="push", source="manual")
    seance = create_session(
        session,
        date=dt.datetime(2026, 5, 23, 18, 0),
        type="push",
        duree_min=10,        # serait normalement "low"
        intensite="high",    # mais on force
    )
    add_set(session, seance_id=seance.id, exercice_id=bench.id, reps=5, poids_kg=60.0)
    assert compute_intensity_for_date(session, dt.date(2026, 5, 23)) == "high"


def test_sport_days_fallback_param_overrides_default(session):
    """Le param `sport_days_fallback` change le défaut quand rien d'autre n'existe."""
    monday = dt.date(2026, 5, 18)
    # Si l'utilisateur ne s'entraîne que le dimanche
    assert compute_intensity_for_date(session, monday, sport_days_fallback=[6]) == "none"
    sunday = dt.date(2026, 5, 24)
    assert compute_intensity_for_date(session, sunday, sport_days_fallback=[6]) == "medium"
