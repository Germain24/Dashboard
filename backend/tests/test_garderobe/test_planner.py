"""Planificateur de tenues hebdomadaire (#79)."""

from __future__ import annotations

import datetime as dt

from app.services.garderobe.planner import (
    get_day,
    monday_of,
    set_day,
    week_dates,
)


def test_monday_of_and_week():
    # 2026-06-03 est un mercredi
    mon = monday_of(dt.date(2026, 6, 3))
    assert mon == dt.date(2026, 6, 1)
    assert week_dates(mon)[0] == mon
    assert week_dates(mon)[-1] == dt.date(2026, 6, 7)
    assert len(week_dates(mon)) == 7


def test_set_and_get_day(tmp_path):
    p = tmp_path / "plan.json"
    d = dt.date(2026, 6, 3)
    set_day(d, {"Haut": "pull-marine", "Pantalon": "jean-brut", "Manteau": None}, path=p)
    got = get_day(d, path=p)
    assert got == {"Haut": "pull-marine", "Pantalon": "jean-brut"}  # None retiré


def test_empty_tenue_removes_date(tmp_path):
    p = tmp_path / "plan.json"
    d = dt.date(2026, 6, 3)
    set_day(d, {"Haut": "x"}, path=p)
    set_day(d, {"Haut": None}, path=p)
    assert get_day(d, path=p) == {}


def test_get_unknown_day(tmp_path):
    assert get_day(dt.date(2026, 6, 9), path=tmp_path / "plan.json") == {}
