"""Bloc focus Études → Agenda (#89)."""

from __future__ import annotations

import datetime as dt

from app.services.agenda.focus import pick_slot


def _slot(h0, h1):
    return {
        "debut": dt.datetime(2026, 6, 3, h0, 0),
        "fin": dt.datetime(2026, 6, 3, h1, 0),
        "duree_min": (h1 - h0) * 60,
    }


def test_pick_first_fitting_slot():
    slots = [_slot(9, 10), _slot(13, 16)]  # 60 min, 180 min
    got = pick_slot(slots, 120)
    assert got is not None
    assert got["debut"] == dt.datetime(2026, 6, 3, 13, 0)
    assert got["fin"] == dt.datetime(2026, 6, 3, 15, 0)  # 13h + 2h


def test_prefers_earliest_when_it_fits():
    slots = [_slot(9, 11), _slot(14, 18)]
    got = pick_slot(slots, 60)
    assert got["debut"] == dt.datetime(2026, 6, 3, 9, 0)


def test_no_slot_big_enough():
    assert pick_slot([_slot(9, 10)], 120) is None


def test_empty_slots():
    assert pick_slot([], 60) is None
