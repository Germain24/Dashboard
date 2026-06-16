"""Tests TDD — objectifs de vie inter-modules (#226)."""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.objectifs_vie import LifeGoal  # noqa: F401 (enregistre la table)
from app.services.automatisations.objectifs_vie import (
    compute_progress,
    create_goal,
    delete_goal,
    goal_with_progress,
    list_goals,
)


@pytest.fixture()
def session():
    e = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(e)
    with Session(e) as s:
        yield s


def _obj(label, metric, baseline, cible):
    return {"label": label, "metric": metric, "baseline": baseline, "cible": cible}


# ── compute_progress (pur) ────────────────────────────────────────────────────

def test_progress_increase():
    out = compute_progress([_obj("Épargne", "epargne", 0, 2000)], {"epargne": 500})
    assert out["objectifs"][0]["pct"] == 25.0
    assert out["objectifs"][0]["atteint"] is False
    assert out["pct_global"] == 25.0


def test_progress_decrease_weight_loss():
    # baseline 80 -> cible 75, courant 77 : (77-80)/(75-80)=0.6
    out = compute_progress([_obj("Poids", "poids", 80, 75)], {"poids": 77})
    assert out["objectifs"][0]["pct"] == 60.0


def test_progress_achieved_clamped_to_100():
    out = compute_progress([_obj("Épargne", "epargne", 0, 1000)], {"epargne": 1500})
    assert out["objectifs"][0]["pct"] == 100.0
    assert out["objectifs"][0]["atteint"] is True


def test_progress_missing_value_is_none():
    out = compute_progress([_obj("Poids", "poids", 80, 75)], {})
    assert out["objectifs"][0]["pct"] is None
    assert out["pct_global"] is None


def test_progress_baseline_equals_cible_is_none():
    out = compute_progress([_obj("X", "x", 50, 50)], {"x": 50})
    assert out["objectifs"][0]["pct"] is None


def test_pct_global_is_mean_of_known():
    objs = [_obj("A", "a", 0, 100), _obj("B", "b", 0, 100), _obj("C", "c", 0, 100)]
    out = compute_progress(objs, {"a": 100, "b": 0, "c": None})  # 100%, 0%, inconnu
    assert out["pct_global"] == 50.0  # moyenne de 100 et 0


# ── CRUD + intégration ────────────────────────────────────────────────────────

def test_crud_and_progress(session):
    g = create_goal(
        session, titre="Forme & épargne",
        objectifs=[_obj("Perdre 5 kg", "poids", 80, 75), _obj("Épargner 2000", "epargne", 0, 2000)],
    )
    assert len(list_goals(session)) == 1
    view = goal_with_progress(session, g, valeurs={"poids": 77, "epargne": 1000})
    assert view["titre"] == "Forme & épargne"
    assert view["objectifs"][0]["pct"] == 60.0
    assert view["objectifs"][1]["pct"] == 50.0
    assert view["pct_global"] == 55.0
    assert delete_goal(session, g.id) is True
    assert list_goals(session) == []
