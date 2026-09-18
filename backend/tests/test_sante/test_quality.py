"""Score de qualité nutritionnelle hebdomadaire (#65)."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.models.sante import PlanNutrition
from app.services.sante import quality


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_score_day_perfect():
    targets = {"Calories": 2000, "Protéines": 150, "Fibres": 30, "Sucres_Max": 50}
    consumed = {"Calories": 2000, "Protéines": 150, "Fibres": 30, "Sucres_Max": 40}
    r = quality.score_day(consumed, targets)
    assert r["score"] == 100


def test_score_day_low_protein_and_excess_sugar():
    targets = {"Calories": 2000, "Protéines": 150, "Fibres": 30, "Sucres_Max": 50}
    # moitié des protéines, double du sucre limite
    consumed = {"Calories": 2000, "Protéines": 75, "Fibres": 30, "Sucres_Max": 100}
    r = quality.score_day(consumed, targets)
    assert r["criteria"]["Protéines"] == 50
    assert r["criteria"]["Sucres_Max"] == 0
    assert 0 < r["score"] < 100


def test_score_day_no_data_returns_none():
    assert quality.score_day({}, {"Calories": 2000})["score"] is None


def test_weekly_aggregates_days_with_consumed(session):
    base = dt.date(2026, 6, 3)
    targets = {"Calories": 2000, "Protéines": 150, "Fibres": 30}
    # 2 jours parfaits, 1 jour sans conso (ignoré)
    for i, consumed in enumerate([
        {"Calories": 2000, "Protéines": 150, "Fibres": 30},
        {"Calories": 2000, "Protéines": 150, "Fibres": 30},
        None,
    ]):
        session.add(PlanNutrition(date=base - dt.timedelta(days=i), targets=targets, consumed=consumed))
    session.commit()

    r = quality.weekly_nutrition_quality(session, end_date=base, days=7)
    assert r["days"] == 2
    assert r["score"] == 100
    assert len(r["daily"]) == 2


def test_weekly_no_data(session):
    r = quality.weekly_nutrition_quality(session, end_date=dt.date(2026, 6, 3))
    assert r["days"] == 0
    assert r["score"] is None
