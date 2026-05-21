"""Tests basiques de l'optimiseur SLSQP."""

import pandas as pd
import pytest

from app.services.sante.optimizer import optimize_nutrition


def _mini_catalog() -> pd.DataFrame:
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
    data = {
        "Poulet":      [1.2, 30.0, 5.0,   0.0,  165.0, 0.0] + [0.0] * (len(cols) - 6),
        "Riz blanc":   [0.3, 7.0,  0.5,  78.0,  350.0, 1.0] + [0.0] * (len(cols) - 6),
        "Brocoli":     [0.4, 3.0,  0.4,   7.0,   35.0, 3.0] + [0.0] * (len(cols) - 6),
        "Huile olive": [0.8, 0.0,  100.0, 0.0,  900.0, 0.0] + [0.0] * (len(cols) - 6),
    }
    df = pd.DataFrame.from_dict(data, orient="index", columns=cols)
    df["TotalSugars"] = 0.0
    return df


def _base_targets():
    return {
        "Calories": 2200.0, "Proteines": 110.0, "Lipides": 60.0,
        "Glucides": 280.0, "Fibres": 30.0,
        "Sodium_Max": 2000.0, "Cholesterol_Max": 300.0, "Sucres_Max": 50.0,
        "Prix_Max": 18.0, "Poids_Corps": 51.0,
    }


def _t(d):
    """Convertit Proteines -> Protéines (clé accentuée attendue par l'optimiseur)."""
    out = dict(d)
    out["Protéines"] = out.pop("Proteines")
    return out


def test_returns_plan_for_reasonable_targets():
    df = _mini_catalog()
    plan, warning = optimize_nutrition(df, _t(_base_targets()), budget_max_daily=18.0)
    assert plan is not None
    assert len(plan) >= 1
    total_cal = sum(it["Calories"] for it in plan)
    total_prot = sum(it["Protéines"] for it in plan)
    total_prix = sum(it["Prix"] for it in plan)
    assert total_cal >= 2200.0 * 0.95
    assert total_prot >= 110.0 * 0.95
    assert total_prix <= 18.0 * 1.05


def test_empty_catalog_fails_cleanly():
    plan, warning = optimize_nutrition(
        pd.DataFrame(),
        {"Calories": 2000, "Protéines": 100, "Lipides": 60, "Glucides": 200, "Poids_Corps": 51},
        budget_max_daily=10.0,
    )
    assert plan is None
    assert "vide" in warning.lower()


def test_minqty_grams_is_respected():
    """MinQty en grammes (>= 1) doit forcer la borne inferieure."""
    df = _mini_catalog()
    df.loc["Brocoli", "MinQty"] = 50      # 50g
    df.loc["Huile olive", "MinQty"] = 5   # 5g

    plan, _ = optimize_nutrition(df, _t(_base_targets()), budget_max_daily=18.0)
    assert plan is not None

    by_name = {it["Aliment"]: it for it in plan}
    assert "Brocoli" in by_name, "Brocoli absent malgre MinQty=50g"
    assert by_name["Brocoli"]["Quantite_g"] >= 49.0, (
        f"Brocoli a {by_name['Brocoli']['Quantite_g']:.1f}g (attendu >= 50g)"
    )
    assert "Huile olive" in by_name, "Huile olive absente malgre MinQty=5g"
    assert by_name["Huile olive"]["Quantite_g"] >= 4.5


def test_minqty_units_format_is_respected():
    """MinQty en unites (< 1) doit etre interprete comme deja en unites internes."""
    df = _mini_catalog()
    df.loc["Huile olive", "MinQty"] = 0.1  # 0.1 unite = 10g

    plan, _ = optimize_nutrition(df, _t(_base_targets()), budget_max_daily=18.0)
    assert plan is not None
    by_name = {it["Aliment"]: it for it in plan}
    assert by_name.get("Huile olive", {}).get("Quantite_g", 0) >= 9.5


def test_tight_budget_emits_warning_or_failure():
    df = _mini_catalog()
    targets = _t(_base_targets())
    targets["Calories"] = 3500.0
    targets["Protéines"] = 200.0
    targets["Prix_Max"] = 2.0
    targets["Poids_Corps"] = 70.0

    plan, warning = optimize_nutrition(df, targets, budget_max_daily=2.0)
    if plan is None:
        assert "budget" in warning.lower() or "erreur" in warning.lower()
    else:
        assert isinstance(warning, str)
