import datetime as dt

from sqlmodel import SQLModel, Session, create_engine

from app.models.habitudes import Habit, HabitEntry  # noqa: F401
from app.services.habitudes.entries import DEFAULT_HABITS, get_today_checklist, upsert_entry


def test_default_habits_count():
    assert len(DEFAULT_HABITS) == 6


def test_default_habits_have_required_fields():
    for h in DEFAULT_HABITS:
        assert "nom" in h
        assert "type" in h
        assert h["type"] in ("binaire", "quantifiable")


def test_muscu_has_source_auto():
    muscu = next(h for h in DEFAULT_HABITS if h["nom"] == "Muscu")
    assert muscu["source_auto"] == "entrainement_muscu"


def test_lecture_is_quantifiable():
    lecture = next(h for h in DEFAULT_HABITS if h["nom"] == "Lecture")
    assert lecture["type"] == "quantifiable"
    assert lecture["cible"] == 30.0


# ── fréquence hebdomadaire (#135) ────────────────────────────────────────────

def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_weekly_habit_done_this_week_shows_entry():
    s = _session()
    habit = Habit(nom="Yoga", frequence="weekly", actif=True)
    s.add(habit)
    s.commit(); s.refresh(habit)
    today = dt.date(2026, 6, 5)                    # Thursday
    monday = dt.date(2026, 6, 2)
    upsert_entry(s, habit.id, monday)              # done on Monday
    checklist = get_today_checklist(s, today=today)
    row = next(r for r in checklist if r["habit"].id == habit.id)
    assert row["entry"] is not None                # shows as done


def test_daily_habit_uses_today_only():
    s = _session()
    habit = Habit(nom="Méditation", frequence="daily", actif=True)
    s.add(habit)
    s.commit(); s.refresh(habit)
    today = dt.date(2026, 6, 5)
    yesterday = dt.date(2026, 6, 4)
    upsert_entry(s, habit.id, yesterday)
    checklist = get_today_checklist(s, today=today)
    row = next(r for r in checklist if r["habit"].id == habit.id)
    assert row["entry"] is None                    # yesterday doesn't count today


# ── habitudes liées (#139) ───────────────────────────────────────────────────

import json
from sqlmodel import select as sq_select
from app.models.habitudes import HabitEntry as HE


def test_linked_habits_auto_checked():
    s = _session()
    sport = Habit(nom="Sport", actif=True)
    s.add(sport); s.commit(); s.refresh(sport)
    cardio = Habit(nom="Cardio", actif=True)
    s.add(cardio); s.commit(); s.refresh(cardio)
    # sport linked to cardio
    sport.linked_ids = json.dumps([cardio.id])
    s.add(sport); s.commit()
    today = dt.date(2026, 6, 5)
    upsert_entry(s, sport.id, today)
    linked_entry = s.exec(
        sq_select(HE).where(HE.habit_id == cardio.id, HE.date == today)
    ).first()
    assert linked_entry is not None
    assert linked_entry.auto is True
