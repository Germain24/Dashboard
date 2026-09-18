"""Tests rappel mensuel score de crédit (#credit-reminder)."""

import datetime as dt

from app.services.finance.credit.reminders import should_remind, mark_reminded, reminder_key


def test_reminder_key_is_monthly():
    assert reminder_key(dt.date(2026, 7, 5)) == "2026-07"
    assert reminder_key(dt.date(2026, 7, 31)) == "2026-07"


def test_should_remind_first_time(tmp_path):
    assert should_remind(dt.date(2026, 7, 5), path=tmp_path / "r.json") is True


def test_should_remind_after_mark(tmp_path):
    p = tmp_path / "r.json"
    date = dt.date(2026, 7, 5)
    mark_reminded(date, path=p)
    assert should_remind(date, path=p) is False


def test_should_remind_same_month_different_day(tmp_path):
    p = tmp_path / "r.json"
    mark_reminded(dt.date(2026, 7, 5), path=p)
    assert should_remind(dt.date(2026, 7, 20), path=p) is False


def test_should_remind_different_month(tmp_path):
    p = tmp_path / "r.json"
    mark_reminded(dt.date(2026, 7, 5), path=p)
    assert should_remind(dt.date(2026, 8, 5), path=p) is True
