"""Tests TDD — prédiction de tendances par régression (#228)."""

from __future__ import annotations

import datetime as dt

from app.services.automatisations.forecast import forecast_series, linear_regression

D = dt.date(2026, 6, 1)


def test_linear_regression_perfect_line():
    slope, intercept = linear_regression([0, 1, 2, 3], [1, 3, 5, 7])  # y = 2x + 1
    assert round(slope, 6) == 2.0
    assert round(intercept, 6) == 1.0


def test_linear_regression_flat():
    slope, intercept = linear_regression([0, 1, 2], [5, 5, 5])
    assert slope == 0.0
    assert intercept == 5.0


def test_linear_regression_needs_variance_in_x():
    assert linear_regression([2, 2, 2], [1, 2, 3]) is None
    assert linear_regression([1], [1]) is None


def test_forecast_projects_forward():
    # +1 / jour pendant 10 jours -> dans 30 j, +30 par rapport au dernier
    points = [(D + dt.timedelta(days=i), float(i)) for i in range(10)]
    out = forecast_series(points, horizon_days=30)
    assert out["slope_per_day"] == 1.0
    assert out["courant"] == 9.0
    assert out["prevision"] == 39.0  # 9 + 30
    assert out["variation"] == 30.0
    assert out["direction"] == "hausse"


def test_forecast_decreasing_direction():
    points = [(D + dt.timedelta(days=i), float(80 - i)) for i in range(8)]
    out = forecast_series(points, horizon_days=10)
    assert out["direction"] == "baisse"
    assert out["prevision"] < out["courant"]


def test_forecast_needs_enough_points():
    assert forecast_series([(D, 1.0)], horizon_days=10) is None
