"""Tests TDD — insights hebdomadaires auto-générés (#223)."""

from __future__ import annotations

import datetime as dt

from app.services.automatisations.insights import (
    aggregate_period,
    summarize_week,
)

MON = dt.date(2026, 6, 8)  # un lundi


def _week(start):
    return [start + dt.timedelta(days=i) for i in range(7)]


# ── aggregate_period ──────────────────────────────────────────────────────────

def test_aggregate_mean_and_sum():
    days = _week(MON)
    series = {
        "Habitudes %": {d: 80 for d in days},          # moyenne -> 80
        "Dépenses": {d: 10 for d in days},             # somme -> 70
    }
    agg = aggregate_period(series, set(days))
    assert agg["Habitudes %"] == 80
    assert agg["Dépenses"] == 70


def test_aggregate_ignores_dates_outside_period():
    days = _week(MON)
    series = {"Séances": {days[0]: 1, days[1]: 1, MON - dt.timedelta(days=3): 5}}
    agg = aggregate_period(series, set(days))
    assert agg["Séances"] == 2  # le 5 hors période est ignoré


# ── summarize_week ────────────────────────────────────────────────────────────

def test_habits_up_is_a_success():
    out = summarize_week({"Habitudes %": 90}, {"Habitudes %": 70}, min_change_pct=10)
    assert any("Habitudes" in m for m in out["reussites"])
    assert out["vigilance"] == []


def test_spending_up_is_vigilance():
    out = summarize_week({"Dépenses": 200}, {"Dépenses": 100}, min_change_pct=10)
    assert any("Dépenses" in m for m in out["vigilance"])


def test_spending_down_is_success():
    out = summarize_week({"Dépenses": 80}, {"Dépenses": 100}, min_change_pct=10)
    assert any("Dépenses" in m for m in out["reussites"])


def test_neutral_metric_is_a_trend_not_judged():
    out = summarize_week({"Poids": 72}, {"Poids": 70}, min_change_pct=1)
    assert any("Poids" in m for m in out["tendances"])
    assert out["reussites"] == [] and out["vigilance"] == []


def test_small_change_below_threshold_ignored():
    out = summarize_week({"Humeur": 7.1}, {"Humeur": 7.0}, min_change_pct=10)
    assert out["reussites"] == [] and out["vigilance"] == [] and out["tendances"] == []


def test_missing_or_zero_previous_skipped():
    out = summarize_week({"Séances": 3}, {}, min_change_pct=10)              # absent
    assert out["reussites"] == [] and out["tendances"] == []
    out2 = summarize_week({"Séances": 3}, {"Séances": 0}, min_change_pct=10)  # prev 0
    assert out2["reussites"] == []
