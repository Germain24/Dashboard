"""Tests objectif annuel de lecture (#151)."""

import pytest

from app.services.livres.goals import (
    DEFAULT_ANNUAL_GOAL,
    get_annual_goal,
    set_annual_goal,
    goal_progress,
)


def test_default_goal_when_absent(tmp_path):
    assert get_annual_goal(path=tmp_path / "g.json") == DEFAULT_ANNUAL_GOAL


def test_set_and_get(tmp_path):
    p = tmp_path / "g.json"
    set_annual_goal(24, path=p)
    assert get_annual_goal(path=p) == 24


def test_negative_goal_rejected(tmp_path):
    with pytest.raises(ValueError):
        set_annual_goal(-1, path=tmp_path / "g.json")


def test_goal_progress_partial():
    p = goal_progress(6, 12)
    assert p["pct"] == 50.0
    assert p["atteint"] is False
    assert p["restant"] == 6


def test_goal_progress_reached():
    p = goal_progress(15, 12)
    assert p["atteint"] is True
    assert p["pct"] == 100.0
    assert p["restant"] == 0


def test_goal_progress_zero_goal():
    p = goal_progress(3, 0)
    assert p["pct"] == 0.0
    assert p["atteint"] is False
