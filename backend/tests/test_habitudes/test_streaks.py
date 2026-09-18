import datetime as dt
from app.services.habitudes.streaks import compute_streak_pure, compute_best_streak_pure

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

# ── best streak ──────────────────────────────────────────────────────────────

def test_best_streak_empty():
    assert compute_best_streak_pure([]) == 0

def test_best_streak_single():
    assert compute_best_streak_pure([dt.date(2026, 5, 31)]) == 1

def test_best_streak_all_consecutive():
    dates = [dt.date(2026, 5, 29), dt.date(2026, 5, 30), dt.date(2026, 5, 31)]
    assert compute_best_streak_pure(dates) == 3

def test_best_streak_gap():
    dates = [
        dt.date(2026, 5, 1), dt.date(2026, 5, 2), dt.date(2026, 5, 3),  # run of 3
        dt.date(2026, 5, 10), dt.date(2026, 5, 11),                        # run of 2
    ]
    assert compute_best_streak_pure(dates) == 3

def test_best_streak_picks_longest():
    dates = [
        dt.date(2026, 5, 1),
        dt.date(2026, 5, 5), dt.date(2026, 5, 6), dt.date(2026, 5, 7),
        dt.date(2026, 5, 8), dt.date(2026, 5, 9),                         # run of 5
    ]
    assert compute_best_streak_pure(dates) == 5
