"""Fréquence de port (#77)."""

from __future__ import annotations

from app.services.garderobe.frequency import wear_buckets


def _items():
    return [
        {"id": "a", "portes": 0},
        {"id": "b", "portes": 0},
        {"id": "c", "portes": 1},
        {"id": "d", "portes": 12},
        {"id": "e", "portes": 3},
    ]


def test_never_worn():
    b = wear_buckets(_items())
    assert set(b["never_worn"]) == {"a", "b"}
    assert b["never_worn_count"] == 2
    assert b["total"] == 5


def test_least_and_most_worn_order():
    b = wear_buckets(_items(), top_n=2)
    assert b["least_worn"] == ["c", "e"]   # 1 puis 3
    assert b["most_worn"] == ["d", "e"]    # 12 puis 3


def test_empty():
    b = wear_buckets([])
    assert b == {"total": 0, "never_worn_count": 0, "never_worn": [], "least_worn": [], "most_worn": []}
