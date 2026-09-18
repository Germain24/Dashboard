"""Export .ics (#91)."""

from __future__ import annotations

import datetime as dt

from app.services.agenda.ical_adapter import serialize_ics


def _ev(titre, h, lieu=None):
    return {
        "titre": titre,
        "debut": dt.datetime(2026, 6, 3, h, 0),
        "fin": dt.datetime(2026, 6, 3, h + 1, 0),
        "lieu": lieu,
    }


def test_serialize_basic_structure():
    ics = serialize_ics([_ev("Cours maths", 9)])
    assert ics.startswith("BEGIN:VCALENDAR")
    assert "END:VCALENDAR" in ics
    assert "BEGIN:VEVENT" in ics
    assert "SUMMARY:Cours maths" in ics
    assert "DTSTART:20260603T090000" in ics
    assert "DTEND:20260603T100000" in ics
    assert ics.endswith("\r\n")


def test_escaping_special_chars():
    ics = serialize_ics([{"titre": "Réu; client, A\nB", "debut": dt.datetime(2026, 6, 3, 9), "fin": None}])
    assert "SUMMARY:Réu\\; client\\, A\\nB" in ics


def test_missing_fin_defaults_one_hour():
    ics = serialize_ics([{"titre": "X", "debut": dt.datetime(2026, 6, 3, 9), "fin": None}])
    assert "DTSTART:20260603T090000" in ics
    assert "DTEND:20260603T100000" in ics


def test_location_included():
    ics = serialize_ics([_ev("Sport", 18, lieu="Gym")])
    assert "LOCATION:Gym" in ics


def test_skips_invalid_debut():
    ics = serialize_ics([{"titre": "bad", "debut": "pas une date"}])
    assert "BEGIN:VEVENT" not in ics
