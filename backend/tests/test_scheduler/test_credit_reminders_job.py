"""Tests job rappel mensuel score de crédit (#credit-reminder)."""

from __future__ import annotations

from sqlmodel import select

from app.models.scheduler import Notification
from app.services.scheduler.jobs import credit_reminders


def _notifications(session):
    return list(session.exec(select(Notification).where(Notification.source == "credit_reminder")).all())


def test_run_creates_one_notification_when_none_exists(mem_session, tmp_path, monkeypatch):
    from app.services.finance.credit import reminders as reminders_mod
    monkeypatch.setattr(reminders_mod, "reminded_file", lambda: tmp_path / "credit_score_reminded.json")

    msg = credit_reminders.run(mem_session)

    notifs = _notifications(mem_session)
    assert len(notifs) == 1
    assert "Rappel créé" in msg


def test_run_again_same_month_creates_no_additional_notification(mem_session, tmp_path, monkeypatch):
    from app.services.finance.credit import reminders as reminders_mod
    monkeypatch.setattr(reminders_mod, "reminded_file", lambda: tmp_path / "credit_score_reminded.json")

    credit_reminders.run(mem_session)
    msg = credit_reminders.run(mem_session)

    notifs = _notifications(mem_session)
    assert len(notifs) == 1
    # Branche sans action -> None (silencieux) : le runner ne notifie pas.
    assert msg is None


def test_run_suspended_in_vacation_mode(mem_session, tmp_path, monkeypatch):
    from app.services.finance.credit import reminders as reminders_mod
    monkeypatch.setattr(reminders_mod, "reminded_file", lambda: tmp_path / "credit_score_reminded.json")

    from app.services import settings as settings_mod
    monkeypatch.setattr(settings_mod, "get_preferences", lambda: {"mode_vacances": True})

    msg = credit_reminders.run(mem_session)

    assert _notifications(mem_session) == []
    # Mode vacances -> None : aucun bruit toutes les 15 min pendant l'absence.
    assert msg is None
