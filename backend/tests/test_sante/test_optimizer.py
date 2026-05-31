"""Tests basiques de l'optimiseur SLSQP + sémantique MinQty (semi-continuous)."""

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
    out = dict(d)
    out["Protéines"] = out.pop("Proteines")
    return out


def test_returns_plan_for_reasonable_targets():
    df = _mini_catalog()
    plan, _ = optimize_nutrition(df, _t(_base_targets()), budget_max_daily=18.0)
    assert plan is not None
    assert len(plan) >= 1
    assert sum(it["Calories"] for it in plan) >= 2200 * 0.90
    assert sum(it["Protéines"] for it in plan) >= 110 * 0.90
    assert sum(it["Prix"] for it in plan) <= 18 * 1.05


def test_empty_catalog_fails_cleanly():
    plan, warning = optimize_nutrition(
        pd.DataFrame(),
        {"Calories": 2000, "Protéines": 100, "Lipides": 60, "Glucides": 200, "Poids_Corps": 51},
        budget_max_daily=10.0,
    )
    assert plan is None
    assert "vide" in warning.lower()


def test_minqty_is_purchase_minimum_when_included():
    """MinQty = seuil d'achat. Si l'aliment EST inclus, sa quantite doit
    etre >= MinQty (snap apres SLSQP). L'aliment peut aussi etre exclus."""
    df = _mini_catalog()
    df.loc["Brocoli", "MinQty"] = 50
    df.loc["Huile olive", "MinQty"] = 5
    plan, _ = optimize_nutrition(df, _t(_base_targets()), budget_max_daily=18.0)
    assert plan is not None
    by_name = {it["Aliment"]: it for it in plan}
    if "Brocoli" in by_name:
        assert by_name["Brocoli"]["Quantite_g"] >= 49.0
    if "Huile olive" in by_name:
        assert by_name["Huile olive"]["Quantite_g"] >= 4.5


def test_minqty_does_not_force_inclusion():
    """Avec un MinQty extreme (~400g) pour un aliment non essentiel, l'optimiseur
    doit pouvoir l'exclure (x=0) au lieu de forcer 400g qui casserait le plan.

    L'heuristique de snap met x a 0 si la solution continue est < MinQty/2."""
    df = _mini_catalog()
    df.loc["Brocoli", "MinQty"] = 400
    plan, _ = optimize_nutrition(df, _t(_base_targets()), budget_max_daily=18.0)
    assert plan is not None
    by_name = {it["Aliment"]: it for it in plan}
    if "Brocoli" in by_name:
        # Si SLSQP a juge le brocoli utile, on aura exactement 400g (MinQty=MaxQty)
        assert by_name["Brocoli"]["Quantite_g"] == pytest.approx(400.0, abs=1.0)
    # Sinon : brocoli absent, et le plan reste valide
    assert sum(it["Calories"] for it in plan) >= 2200 * 0.85


def test_minqty_units_format_is_respected():
    df = _mini_catalog()
    df.loc["Huile olive", "MinQty"] = 0.1  # 10g (format units)
    plan, _ = optimize_nutrition(df, _t(_base_targets()), budget_max_daily=18.0)
    assert plan is not None
    by_name = {it["Aliment"]: it for it in plan}
    if "Huile olive" in by_name:
        assert by_name["Huile olive"]["Quantite_g"] >= 9.5


def test_high_targets_still_work_with_minqty():
    """Regression : meme avec des cibles eleveees et des MinQty, on doit
    obtenir un plan (pas une 422). Test issu du bug rapporte par Germain :
    cibles 3672 kcal / 176g prot / budget 180 CAD."""
    df = _mini_catalog()
    df.loc["Riz blanc", "MinQty"] = 100
    df.loc["Huile olive", "MinQty"] = 10
    targets = _t(_base_targets())
    targets["Calories"] = 3672.0
    targets["Protéines"] = 176.0
    plan, warning = optimize_nutrition(df, targets, budget_max_daily=180.0)
    assert plan is not None, f"Plan attendu, got None (warning: {warning})"


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
