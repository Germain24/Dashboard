"""Tests de la projection de poids."""

import datetime as dt

import pytest

from app.services.sante.projection import project_weight_to_target


def _linear_history(start_date, start_w, slope_per_day, days):
    return [(start_date + dt.timedelta(days=i), start_w + i * slope_per_day) for i in range(days)]


def test_no_measures_returns_none():
    assert project_weight_to_target([], target_weight=70.0) is None


def test_constant_weight_returns_no_date():
    today = dt.date(2026, 5, 17)
    measures = _linear_history(today - dt.timedelta(days=30), 51.0, 0.0, 31)
    res = project_weight_to_target(measures, target_weight=71.0, today=today)
    assert res is not None
    assert res.days_to_target is None
    assert "stable" in res.note.lower()


def test_steady_gain_projects_target_date():
    today = dt.date(2026, 5, 17)
    measures = _linear_history(today - dt.timedelta(days=30), 48.0, 0.1, 31)
    res = project_weight_to_target(measures, target_weight=71.0, today=today)
    assert res is not None
    assert res.current_weight == pytest.approx(51.0, abs=0.01)
    assert res.delta_kg == pytest.approx(20.0, abs=0.01)
    assert res.slope_kg_per_week == pytest.approx(0.7, abs=0.05)
    assert res.days_to_target is not None
    assert abs(res.days_to_target - 200) <= 2
    assert res.target_date == today + dt.timedelta(days=res.days_to_target)


def test_wrong_direction_returns_none_date():
    today = dt.date(2026, 5, 17)
    measures = _linear_history(today - dt.timedelta(days=30), 54.0, -0.1, 31)
    res = project_weight_to_target(measures, target_weight=71.0, today=today)
    assert res is not None
    assert res.days_to_target is None
    note = res.note.lower()
    assert "mene pas" in note or "mene" in note


def test_trend_7d_and_30d_both_returned():
    today = dt.date(2026, 5, 17)
    measures = _linear_history(today - dt.timedelta(days=30), 48.0, 0.1, 31)
    res = project_weight_to_target(measures, target_weight=71.0, today=today)
    assert res is not None
    assert res.trend_7d is not None
    assert res.trend_30d is not None
    assert res.trend_30d.samples >= 7


def test_confidence_low_when_few_samples():
    today = dt.date(2026, 5, 17)
    measures = [
        (today - dt.timedelta(days=2), 50.5),
        (today - dt.timedelta(days=1), 50.7),
        (today, 51.0),
    ]
    res = project_weight_to_target(measures, target_weight=71.0, today=today)
    assert res is not None
    assert res.confidence in ("low", "medium")
