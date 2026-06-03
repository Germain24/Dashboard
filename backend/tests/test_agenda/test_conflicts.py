"""Détection de conflits d'horaire (#87)."""

from __future__ import annotations

import datetime as dt

from app.services.agenda.conflicts import find_conflicts, overlaps


def _dt(h, m=0):
    return dt.datetime(2026, 6, 3, h, m)


def test_overlaps_basic():
    assert overlaps(_dt(9), _dt(11), _dt(10), _dt(12)) is True
    assert overlaps(_dt(9), _dt(10), _dt(10), _dt(11)) is False  # adjacents
    assert overlaps(_dt(9), _dt(10), _dt(11), _dt(12)) is False


def test_missing_fin_uses_default_hour():
    # event sans fin = 1h -> [10,11) chevauche [10:30, 11:30)
    assert overlaps(_dt(10), None, _dt(10, 30), _dt(11, 30)) is True


def test_find_conflicts_filters_and_ignores_id():
    existing = [
        {"id": 1, "titre": "A", "debut": _dt(9), "fin": _dt(10)},
        {"id": 2, "titre": "B", "debut": _dt(10, 30), "fin": _dt(11, 30)},
        {"id": 3, "titre": "C", "debut": _dt(14), "fin": _dt(15)},
    ]
    conflicts = find_conflicts(_dt(10), _dt(11), existing)
    assert [c["id"] for c in conflicts] == [2]

    # en modification, on ignore l'événement lui-même
    conflicts = find_conflicts(_dt(10, 30), _dt(11, 30), existing, ignore_id=2)
    assert conflicts == []


def test_find_conflicts_empty():
    assert find_conflicts(_dt(10), _dt(11), []) == []
