"""Objectif d'épargne mensuel (#121)."""

from __future__ import annotations

from app.services.budget.savings import get_savings_goal, savings_progress, set_savings_goal


def test_get_default_zero(tmp_path):
    assert get_savings_goal(path=tmp_path / "g.json") == 0.0


def test_set_and_get(tmp_path):
    p = tmp_path / "g.json"
    assert set_savings_goal(500.0, path=p) == 500.0
    assert get_savings_goal(path=p) == 500.0


def test_set_clamps_negative(tmp_path):
    assert set_savings_goal(-50.0, path=tmp_path / "g.json") == 0.0


def test_progress():
    assert savings_progress(500.0, 250.0) == {"objectif": 500.0, "epargne": 250.0, "progress_pct": 50.0}
    # solde négatif -> épargne 0
    assert savings_progress(500.0, -100.0)["epargne"] == 0.0
    # objectif 0 -> pas de division
    assert savings_progress(0.0, 100.0)["progress_pct"] == 0.0
