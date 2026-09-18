import numpy as np
import pandas as pd
import pytest

from app.services.sante.optimizer import optimize_nutrition


def _mini_df():
    """Deux aliments : 'Cher' riche en VitD mais coûteux, 'Pas cher' générique."""
    cols = ["Energie", "Proteines", "Lipides", "Glucides", "Prix", "VitD", "Fibres"]
    data = {
        "Cher":      [100.0, 8.0, 2.0, 10.0, 5.0, 40.0, 2.0],
        "Pas cher":  [100.0, 8.0, 2.0, 10.0, 0.5, 0.0, 2.0],
    }
    df = pd.DataFrame.from_dict(data, orient="index", columns=cols)
    df["MaxQty"] = 0.0
    df["MinQty"] = 0.0
    return df


def _targets():
    return {
        "Calories": 300.0, "Protéines": 20.0, "Lipides": 6.0, "Glucides": 30.0,
        "Poids_Corps": 60.0, "Prix_Max": 30.0,
        "VitD": 15.0, "Fibres": 10.0,
    }


def test_default_price_weight_preserves_behaviour():
    df, t = _mini_df(), _targets()
    plan_a, _ = optimize_nutrition(df, t, budget_max_daily=30.0, seed=1)
    plan_b, _ = optimize_nutrition(df, t, budget_max_daily=30.0, seed=1, price_weight=0.001)
    grams = lambda p: {it["Aliment"]: round(it["Quantite_g"], 3) for it in p}
    assert grams(plan_a) == grams(plan_b)


def test_higher_price_weight_shifts_toward_cheaper_food():
    df, t = _mini_df(), _targets()
    cheap = lambda p: sum(it["Quantite_g"] for it in p if it["Aliment"] == "Pas cher")
    low = optimize_nutrition(df, t, budget_max_daily=30.0, price_weight=0.001)[0]
    high = optimize_nutrition(df, t, budget_max_daily=30.0, price_weight=2.0)[0]
    assert cheap(high) >= cheap(low) - 1e-5


def test_micro_weight_mult_forces_expensive_micro():
    df, t = _mini_df(), _targets()
    vitd = lambda p: sum(it["Quantite_g"] for it in p if it["Aliment"] == "Cher")
    base = optimize_nutrition(df, t, budget_max_daily=30.0, price_weight=1.0)[0]
    forced = optimize_nutrition(df, t, budget_max_daily=30.0, price_weight=1.0,
                                micro_weight_mult={"VitD": 8.0})[0]
    assert vitd(forced) >= vitd(base) - 1e-5
