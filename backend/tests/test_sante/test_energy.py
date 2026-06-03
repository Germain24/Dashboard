"""Alerte déficit/surplus calorique agressif (#70)."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.models.sante import PlanNutrition
from app.services.sante import energy


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_classify_levels():
    assert energy.classify_balance(-300)["level"] == "ok"
    assert energy.classify_balance(-800)["level"] == "warning"
    assert energy.classify_balance(-1500)["level"] == "alert"
    assert energy.classify_balance(-1500)["direction"] == "déficit"
    assert energy.classify_balance(1200)["direction"] == "surplus"


def test_weekly_flags_aggressive_deficit(session):
    base = dt.date(2026, 6, 3)
    # maintenance = 80 * 32 = 2560 ; conso 1300 -> deficit ~1260/j (alert)
    for i in range(5):
        session.add(PlanNutrition(
            date=base - dt.timedelta(days=i),
            poids_used=80.0,
            consumed={"Calories": 1300},
        ))
    session.commit()
    r = energy.weekly_energy_balance(session, end_date=base)
    assert r["days"] == 5
    assert r["direction"] == "déficit"
    assert r["level"] == "alert"
    assert r["avg_balance"] == -1260


def test_weekly_no_data(session):
    r = energy.weekly_energy_balance(session, end_date=dt.date(2026, 6, 3))
    assert r["days"] == 0
    assert r["avg_balance"] is None
