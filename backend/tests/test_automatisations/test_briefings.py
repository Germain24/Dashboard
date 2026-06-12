"""Tests TDD — briefings matin/soir (#203, #204)."""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.services.automatisations.briefing import build_morning_briefing, build_evening_recap


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_morning_briefing_returns_string(session):
    """Le briefing matin retourne toujours une chaîne non vide même sans données."""
    today = dt.date(2026, 6, 11)
    result = build_morning_briefing(session, today=today)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "mercredi 11 juin" in result.lower() or "11 juin" in result


def test_morning_briefing_includes_date(session):
    today = dt.date(2026, 6, 11)
    result = build_morning_briefing(session, today=today)
    assert "11 juin" in result


def test_morning_briefing_graceful_no_habits(session):
    """Sans habitudes, le briefing ne plante pas."""
    today = dt.date(2026, 1, 15)
    result = build_morning_briefing(session, today=today)
    assert isinstance(result, str)


def test_evening_recap_returns_string(session):
    today = dt.date(2026, 6, 11)
    result = build_evening_recap(session, today=today)
    assert isinstance(result, str)
    assert len(result) > 0


def test_evening_recap_includes_date(session):
    today = dt.date(2026, 6, 11)
    result = build_evening_recap(session, today=today)
    assert "11" in result and "juin" in result


def test_evening_recap_no_depenses(session):
    """Sans transactions, le récap signale aucune dépense."""
    today = dt.date(2026, 6, 11)
    result = build_evening_recap(session, today=today)
    assert "Aucune dépense" in result or "dépense" in result.lower()
