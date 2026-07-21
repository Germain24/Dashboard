"""Tests basiques de l'optimiseur SLSQP + sémantique MinQty (semi-continuous)."""

import numpy as np
import pandas as pd
import pytest

from app.services.sante.optimizer import diversity_penalty, optimize_nutrition


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


# ── Malus de diversité (#bug rapporté : "5g de courgette" — un aliment inclus
# pour un gain marginal minuscule, puis remonté à MinQty par le snap). ──────

def test_diversity_penalty_zero_when_nothing_included():
    assert diversity_penalty(np.zeros(3), eps=0.02) == 0.0


def test_diversity_penalty_half_at_eps():
    x = np.array([0.02, 0.0, 0.0])
    assert diversity_penalty(x, eps=0.02) == pytest.approx(0.5)


def test_diversity_penalty_saturates_near_one_for_large_quantity():
    x = np.array([2.0])  # 200g, très au-dessus de eps
    assert diversity_penalty(x, eps=0.02) > 0.98


def test_diversity_penalty_grows_with_number_of_foods():
    small = diversity_penalty(np.array([1.0]), eps=0.02)
    large = diversity_penalty(np.array([1.0, 1.0, 1.0]), eps=0.02)
    assert large == pytest.approx(3 * small)


def test_diversity_malus_reduces_marginal_filler_foods():
    """Avec un malus de diversité, l'optimiseur consolide sur MOINS d'aliments
    à faible valeur marginale plutôt que de saupoudrer une cible de couverture
    (ici Magnesium, presque entièrement à 0) sur de nombreux "fillers" quasi
    équivalents. Reproduit la dynamique du bug rapporté (« 5g de courgette ») :
    sans malus, le coût nul de chaque source additionnelle (prix négligeable,
    shortfall^4 toujours légèrement positif) encourage à en inclure beaucoup ;
    avec malus, chaque aliment actif a un coût fixe -> consolidation."""
    df = _mini_catalog()
    df.loc["Riz blanc", "Magnesium"] = 100.0
    df.loc["Poulet", "Magnesium"] = 25.0
    for i, mg in enumerate([8.0, 7.0, 6.0, 5.0, 4.0, 3.0]):
        name = f"Filler{i}"
        row = df.loc["Brocoli"].copy()
        row["Magnesium"] = mg
        row["Prix"] = 0.01
        df.loc[name] = row
    targets = _t(_base_targets())
    targets["Magnésium"] = 400.0

    import app.services.sante.optimizer as opt_mod

    plan_with_malus, _ = optimize_nutrition(df, targets, budget_max_daily=18.0)
    n_with = sum(1 for it in plan_with_malus if it["Aliment"].startswith("Filler"))

    old_weight = opt_mod.DIVERSITY_WEIGHT
    opt_mod.DIVERSITY_WEIGHT = 0.0
    try:
        plan_without_malus, _ = optimize_nutrition(df, targets, budget_max_daily=18.0)
    finally:
        opt_mod.DIVERSITY_WEIGHT = old_weight
    n_without = sum(1 for it in plan_without_malus if it["Aliment"].startswith("Filler"))

    assert n_without == 6            # sans malus : saupoudré sur tous les fillers
    assert n_with < n_without        # avec malus : nettement consolidé


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
