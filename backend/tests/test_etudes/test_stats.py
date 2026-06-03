"""Statistiques d'étude (#94/#97/#101/#102)."""

from __future__ import annotations

import datetime as dt

from app.services.etudes.stats import (
    daily_minutes,
    minutes_by_course,
    study_streak,
    weekly_summary,
)


def _s(d, mins, cid=None):
    return {"date": d, "duree_min": mins, "cours_id": cid}


def test_minutes_by_course_sorted_with_labels():
    sessions = [_s(dt.date(2026, 6, 1), 60, 1), _s(dt.date(2026, 6, 2), 30, 2), _s(dt.date(2026, 6, 3), 90, 1)]
    out = minutes_by_course(sessions, {1: "INF1000", 2: "MAT1000"})
    assert out[0]["label"] == "INF1000"
    assert out[0]["minutes"] == 150
    assert out[1]["minutes"] == 30


def test_minutes_by_course_libre():
    out = minutes_by_course([_s(dt.date(2026, 6, 1), 25, None)])
    assert out[0]["label"] == "Libre"


def test_daily_minutes():
    sessions = [_s(dt.date(2026, 6, 1), 30), _s(dt.date(2026, 6, 1), 20), _s(dt.date(2026, 6, 3), 45)]
    dm = daily_minutes(sessions)
    assert dm["2026-06-01"] == 50
    assert dm["2026-06-03"] == 45


def test_streak_current_and_best():
    dates = [dt.date(2026, 6, 1), dt.date(2026, 6, 2), dt.date(2026, 6, 3),  # série de 3
             dt.date(2026, 5, 20), dt.date(2026, 5, 21)]  # série de 2
    r = study_streak(dates, today=dt.date(2026, 6, 3))
    assert r["best"] == 3
    assert r["current"] == 3


def test_streak_anchored_yesterday():
    # pas encore étudié aujourd'hui, mais hier + avant-hier
    dates = [dt.date(2026, 6, 1), dt.date(2026, 6, 2)]
    r = study_streak(dates, today=dt.date(2026, 6, 3))
    assert r["current"] == 2


def test_streak_broken():
    r = study_streak([dt.date(2026, 5, 1)], today=dt.date(2026, 6, 3))
    assert r["current"] == 0
    assert r["best"] == 1


def test_weekly_summary_window():
    # semaine du lundi 2026-06-01
    sessions = [
        _s(dt.date(2026, 6, 1), 60, 1),
        _s(dt.date(2026, 6, 7), 30, 1),   # dimanche, dans la semaine
        _s(dt.date(2026, 6, 8), 90, 1),   # hors semaine
    ]
    r = weekly_summary(sessions, {1: "INF"}, week_start=dt.date(2026, 6, 1))
    assert r["total_minutes"] == 90
    assert r["sessions"] == 2
