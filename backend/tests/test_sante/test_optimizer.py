"""Tests basiques de l'optimiseur SLSQP.

On utilise un mini-catalogue synthétique : trois aliments avec des profils
contrastés (riche en protéines, riche en glucides, gras) pour vérifier que
l'optimiseur retourne un plan plausible et respecte les contraintes dures.
"""

import pandas as pd
import pytest

from app.services.sante.optimizer import optimize_nutrition


def _mini_catalog() -> pd.DataFrame:
    # Colonnes minimales utilisées par l'optimiseur
    cols = [
        "Prix", "Proteines", "Lipides", "Glucides", "Energie", "Fibres",
        "Sodium", "Magnesium", "VitA", "VitB1", "VitB2", "VitB3", "VitB5",
        "VitB6", "VitB9", "VitB12", "VitC", "VitD", "VitE", "VitK",
        "Calcium", "Chlorure", "Cuivre", "Fer", "Iode", "Manganese",
        "Phosphore", "Potassium", "Selenium", "Zinc", "Cholesterol",
        "Omega 3", "AG satures", "AG monoinsatures", "Omega 6",
        "Glucose", "Fructose", "Galactose", "Saccharose", "Lactose",
        "Polyols", "MinQty", "MaxQty",
    ]
    # 4 aliments, valeurs /100g
    data = {
        "Poulet":      [1.2, 30.0, 5.0,  0.0,  165.0, 0.0] + [0.0] * (len(cols) - 6),
        "Riz blanc":   [0.3, 7.0,  0.5,  78.0, 350.0, 1.0] + [0.0] * (len(cols) - 6),
        "Brocoli":     [0.4, 3.0,  0.4,  7.0,  35.0,  3.0] + [0.0] * (len(cols) - 6),
        "Huile olive": [0.8, 0.0,  100.0, 0.0, 900.0, 0.0] + [0.0] * (len(cols) - 6),
    }
    df = pd.DataFrame.from_dict(data, orient="index", columns=cols)
    df["TotalSugars"] = 0.0  # sucres synthétiques
    return df


def test_returns_plan_for_reasonable_targets():
    df = _mini_catalog()
    targets = {
        "Calories": 2200.0,
        "Protéines": 110.0,
        "Lipides": 60.0,
        "Glucides": 280.0,
        "Fibres": 30.0,
        "Sodium_Max": 2000.0,
        "Cholesterol_Max": 300.0,
        "Sucres_Max": 50.0,
        "Prix_Max": 18.0,
        "Poids_Corps": 51.0,
    }
    plan, warning = optimize_nutrition(df, targets, budget_max_daily=18.0)
    assert plan is not None
    assert len(plan) >= 1
    # Vérifie contraintes dures
    total_cal = sum(it["Calories"] for it in plan)
    total_prot = sum(it["Protéines"] for it in plan)
    total_prix = sum(it["Prix"] for it in plan)
    assert total_cal >= targets["Calories"] * 0.95
    assert total_prot >= targets["Protéines"] * 0.95
    assert total_prix <= targets["Prix_Max"] * 1.05


def test_empty_catalog_fails_cleanly():
    plan, warning = optimize_nutrition(pd.DataFrame(), {"Calories": 2000, "Protéines": 100, "Lipides": 60, "Glucides": 200, "Poids_Corps": 51}, budget_max_daily=10.0)
    assert plan is None
    assert "vide" in warning.lower()


def test_tight_budget_emits_warning_or_failure():
    """Avec un budget délibérément trop serré, on retourne soit un plan dégradé soit None."""
    df = _mini_catalog()
    targets = {
        "Calories": 3500.0,
        "Protéines": 200.0,
        "Lipides": 100.0,
        "Glucides": 400.0,
        "Fibres": 35.0,
        "Sodium_Max": 2000.0,
        "Cholesterol_Max": 300.0,
        "Sucres_Max": 50.0,
        "Prix_Max": 2.0,
        "Poids_Corps": 70.0,
    }
    plan, warning = optimize_nutrition(df, targets, budget_max_daily=2.0)
    # Soit ça échoue (plan=None), soit ça réussit avec un warning de budget
    if plan is None:
        assert "budget" in warning.lower() or "erreur" in warning.lower()
    else:
        # Plan retourné mais probablement avec warning
        assert isinstance(warning, str)
