"""Tests rappels habitudes (#136)."""

import datetime as dt
from types import SimpleNamespace

from app.services.habitudes.reminders import unchecked_habits, should_remind, mark_reminded


def _row(nom: str, done: bool) -> dict:
    return {"habit": SimpleNamespace(nom=nom), "entry": object() if done else None}


def test_unchecked_all_done():
    checklist = [_row("Méditation", True), _row("Lecture", True)]
    assert unchecked_habits(checklist) == []


def test_unchecked_some_missing():
    checklist = [_row("Méditation", True), _row("Lecture", False), _row("Sport", False)]
    assert unchecked_habits(checklist) == ["Lecture", "Sport"]


def test_should_remind_first_time(tmp_path):
    assert should_remind(dt.date(2026, 6, 7), path=tmp_path / "r.json") is True


def test_should_remind_after_mark(tmp_path):
    p = tmp_path / "r.json"
    date = dt.date(2026, 6, 7)
    mark_reminded(date, path=p)
    assert should_remind(date, path=p) is False


def test_should_remind_different_day(tmp_path):
    p = tmp_path / "r.json"
    mark_reminded(dt.date(2026, 6, 7), path=p)
    assert should_remind(dt.date(2026, 6, 8), path=p) is True
