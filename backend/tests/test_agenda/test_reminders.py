"""Rappels d'événements (#85)."""

from __future__ import annotations

import datetime as dt

from app.services.agenda.reminders import (
    due_events,
    load_reminded,
    reminder_key,
    save_reminded,
)


def _ev(titre, h, m=0):
    return {"titre": titre, "debut": dt.datetime(2026, 6, 3, h, m)}


def test_due_events_window():
    now = dt.datetime(2026, 6, 3, 9, 0)
    events = [_ev("bientot", 9, 20), _ev("trop tard", 10, 0), _ev("passe", 8, 30)]
    due = due_events(events, now, lookahead_min=30)
    assert [e["titre"] for e in due] == ["bientot"]


def test_due_events_excludes_now_itself():
    now = dt.datetime(2026, 6, 3, 9, 0)
    # un événement pile à `now` n'est pas "à venir"
    assert due_events([_ev("pile", 9, 0)], now) == []


def test_reminder_key_stable():
    k1 = reminder_key("Cours", dt.datetime(2026, 6, 3, 9, 0))
    k2 = reminder_key("Cours", dt.datetime(2026, 6, 3, 9, 0))
    assert k1 == k2
    assert "Cours" in k1


def test_reminded_store_roundtrip(tmp_path):
    p = tmp_path / "reminded.json"
    assert load_reminded(path=p) == set()
    save_reminded({"a", "b"}, path=p)
    assert load_reminded(path=p) == {"a", "b"}


def test_reminded_store_trims(tmp_path):
    p = tmp_path / "reminded.json"
    keys = {f"2026-06-03T{h:02d}:00|x" for h in range(10)}
    save_reminded(keys, path=p, keep=3)
    assert len(load_reminded(path=p)) == 3
