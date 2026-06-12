"""Tests TDD — snapshot + wellbeing + templates (#206, 207, 212, 222)."""

from __future__ import annotations

import datetime as dt
import json
import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.services.automatisations.snapshot import (
    build_daily_snapshot,
    get_recent_snapshots,
    get_snapshot,
    save_snapshot,
)
from app.services.automatisations.wellbeing import compute_wellbeing_score, _label_from_score
from app.services.automatisations.templates import get_templates, get_template


@pytest.fixture()
def session():
    from app.models import DailySnapshot  # ensure table registered
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


# ─── Snapshot ──────────────────────────────────────────────────────────────────

def test_build_snapshot_returns_dict(session):
    today = dt.date(2026, 6, 11)
    data = build_daily_snapshot(session, today)
    assert isinstance(data, dict)
    assert data["date"] == "2026-06-11"


def test_save_and_get_snapshot(session):
    today = dt.date(2026, 6, 11)
    snap = save_snapshot(session, today)
    assert snap.id is not None
    assert snap.date == today
    fetched = get_snapshot(session, today)
    assert fetched is not None
    assert fetched.id == snap.id


def test_save_snapshot_upserts(session):
    today = dt.date(2026, 6, 11)
    snap1 = save_snapshot(session, today)
    snap2 = save_snapshot(session, today)
    assert snap1.id == snap2.id  # même ligne, pas de doublon


def test_get_recent_snapshots(session):
    for offset in range(3):
        d = dt.date.today() - dt.timedelta(days=offset)
        save_snapshot(session, d)
    snaps = get_recent_snapshots(session, days=10)
    assert len(snaps) == 3


# ─── Wellbeing Score ───────────────────────────────────────────────────────────

def test_wellbeing_full_data():
    data = {
        "habitudes": {"pct": 100},
        "humeur": {"valeur": 9, "energie": 8},
        "sante": {"calories": 2100, "calories_cible": 2100},
        "entrainement": {"nb_seances": 1},
    }
    result = compute_wellbeing_score(data)
    assert result["score"] >= 85
    assert result["label"] in ["Excellente journée", "Bonne journée"]


def test_wellbeing_no_data():
    result = compute_wellbeing_score({})
    assert 0 <= result["score"] <= 100
    assert isinstance(result["label"], str)


def test_wellbeing_labels():
    assert _label_from_score(95) == "Excellente journée"
    assert _label_from_score(72) == "Bonne journée"
    assert _label_from_score(57) == "Journée correcte"
    assert _label_from_score(42) == "Journée difficile"
    assert _label_from_score(20) == "Journée compliquée"


def test_wellbeing_components_sum_to_score():
    data = {"habitudes": {"pct": 80}, "humeur": {"valeur": 7, "energie": 7}}
    result = compute_wellbeing_score(data)
    assert result["score"] == sum(result["components"].values())


# ─── Templates ─────────────────────────────────────────────────────────────────

def test_templates_exist():
    templates = get_templates()
    assert len(templates) >= 3
    for t in templates:
        assert "id" in t
        assert "name" in t
        assert "actions" in t


def test_get_template_by_id():
    tpl = get_template("semaine_type")
    assert tpl is not None
    assert tpl["trigger_type"] == "cron"


def test_get_template_unknown():
    assert get_template("inexistant") is None
