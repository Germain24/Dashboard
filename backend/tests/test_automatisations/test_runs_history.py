"""Tests TDD — file d'automatisations : ré-exécution + rollback (#216).

L'historique (RoutineRun) vient de #217. Ici on ajoute :
- rerun_run : ré-exécuter le run passé (re-lance la routine, nouveau RoutineRun).
- rollback_run : annule ce qui est RÉVERSIBLE (les notifications créées par le run).
  Les actions `job` ont des effets déjà appliqués ailleurs -> non réversibles, signalées.
"""

from __future__ import annotations

import json

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.routines import RoutineRun
from app.models.scheduler import Notification
from app.services.automatisations import engine as eng
from app.services.automatisations.engine import (
    create_routine,
    execute_routine,
    rerun_run,
    rollback_run,
)


@pytest.fixture()
def session():
    e = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(e)
    with Session(e) as s:
        yield s


@pytest.fixture(autouse=True)
def _no_kill_switch(monkeypatch):
    monkeypatch.setattr(eng, "get_preferences", lambda: {"automatisations_kill_switch": False})


def test_run_records_created_notification_ids(session):
    r = create_routine(session, name="Notif", actions=[{"type": "notify", "titre": "T", "message": "m"}])
    execute_routine(session, r.id)
    run = session.exec(select(RoutineRun).where(RoutineRun.routine_id == r.id)).one()
    created = json.loads(run.created_ids)
    assert len(created["notifications"]) == 1
    # l'id pointe sur une vraie notification
    assert session.get(Notification, created["notifications"][0]) is not None


def test_rerun_creates_a_new_run(session):
    r = create_routine(session, name="Re", actions=[{"type": "notify", "titre": "T", "message": "m"}])
    execute_routine(session, r.id)
    first = session.exec(select(RoutineRun).where(RoutineRun.routine_id == r.id)).one()
    rerun_run(session, first.id)
    runs = session.exec(select(RoutineRun).where(RoutineRun.routine_id == r.id)).all()
    assert len(runs) == 2  # le run d'origine + le nouveau
    # deux notifications créées au total (une par exécution)
    notifs = session.exec(select(Notification).where(Notification.source == f"routine_{r.id}")).all()
    assert len(notifs) == 2


def test_rollback_deletes_created_notifications(session):
    r = create_routine(session, name="Roll", actions=[{"type": "notify", "titre": "T", "message": "m"}])
    execute_routine(session, r.id)
    run = session.exec(select(RoutineRun).where(RoutineRun.routine_id == r.id)).one()
    nid = json.loads(run.created_ids)["notifications"][0]
    assert session.get(Notification, nid) is not None

    msg = rollback_run(session, run.id)
    assert session.get(Notification, nid) is None       # supprimée
    assert session.get(RoutineRun, run.id).rolled_back is True
    assert "1" in msg

    # idempotent : un 2e rollback ne casse rien
    assert "déjà" in rollback_run(session, run.id).lower()


def test_rollback_job_action_is_flagged_non_reversible(session, monkeypatch):
    monkeypatch.setattr(eng, "_trigger_job_now", lambda _: None)
    r = create_routine(session, name="Job", actions=[{"type": "job", "job_id": "daily_snapshot"}])
    execute_routine(session, r.id)
    run = session.exec(select(RoutineRun).where(RoutineRun.routine_id == r.id)).one()
    msg = rollback_run(session, run.id)
    assert "non réversible" in msg.lower() or "non reversible" in msg.lower()
    assert session.get(RoutineRun, run.id).rolled_back is True


def test_rerun_missing_run_raises(session):
    with pytest.raises(ValueError):
        rerun_run(session, 9999)
