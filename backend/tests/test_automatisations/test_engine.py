"""Tests TDD — moteur de routines (#201)."""

from __future__ import annotations

import json
import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.routines import Routine
from app.models.scheduler import Notification, JobRun
from app.services.automatisations.engine import (
    create_routine,
    delete_routine,
    execute_routine,
    get_routine,
    get_routines,
    update_routine,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_create_and_get(session):
    r = create_routine(session, name="Test", trigger_type="cron", trigger_value="0 7 * * *")
    assert r.id is not None
    fetched = get_routine(session, r.id)
    assert fetched is not None
    assert fetched.name == "Test"


def test_list_routines(session):
    create_routine(session, name="A")
    create_routine(session, name="B")
    routines = get_routines(session)
    assert len(routines) == 2


def test_update_routine(session):
    r = create_routine(session, name="Old", enabled=True)
    updated = update_routine(session, r.id, {"enabled": False, "name": "New"})
    assert updated is not None
    assert updated.enabled is False
    assert updated.name == "New"


def test_delete_routine(session):
    r = create_routine(session, name="To delete")
    ok = delete_routine(session, r.id)
    assert ok is True
    assert get_routine(session, r.id) is None


def test_execute_notify_action(session):
    r = create_routine(
        session,
        name="Notif routine",
        actions=[{"type": "notify", "titre": "Test", "message": "Hello"}],
    )
    result = execute_routine(session, r.id)
    assert "notif créée" in result
    notifs = session.exec(
        select(Notification).where(Notification.source == f"routine_{r.id}")
    ).all()
    assert len(notifs) == 1
    assert notifs[0].titre == "Test"


def test_execute_updates_last_run_at(session):
    r = create_routine(session, name="Timer", actions=[])
    assert r.last_run_at is None
    execute_routine(session, r.id)
    updated = session.get(Routine, r.id)
    assert updated.last_run_at is not None


def test_execute_unknown_action_does_not_crash(session):
    r = create_routine(session, name="Unknown", actions=[{"type": "future_action"}])
    result = execute_routine(session, r.id)
    assert "future_action" in result


def test_execute_missing_routine_raises(session):
    with pytest.raises(ValueError):
        execute_routine(session, 9999)
