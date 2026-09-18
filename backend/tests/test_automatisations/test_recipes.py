"""Tests TDD — recettes cross-module (#215)."""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.scheduler import Notification
from app.services.automatisations import engine as eng
from app.services.automatisations import recipes as rec


@pytest.fixture()
def session():
    e = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(e)
    with Session(e) as s:
        yield s


@pytest.fixture(autouse=True)
def no_kill(monkeypatch):
    monkeypatch.setattr(rec, "get_preferences", lambda: {"automatisations_kill_switch": False})
    # Les jobs ne tournent pas en test : on neutralise le déclencheur.
    monkeypatch.setattr(eng, "_trigger_job_now", lambda _job: None)


def test_get_recipes_lists_chains():
    recipes = rec.get_recipes()
    assert len(recipes) >= 3
    ids = {r["id"] for r in recipes}
    assert "preparer_semaine" in ids
    assert all("nb_actions" in r and r["nb_actions"] >= 1 for r in recipes)


def test_run_recipe_executes_actions(session):
    detail = rec.run_recipe(session, "preparer_semaine")
    assert "notif créée" in detail
    notifs = session.exec(
        select(Notification).where(Notification.source == "recipe_preparer_semaine")
    ).all()
    assert len(notifs) == 1  # la recette contient 1 action notify


def test_run_unknown_recipe_raises(session):
    with pytest.raises(ValueError):
        rec.run_recipe(session, "inconnue")


def test_kill_switch_blocks_recipe(session, monkeypatch):
    monkeypatch.setattr(rec, "get_preferences", lambda: {"automatisations_kill_switch": True})
    detail = rec.run_recipe(session, "bilan_jour")
    assert "bloqu" in detail.lower()
    notifs = session.exec(select(Notification)).all()
    assert notifs == []
