"""Tests TDD — webhooks entrants/sortants (#219).

Sortant : action `webhook` -> POST JSON sur une URL (envoi injectable, best-effort).
Entrant : POST /automatisations/webhooks/{token} -> exécute la routine dont
trigger_type="webhook" et trigger_value==token (respecte le kill switch).
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.routines import RoutineRun
from app.models.scheduler import Notification
from app.services.automatisations import engine as eng
from app.services.automatisations.engine import (
    create_routine,
    run_action_list,
    trigger_webhook,
)


@pytest.fixture()
def session():
    e = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(e)
    with Session(e) as s:
        yield s


@pytest.fixture(autouse=True)
def _no_kill(monkeypatch):
    monkeypatch.setattr(eng, "get_preferences", lambda: {"automatisations_kill_switch": False})


# ── Sortant ───────────────────────────────────────────────────────────────────

def test_webhook_action_calls_sender(session, monkeypatch):
    calls = []
    monkeypatch.setattr(eng, "_post_webhook", lambda url, payload: calls.append((url, payload)) or True)
    status, detail, created = run_action_list(
        session, [{"type": "webhook", "url": "https://example.com/hook"}], source="routine_1"
    )
    assert status == "ok"
    assert calls and calls[0][0] == "https://example.com/hook"
    assert created["webhooks"] == ["https://example.com/hook"]


def test_webhook_action_failure_is_reported_not_raised(session, monkeypatch):
    monkeypatch.setattr(eng, "_post_webhook", lambda url, payload: False)
    status, detail, created = run_action_list(
        session, [{"type": "webhook", "url": "ftp://bad"}], source="routine_1"
    )
    # échec d'envoi -> le run n'explose pas (best-effort), juste signalé
    assert status == "ok"
    assert "échou" in detail.lower() or "echou" in detail.lower()


def test_post_webhook_rejects_non_http_scheme():
    # garde-fou : pas de schéma exotique (file://, etc.)
    assert eng._post_webhook("file:///etc/passwd", {}) is False
    assert eng._post_webhook("", {}) is False


# ── Entrant ─────────────────────────────────────────────────────────────────--

def test_trigger_webhook_executes_routine(session):
    r = create_routine(
        session, name="Hook", trigger_type="webhook", trigger_value="secret-token-123",
        actions=[{"type": "notify", "titre": "via webhook", "message": "ok"}],
    )
    trigger_webhook(session, "secret-token-123")
    notifs = session.exec(select(Notification).where(Notification.source == f"routine_{r.id}")).all()
    assert len(notifs) == 1
    runs = session.exec(select(RoutineRun).where(RoutineRun.routine_id == r.id)).all()
    assert len(runs) == 1 and runs[0].status == "ok"


def test_trigger_webhook_unknown_token_raises(session):
    with pytest.raises(ValueError):
        trigger_webhook(session, "n-existe-pas")


def test_trigger_webhook_respects_kill_switch(session, monkeypatch):
    monkeypatch.setattr(eng, "get_preferences", lambda: {"automatisations_kill_switch": True})
    r = create_routine(
        session, name="Hook", trigger_type="webhook", trigger_value="tok",
        actions=[{"type": "notify", "titre": "x", "message": "y"}],
    )
    trigger_webhook(session, "tok")
    notifs = session.exec(select(Notification).where(Notification.source == f"routine_{r.id}")).all()
    assert notifs == []  # bloqué
    runs = session.exec(select(RoutineRun).where(RoutineRun.routine_id == r.id)).all()
    assert len(runs) == 1 and runs[0].status == "blocked"
