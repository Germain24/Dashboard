import datetime as dt
from app.services.habitudes.streaks import compute_streak_pure

def test_streak_consecutive():
    today = dt.date(2026, 5, 31)
    dates = [dt.date(2026, 5, 29), dt.date(2026, 5, 30), dt.date(2026, 5, 31)]
    assert compute_streak_pure(dates, today) == 3

def test_streak_broken():
    today = dt.date(2026, 5, 31)
    dates = [dt.date(2026, 5, 28), dt.date(2026, 5, 30), dt.date(2026, 5, 31)]
    assert compute_streak_pure(dates, today) == 2

def test_streak_empty():
    assert compute_streak_pure([], dt.date(2026, 5, 31)) == 0

def test_streak_not_today():
    today = dt.date(2026, 5, 31)
    dates = [dt.date(2026, 5, 29), dt.date(2026, 5, 30)]
    assert compute_streak_pure(dates, today) == 0
