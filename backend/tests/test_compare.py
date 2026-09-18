"""Tests TDD — helper générique de comparaison période/période (#229)."""

from __future__ import annotations

from app.core.compare import period_over_period


def test_increase():
    r = period_over_period(120.0, 100.0)
    assert r["current"] == 120.0
    assert r["previous"] == 100.0
    assert r["delta"] == 20.0
    assert r["delta_pct"] == 20.0
    assert r["direction"] == "up"


def test_decrease():
    r = period_over_period(80.0, 100.0)
    assert r["delta"] == -20.0
    assert r["delta_pct"] == -20.0
    assert r["direction"] == "down"


def test_flat():
    r = period_over_period(50.0, 50.0)
    assert r["delta"] == 0.0
    assert r["delta_pct"] == 0.0
    assert r["direction"] == "flat"


def test_previous_zero_pct_undefined():
    r = period_over_period(50.0, 0.0)
    assert r["delta"] == 50.0
    assert r["delta_pct"] is None  # pas de % quand la base est 0
    assert r["direction"] == "up"


def test_pct_uses_absolute_previous():
    # base négative (ex. dépenses) : le % se calcule sur la valeur absolue.
    r = period_over_period(-80.0, -100.0)
    assert r["delta"] == 20.0
    assert r["delta_pct"] == 20.0
    assert r["direction"] == "up"
