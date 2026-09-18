"""The planner values only existing pantry quantities at a reduced rate."""
import numpy as np
import pytest

from app.services.sante.optimizer import _build_cost_functions


def _costs(stock, *, package_price=None, package_units=None):
    economic, cash = _build_cost_functions(
        np.array([2.0]),
        package_price_arr=(None if package_price is None else np.array([package_price])),
        package_units_arr=(None if package_units is None else np.array([package_units])),
        pantry_tiers=[stock],
    )
    return economic, cash


@pytest.mark.parametrize(
    ("quantity_units", "expected"),
    [(0.0, 0.0), (3.0, 3.0), (5.0, 5.0), (6.0, 7.0)],
)
def test_durable_stock_is_half_price_only_up_to_available_amount(quantity_units, expected):
    economic, cash = _costs([(5.0, 0.5)])
    assert economic(np.array([quantity_units])) == pytest.approx(expected)
    # No package metadata: only the portion beyond the 500 g stock is purchased.
    assert cash(np.array([quantity_units])) == pytest.approx(max(0.0, quantity_units - 5.0) * 2.0)


def test_perishable_stock_is_free_but_excess_returns_to_full_price():
    economic, cash = _costs([(5.0, 0.0)])
    assert economic(np.array([5.0])) == pytest.approx(0.0)
    assert economic(np.array([6.0])) == pytest.approx(2.0)
    assert cash(np.array([5.0])) == pytest.approx(0.0)
    assert cash(np.array([6.0])) == pytest.approx(2.0)


def test_package_checkout_applies_only_to_stock_deficit():
    economic, cash = _costs([(5.0, 0.5)], package_price=20.0, package_units=10.0)
    assert economic(np.array([6.0])) == pytest.approx(7.0)
    assert cash(np.array([5.0])) == pytest.approx(0.0)
    assert cash(np.array([6.0])) == pytest.approx(20.0, abs=0.01)


def test_optimizer_budget_uses_cash_needed_after_stock():
    import pandas as pd

    from app.services.sante.optimizer import optimize_nutrition

    df = pd.DataFrame.from_dict(
        {"A": [100, 8, 2, 10, 1.0, 40, 3]}, orient="index",
        columns=["Energie", "Proteines", "Lipides", "Glucides", "Prix", "VitC", "Fibres"],
    )
    df["MaxQty"] = 0.0
    df["MinQty"] = 0.0
    targets = {
        "Calories": 300.0, "Protéines": 20.0, "Lipides": 6.0,
        "Glucides": 30.0, "Poids_Corps": 60.0, "Prix_Max": 0.0,
        "VitC": 100.0, "Fibres": 10.0,
    }
    plan, warning = optimize_nutrition(
        df, targets, budget_max_daily=0.0,
        pantry_stock={"A": [{"available_g": 500.0, "cost_factor": 0.5}]},
    )
    assert plan is not None, warning
    assert sum(item["Quantite_g"] for item in plan) <= 500.0 + 1e-6
