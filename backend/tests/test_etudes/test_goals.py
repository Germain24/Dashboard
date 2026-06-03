"""Objectif d'heures d'étude hebdo (#95)."""

from __future__ import annotations

import pytest

from app.services.etudes import goals


def test_default_when_absent(tmp_path):
    assert goals.get_weekly_hours(path=tmp_path / "g.json") == goals.DEFAULT_WEEKLY_HOURS


def test_set_and_get(tmp_path):
    p = tmp_path / "g.json"
    goals.set_weekly_hours(15.5, path=p)
    assert goals.get_weekly_hours(path=p) == 15.5


def test_negative_rejected(tmp_path):
    with pytest.raises(ValueError):
        goals.set_weekly_hours(-1, path=tmp_path / "g.json")
