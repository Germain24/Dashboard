"""Tests TDD — kill switch global + journal d'audit des routines (#217)."""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.routines import Routine, RoutineRun
from app.models.scheduler import Notification
from app.services.automatisations import engine as eng
from app.services.automatisations.engine import (
    create_routine,
    execute_routine,
    get_routine_runs,
)


@pytest.fixture()
def session():
    e = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(e)
    with Session(e) as s:
        yield s


@pytest.fixture()
def kill_switch(monkeypatch):
    """Pilote le kill switch sans toucher au fichier de préférences réel."""
    state = {"on": False}
    monkeypatch.setattr(
        eng, "get_preferences",
        lambda: {"automatisations_kill_switch": state["on"]},
    )
    return state


def test_execution_logs_audit_entry(session, kill_switch):
    r = create_routine(session, name="Audit", actions=[{"type": "notify", "titre": "X", "message": "y"}])
    execute_routine(session, r.id)
    runs = session.exec(select(RoutineRun).where(RoutineRun.routine_id == r.id)).all()
    assert len(runs) == 1
    assert runs[0].status == "ok"
    assert runs[0].routine_name == "Audit"


def test_kill_switch_blocks_execution(session, kill_switch):
    kill_switch["on"] = True
    r = create_routine(session, name="Bloquée", actions=[{"type": "notify", "titre": "X", "message": "y"}])
    result = execute_routine(session, r.id)
    # Aucune action exécutée : pas de notification créée.
    notifs = session.exec(select(Notification).where(Notification.source == f"routine_{r.id}")).all()
    assert notifs == []
    # last_run_at NON mis à jour (la routine n'a pas tourné).
    assert session.get(Routine, r.id).last_run_at is None
    # Une entrée d'audit "blocked" est journalisée.
    runs = session.exec(select(RoutineRun).where(RoutineRun.routine_id == r.id)).all()
    assert len(runs) == 1
    assert runs[0].status == "blocked"
    assert "kill" in result.lower() or "bloqu" in result.lower()


def test_error_in_action_is_audited(session, kill_switch, monkeypatch):
    r = create_routine(session, name="Erreur", actions=[{"type": "job", "job_id": "x"}])
    # Force l'action job à lever.
    def boom(_):
        raise RuntimeError("boom")
    monkeypatch.setattr(eng, "_trigger_job_now", boom)
    execute_routine(session, r.id)
    runs = session.exec(select(RoutineRun).where(RoutineRun.routine_id == r.id)).all()
    assert len(runs) == 1
    assert runs[0].status == "error"
    assert "boom" in runs[0].detail


def test_get_routine_runs_recent_first(session, kill_switch):
    r = create_routine(session, name="Multi", actions=[])
    execute_routine(session, r.id)
    execute_routine(session, r.id)
    runs = get_routine_runs(session, limit=10)
    assert len(runs) == 2
    # Triés du plus récent au plus ancien.
    assert runs[0].id >= runs[1].id
