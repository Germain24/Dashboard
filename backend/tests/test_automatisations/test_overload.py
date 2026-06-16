"""Tests TDD — détection de surcharge (#231)."""

from __future__ import annotations

import datetime as dt

from app.services.automatisations.overload import assess_overload

D = dt.date(2026, 6, 15)


def _day(date, load_min, n=3):
    return {"date": date, "load_min": load_min, "n_events": n}


def test_flags_days_above_threshold():
    days = [_day(D, 700), _day(D + dt.timedelta(days=1), 300)]
    out = assess_overload(days, threshold_min=600)
    assert len(out) == 1
    assert out[0]["date"] == D
    assert out[0]["load_h"] == round(700 / 60, 1)
    assert "alléger" in out[0]["suggestion"] or "reporter" in out[0]["suggestion"]


def test_below_threshold_not_flagged():
    assert assess_overload([_day(D, 300)], threshold_min=600) == []


def test_sorted_by_load_desc():
    days = [_day(D, 650), _day(D + dt.timedelta(days=1), 800), _day(D + dt.timedelta(days=2), 700)]
    out = assess_overload(days, threshold_min=600)
    loads = [o["load_min"] for o in out]
    assert loads == sorted(loads, reverse=True)


def test_threshold_boundary_inclusive():
    assert len(assess_overload([_day(D, 600)], threshold_min=600)) == 1
