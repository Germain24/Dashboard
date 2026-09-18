"""Tests gamification habitudes (#142)."""

import datetime as dt

from sqlmodel import SQLModel, Session, create_engine

from app.models.habitudes import Habit, HabitEntry  # noqa: F401
from app.services.habitudes.gamification import (
    compute_xp,
    compute_level,
    xp_to_next_level,
    get_gamification,
)


def test_xp_zero_completions():
    assert compute_xp(0, 0) == 0


def test_xp_basic():
    assert compute_xp(10, 0) == 10


def test_xp_streak_bonus():
    # 7-day streak → +5 bonus
    assert compute_xp(7, 7) == 7 + 5


def test_xp_streak_two_weeks():
    # 14-day streak → +10 bonus
    assert compute_xp(14, 14) == 14 + 10


def test_level_starts_at_1():
    assert compute_level(0) == 1


def test_level_increases():
    assert compute_level(10) == 2
    assert compute_level(40) == 3
    assert compute_level(90) == 4


def test_xp_to_next():
    # at xp=0 (level 1), need 10 to reach level 2
    assert xp_to_next_level(0) == 10


def test_xp_to_next_partial():
    assert xp_to_next_level(5) == 5


# ── get_gamification (DB) ────────────────────────────────────────────────────

def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_get_gamification_empty():
    assert get_gamification(_session()) == []


def test_get_gamification_counts_completions_and_streak():
    s = _session()
    h = Habit(nom="Sport")
    s.add(h)
    s.commit()
    s.refresh(h)
    today = dt.date(2026, 6, 8)
    # 7 jours consécutifs finissant aujourd'hui → 7 complétions + bonus semaine
    for i in range(7):
        s.add(HabitEntry(habit_id=h.id, date=today - dt.timedelta(days=i), valeur=1.0))
    s.commit()
    rows = get_gamification(s, today=today)
    assert len(rows) == 1
    row = rows[0]
    assert row["habit_id"] == h.id
    assert row["xp"] == compute_xp(7, 7)  # 7 + 5 bonus
    assert row["level"] == compute_level(row["xp"])
    assert row["xp_to_next"] >= 0
