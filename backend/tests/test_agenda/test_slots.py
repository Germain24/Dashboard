"""Tests logique pure slots.py — aucune dépendance DB."""

import datetime as dt
import pytest

from app.services.agenda.slots import free_slots, _merge_intervals


DATE = dt.date(2026, 9, 7)  # Lundi quelconque


def dt_on(h: int, m: int = 0) -> dt.datetime:
    return dt.datetime(DATE.year, DATE.month, DATE.day, h, m)


# ── _merge_intervals ─────────────────────────────────────────────────────────

def test_merge_empty():
    assert _merge_intervals([]) == []


def test_merge_no_overlap():
    ivs = [(dt_on(9), dt_on(10)), (dt_on(11), dt_on(12))]
    merged = _merge_intervals(ivs)
    assert len(merged) == 2


def test_merge_overlap():
    ivs = [(dt_on(9), dt_on(11)), (dt_on(10), dt_on(12))]
    merged = _merge_intervals(ivs)
    assert len(merged) == 1
    assert merged[0] == (dt_on(9), dt_on(12))


def test_merge_adjacent():
    ivs = [(dt_on(9), dt_on(10)), (dt_on(10), dt_on(11))]
    merged = _merge_intervals(ivs)
    assert len(merged) == 1


# ── free_slots ────────────────────────────────────────────────────────────────

def test_free_slots_empty_day():
    """Journée sans événements → un seul slot (7h-23h)."""
    slots = free_slots(DATE, occupied=[], min_duration_min=60)
    assert len(slots) == 1
    assert slots[0]["debut"] == dt_on(7)
    assert slots[0]["fin"] == dt_on(23)
    assert slots[0]["duree_min"] == 16 * 60


def test_free_slots_morning_class():
    """Cours 9h-12h → slots avant (7h-9h) et après (12h-23h)."""
    occupied = [(dt_on(9), dt_on(12))]
    slots = free_slots(DATE, occupied, min_duration_min=60)
    assert len(slots) == 2
    assert slots[0]["debut"] == dt_on(7)
    assert slots[0]["fin"] == dt_on(9)
    assert slots[1]["debut"] == dt_on(12)
    assert slots[1]["fin"] == dt_on(23)


def test_free_slots_full_day():
    """Journée entière bloquée → aucun slot."""
    occupied = [(dt_on(7), dt_on(23))]
    slots = free_slots(DATE, occupied, min_duration_min=60)
    assert slots == []


def test_free_slots_min_duration_filters():
    """Trou de 30 min → exclu si min_duration=60."""
    occupied = [(dt_on(9), dt_on(12, 30)), (dt_on(13), dt_on(17))]
    slots_60 = free_slots(DATE, occupied, min_duration_min=60)
    slots_20 = free_slots(DATE, occupied, min_duration_min=20)
    # Trou 12h30-13h = 30 min → exclu à 60 min, inclus à 20 min
    trous_60 = {(s["debut"].hour, s["fin"].hour) for s in slots_60}
    assert (12, 13) not in {(s["debut"].hour, s["debut"].hour) for s in slots_60}
    assert len(slots_20) > len(slots_60)


def test_free_slots_overlap_events():
    """Deux blocs qui se chevauchent sont fusionnés correctement."""
    occupied = [(dt_on(9), dt_on(11)), (dt_on(10), dt_on(12))]
    slots = free_slots(DATE, occupied, min_duration_min=60)
    # Un seul bloc fusionné 9h-12h → slots 7h-9h et 12h-23h
    assert len(slots) == 2
    assert slots[0]["fin"] == dt_on(9)
    assert slots[1]["debut"] == dt_on(12)


def test_free_slots_custom_day_bounds():
    """day_start et day_end personnalisés."""
    slots = free_slots(DATE, occupied=[], min_duration_min=60, day_start_h=10, day_end_h=20)
    assert slots[0]["debut"] == dt_on(10)
    assert slots[0]["fin"] == dt_on(20)
    assert slots[0]["duree_min"] == 600
