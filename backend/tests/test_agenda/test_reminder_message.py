"""Tests TDD — message de rappel contextuel (heure relative + heure + lieu) (#214)."""

from __future__ import annotations

import datetime as dt

from app.services.agenda.reminders import format_reminder


def test_includes_relative_time_hour_and_place():
    now = dt.datetime(2026, 6, 13, 14, 5)
    debut = dt.datetime(2026, 6, 13, 14, 30)
    msg = format_reminder(debut, now, lieu="Local B-2045")
    assert "dans 25 min" in msg
    assert "14:30" in msg
    assert "Local B-2045" in msg


def test_omits_place_when_absent():
    now = dt.datetime(2026, 6, 13, 14, 5)
    debut = dt.datetime(2026, 6, 13, 14, 30)
    msg = format_reminder(debut, now, lieu=None)
    assert "·" in msg  # heure relative · heure
    assert msg.endswith("14:30")


def test_now_when_already_started():
    now = dt.datetime(2026, 6, 13, 14, 30)
    debut = dt.datetime(2026, 6, 13, 14, 30)
    msg = format_reminder(debut, now)
    assert "maintenant" in msg
