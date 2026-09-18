import datetime as dt

from sqlmodel import select

from app.models.agenda import Evenement
from app.services.agenda.events import create_event
from app.services.agenda.housekeeping import (
    choose_free_slot,
    ensure_housekeeping_events,
)


def test_choose_slot_prefers_next_afternoon_over_same_day_morning():
    monday = dt.date(2026, 8, 3)
    events = [{
        "debut": dt.datetime(2026, 8, 3, 13, 30),
        "fin": dt.datetime(2026, 8, 3, 17, 0),
    }]
    assert choose_free_slot(monday, monday + dt.timedelta(days=1), events) == (
        dt.datetime(2026, 8, 4, 14, 0),
        dt.datetime(2026, 8, 4, 16, 0),
    )


def test_creates_monthly_then_weekly_without_overlap(mem_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.agenda.housekeeping._moment_preference", lambda: "aprem"
    )
    result = ensure_housekeeping_events(mem_session, dt.date(2026, 8, 3))
    events = list(mem_session.exec(select(Evenement).order_by(Evenement.debut)).all())

    assert len(result["created"]) == 2
    assert len(events) == 2
    assert events[0].debut == dt.datetime(2026, 8, 3, 14, 0)
    assert events[1].debut == dt.datetime(2026, 8, 4, 14, 0)
    assert {event.source_id for event in events} == {
        "housekeeping:bedroom:2026-08",
        "housekeeping:laundry:2026-W32",
    }


def test_is_idempotent_for_same_week_and_month(mem_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.agenda.housekeeping._moment_preference", lambda: "aprem"
    )
    ensure_housekeeping_events(mem_session, dt.date(2026, 8, 3))
    second = ensure_housekeeping_events(mem_session, dt.date(2026, 8, 5))

    assert second["created"] == []
    assert len(second["existing"]) == 2
    assert len(list(mem_session.exec(select(Evenement)).all())) == 2


def test_retries_unplaced_chore_later(mem_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.agenda.housekeeping._moment_preference", lambda: "aprem"
    )
    monday = dt.date(2026, 8, 3)
    for offset in range(29):
        day = monday + dt.timedelta(days=offset)
        create_event(mem_session, {
            "titre": "Occupé",
            "debut": dt.datetime.combine(day, dt.time(7, 0)),
            "fin": dt.datetime.combine(day, dt.time(23, 0)),
            "source": "manuel",
        })

    result = ensure_housekeeping_events(mem_session, monday)
    assert result["created"] == []
    assert len(result["unplaced"]) == 2
