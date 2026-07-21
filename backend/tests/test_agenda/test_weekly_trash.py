import datetime as dt

from app.services.agenda.events import create_event
from app.services.agenda.weekly_trash import (
    choose_free_slot,
    ensure_weekly_trash_reminder,
    source_id_for,
)


def test_choose_free_slot_prefers_sunday_evening():
    sunday = dt.date(2026, 7, 19)
    slot = choose_free_slot(sunday, [])
    assert slot == (
        dt.datetime(2026, 7, 19, 20, 30),
        dt.datetime(2026, 7, 19, 20, 45),
    )


def test_choose_free_slot_uses_next_preference_when_busy():
    sunday = dt.date(2026, 7, 19)
    events = [
        {
            "debut": dt.datetime(2026, 7, 19, 20, 0),
            "fin": dt.datetime(2026, 7, 19, 21, 0),
        }
    ]
    slot = choose_free_slot(sunday, events)
    assert slot is not None
    assert slot[0] == dt.datetime(2026, 7, 19, 18, 0)


def test_ensure_weekly_trash_reminder_is_idempotent(mem_session):
    sunday = dt.date(2026, 7, 19)
    first, created = ensure_weekly_trash_reminder(mem_session, sunday)
    second, created_again = ensure_weekly_trash_reminder(mem_session, sunday)

    assert created is True
    assert created_again is False
    assert first is not None and second is not None
    assert first.id == second.id
    assert first.source_id == source_id_for(sunday)
    assert first.debut == dt.datetime(2026, 7, 19, 20, 30)


def test_ensure_weekly_trash_reminder_avoids_calendar_conflicts(mem_session):
    sunday = dt.date(2026, 7, 19)
    create_event(
        mem_session,
        {
            "titre": "Occupation",
            "debut": dt.datetime(2026, 7, 19, 20, 0),
            "fin": dt.datetime(2026, 7, 19, 21, 0),
            "source": "manuel",
        },
    )

    event, created = ensure_weekly_trash_reminder(mem_session, sunday)

    assert created is True
    assert event is not None
    assert event.debut == dt.datetime(2026, 7, 19, 18, 0)
