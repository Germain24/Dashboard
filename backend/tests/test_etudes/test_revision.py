"""Révision espacée SM-2 (#99)."""

from __future__ import annotations

import datetime as dt

import pytest

from app.services.etudes import revision


def test_schedule_failure_resets():
    r = revision.schedule(reps=5, ease=2.5, interval=30, quality=1)
    assert r["reps"] == 0
    assert r["interval"] == 1


def test_schedule_first_successes():
    r1 = revision.schedule(reps=0, ease=2.5, interval=0, quality=4)
    assert r1["interval"] == 1 and r1["reps"] == 1
    r2 = revision.schedule(reps=1, ease=2.5, interval=1, quality=4)
    assert r2["interval"] == 6 and r2["reps"] == 2


def test_schedule_grows_with_ease():
    r = revision.schedule(reps=2, ease=2.5, interval=6, quality=5)
    assert r["interval"] == round(6 * 2.5)
    assert r["ease"] >= 2.5


def test_ease_floor():
    r = revision.schedule(reps=3, ease=1.3, interval=10, quality=3)
    assert r["ease"] >= 1.3


def test_add_and_due(tmp_path):
    p = tmp_path / "rev.json"
    card = revision.add_card("2+2 ?", "4", cours_id=1, path=p, today=dt.date(2026, 6, 3))
    assert card["id"] == 1
    due = revision.due_cards(path=p, today=dt.date(2026, 6, 3))
    assert len(due) == 1  # due = aujourd'hui à la création


def test_review_pushes_due(tmp_path):
    p = tmp_path / "rev.json"
    revision.add_card("Q", "R", path=p)
    c = revision.review_card(1, quality=5, path=p, today=dt.date(2026, 6, 3))
    assert c["due"] == "2026-06-04"  # interval 1 après 1re réussite
    assert revision.due_cards(path=p, today=dt.date(2026, 6, 3)) == []


def test_add_requires_both_sides(tmp_path):
    with pytest.raises(ValueError):
        revision.add_card("recto", "  ", path=tmp_path / "rev.json")


def test_delete(tmp_path):
    p = tmp_path / "rev.json"
    revision.add_card("Q", "R", path=p)
    assert revision.delete_card(1, path=p) is True
    assert revision.delete_card(999, path=p) is False
