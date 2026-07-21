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


def test_morning_briefing_includes_calorie_objective(session):
    """La ligne « Objectif kcal/protéines » doit apparaître dès qu'un poids est connu.

    Régression : `calculate_daily_targets` renvoie un tuple `(base, compensé)` avec
    des clés capitalisées et accentuées (`Calories`, `Protéines`). Le briefing
    appelait `.get("calories")` dessus — AttributeError sur un tuple, avalée par le
    `except Exception: pass` du bloc. La ligne n'est donc jamais sortie depuis son
    introduction, sans aucune erreur visible.
    """
    from app.models.sante import MesureSante

    today = dt.date(2026, 6, 11)
    session.add(MesureSante(date=today - dt.timedelta(days=1), poids=57.0))
    session.commit()

    result = build_morning_briefing(session, today=today)

    assert "Objectif" in result, f"ligne objectif absente du briefing :\n{result}"
    assert "kcal" in result
    assert "protéines" in result
