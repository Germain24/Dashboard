"""Hydratation + sommeil (MesureSante.extra)."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.services.sante import wellbeing


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_water_accumulates(session):
    d = dt.date(2026, 6, 3)
    wellbeing.add_water(session, d, 500)
    st = wellbeing.add_water(session, d, 750)
    assert st["eau_ml"] == 1250
    assert st["cible_ml"] == 2500
    assert st["pct"] == 50


def test_water_empty_day(session):
    st = wellbeing.get_water(session, dt.date(2026, 6, 4))
    assert st["eau_ml"] == 0


def test_sleep_recorded(session):
    d = dt.date(2026, 6, 3)
    r = wellbeing.set_sleep(session, d, 7.5, qualite=4)
    assert r["sommeil_h"] == 7.5
    assert r["sommeil_q"] == 4
    # n'écrase pas l'eau du même jour
    wellbeing.add_water(session, d, 300)
    assert wellbeing.get_water(session, d)["eau_ml"] == 300


def test_sleep_correlation_needs_data(session):
    assert wellbeing.sleep_weight_summary(session)["correlation"] is None
