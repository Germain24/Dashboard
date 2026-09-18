"""Tests progression & estimation de lecture (#144, #150)."""

from app.services.livres.progress import (
    reading_progress,
    reading_pace,
    estimate_remaining_minutes,
)


def test_progress_basic():
    assert reading_progress(150, 300)["pct"] == 50.0


def test_progress_no_pages():
    r = reading_progress(10, None)
    assert r["pct"] == 0
    assert r["pages"] == 0


def test_progress_clamps_overflow():
    r = reading_progress(500, 300)
    assert r["page_courante"] == 300
    assert r["pct"] == 100.0


def test_progress_none_current():
    assert reading_progress(None, 300)["pct"] == 0.0


def test_pace_basic():
    # 60 pages en 120 min → 0.5 page/min
    assert reading_pace(60, 120) == 0.5


def test_pace_zero_minutes():
    assert reading_pace(60, 0) == 0.0


def test_estimate_remaining():
    # 150/300 lues, rythme 0.5 p/min → 150 pages restantes → 300 min
    assert estimate_remaining_minutes(150, 300, 0.5) == 300


def test_estimate_none_when_finished():
    assert estimate_remaining_minutes(300, 300, 0.5) is None


def test_estimate_none_without_pace():
    assert estimate_remaining_minutes(100, 300, 0.0) is None
