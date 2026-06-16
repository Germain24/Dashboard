"""Tests TDD — budget d'énergie personnelle (#232)."""

from __future__ import annotations

from app.services.automatisations.energy import compute_energy_budget


def test_capacity_from_energie():
    out = compute_energy_budget(energie=8, activities=[])
    assert out["capacite"] == 80
    assert out["cout_prevu"] == 0
    assert out["restant"] == 80
    assert out["statut"] == "ok"


def test_default_capacity_without_energie():
    assert compute_energy_budget(activities=[])["capacite"] == 60


def test_sleep_bonus_and_malus():
    assert compute_energy_budget(energie=6, sleep_h=8, activities=[])["capacite"] == 70   # +10
    assert compute_energy_budget(energie=6, sleep_h=5, activities=[])["capacite"] == 45   # -15


def test_cost_by_category():
    # 2 h de cours (12/h) + 1 h de sport (15/h) = 24 + 15 = 39
    acts = [{"categorie": "cours", "duree_min": 120}, {"categorie": "sport", "duree_min": 60}]
    out = compute_energy_budget(energie=10, activities=acts)
    assert out["cout_prevu"] == 39
    assert out["restant"] == 100 - 39


def test_status_thresholds():
    assert compute_energy_budget(energie=3, activities=[{"categorie": "cours", "duree_min": 120}])["statut"] in ("serré", "dépassé")
    over = compute_energy_budget(energie=2, activities=[{"categorie": "sport", "duree_min": 300}])
    assert over["restant"] < 0 and over["statut"] == "dépassé"


def test_unknown_category_uses_default_cost():
    out = compute_energy_budget(energie=10, activities=[{"categorie": "autre", "duree_min": 60}])
    assert out["cout_prevu"] == 6
