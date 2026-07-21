"""Tests TDD — objectifs de vie inter-modules (#226) + jalons datés (§5.4)."""

from __future__ import annotations

import datetime as dt
import json

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.objectifs_vie import LifeGoal  # noqa: F401 (enregistre la table)
from app.services.automatisations.objectifs_vie import (
    compute_progress,
    create_goal,
    delete_goal,
    goal_with_progress,
    jalon_statut,
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

# ── jalon_statut (pur) ────────────────────────────────────────────────────────

TODAY = dt.date(2026, 7, 20)


def test_jalon_atteint_prime_sur_la_date():
    assert jalon_statut(True, dt.date(2026, 1, 1), TODAY) == "atteint"
    assert jalon_statut(True, None, TODAY) == "atteint"


def test_jalon_date_passee_est_en_retard():
    assert jalon_statut(False, dt.date(2026, 7, 19), TODAY) == "en_retard"


def test_jalon_du_jour_nest_pas_encore_en_retard():
    """La journée n'est pas finie : l'échéance du jour reste « à venir »."""
    assert jalon_statut(False, TODAY, TODAY) == "a_venir"


def test_jalon_futur_est_a_venir():
    assert jalon_statut(False, dt.date(2026, 12, 31), TODAY) == "a_venir"


def test_jalon_sans_date_ne_peut_pas_etre_en_retard():
    assert jalon_statut(False, None, TODAY) == "a_venir"


# ── compute_progress + jalons datés ───────────────────────────────────────────

def _jalon(label, metric, baseline, cible, date=None):
    o = _obj(label, metric, baseline, cible)
    if date is not None:
        o["date"] = date
    return o


def test_jalons_sans_date_retrocompatibles():
    """Le JSON déjà stocké n'a pas de champ `date` : la progression doit
    continuer de marcher et aucun jalon ne peut être en retard."""
    out = compute_progress([_obj("Épargne", "epargne", 0, 2000)], {"epargne": 500},
                            today=TODAY)
    row = out["objectifs"][0]
    assert row["pct"] == 25.0          # progression inchangée
    assert row["date"] is None
    assert row["statut"] == "a_venir"
    assert out["jalons_en_retard"] == 0


def test_jalon_date_passee_non_atteint_est_en_retard():
    out = compute_progress(
        [_jalon("Épargne", "epargne", 0, 2000, "2026-06-01")], {"epargne": 500},
        today=TODAY,
    )
    assert out["objectifs"][0]["date"] == "2026-06-01"
    assert out["objectifs"][0]["statut"] == "en_retard"
    assert out["jalons_en_retard"] == 1


def test_jalon_atteint_avant_lecheance_nest_pas_en_retard():
    out = compute_progress(
        [_jalon("Épargne", "epargne", 0, 1000, "2026-06-01")], {"epargne": 1500},
        today=TODAY,
    )
    assert out["objectifs"][0]["statut"] == "atteint"
    assert out["jalons_en_retard"] == 0


def test_jalon_sans_valeur_courante_et_echeance_depassee_est_en_retard():
    """Métrique non résolue : on ne sait pas si c'est atteint, mais la date
    est dépassée — le signaler vaut mieux que de le taire."""
    out = compute_progress(
        [_jalon("Poids", "poids", 80, 75, "2026-06-01")], {}, today=TODAY,
    )
    assert out["objectifs"][0]["pct"] is None
    assert out["objectifs"][0]["statut"] == "en_retard"


def test_jalon_date_illisible_traitee_comme_absente():
    out = compute_progress(
        [_jalon("X", "epargne", 0, 100, "bientôt")], {"epargne": 0}, today=TODAY,
    )
    assert out["objectifs"][0]["date"] is None
    assert out["objectifs"][0]["statut"] == "a_venir"


def test_jalons_melanges_dates_et_non_dates():
    out = compute_progress(
        [
            _jalon("A", "a", 0, 100, "2026-06-01"),
            _obj("B", "b", 0, 100),
            _jalon("C", "c", 0, 100, "2026-12-01"),
        ],
        {"a": 0, "b": 0, "c": 0}, today=TODAY,
    )
    assert [o["statut"] for o in out["objectifs"]] == ["en_retard", "a_venir", "a_venir"]
    assert out["jalons_en_retard"] == 1


# ── CRUD + intégration ────────────────────────────────────────────────────────

def test_goal_stocke_en_legacy_reste_lisible(session):
    """Objectif écrit avant les jalons datés (aucun champ `date` en base)."""
    goal = LifeGoal(titre="Ancien", objectifs=json.dumps([
        {"label": "Épargner 2000", "metric": "epargne", "baseline": 0, "cible": 2000},
    ]))
    session.add(goal)
    session.commit()
    session.refresh(goal)

    view = goal_with_progress(session, goal, valeurs={"epargne": 1000})
    assert view["objectifs"][0]["pct"] == 50.0
    assert view["objectifs"][0]["date"] is None
    assert view["objectifs"][0]["statut"] == "a_venir"
    assert view["jalons_en_retard"] == 0


def test_create_goal_conserve_les_dates_de_jalon(session):
    g = create_goal(session, titre="Forme & épargne", objectifs=[
        _jalon("Perdre 5 kg", "poids", 80, 75, "2026-06-01"),
    ])
    view = goal_with_progress(session, g, valeurs={"poids": 79})
    assert view["objectifs"][0]["date"] == "2026-06-01"
    assert view["objectifs"][0]["statut"] == "en_retard"
    assert view["jalons_en_retard"] == 1


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
