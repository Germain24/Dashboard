"""Backtest buy-and-hold d'une allocation cible (cœur pur)."""

import datetime as dt

from app.services.finance.backtest import simulate_allocation, simulate_walk_forward


def test_single_asset_doubles():
    r = simulate_allocation({"AAA": [100.0, 150.0, 200.0]}, {"AAA": 100.0})
    assert r["equity"][0] == 100.0
    assert r["equity"][-1] == 200.0
    assert r["rendement_pct"] == 100.0
    assert r["n_points"] == 3


def test_weighted_two_assets():
    # 50/50 : un qui double (+100%), un stable (0%) -> +50 % au total
    prices = {"AAA": [100.0, 200.0], "BBB": [50.0, 50.0]}
    r = simulate_allocation(prices, {"AAA": 50.0, "BBB": 50.0})
    assert r["equity"][-1] == 150.0
    assert r["rendement_pct"] == 50.0


def test_weights_renormalized():
    # poids 20/20 (somme 40) -> renormalisés à 50/50
    prices = {"AAA": [100.0, 200.0], "BBB": [50.0, 50.0]}
    r = simulate_allocation(prices, {"AAA": 20.0, "BBB": 20.0})
    assert r["equity"][-1] == 150.0


def test_empty_inputs():
    assert simulate_allocation({}, {})["equity"] == []
    assert simulate_allocation({"AAA": [100.0]}, {"BBB": 100.0})["equity"] == []


def test_walk_forward_never_uses_allocation_before_its_run_date():
    start = dt.date(2025, 1, 1)
    dates = [(start + dt.timedelta(days=i)).isoformat() for i in range(120)]
    prices = {"AAA": [100.0 + i for i in range(120)]}
    allocations = [{"date": dates[60], "weights": {"AAA": 100.0}}]

    result = simulate_walk_forward(dates, prices, allocations)

    assert result["dates"][0] == dates[60]
    assert result["n_rebalances"] == 1
    assert result["rendement_pct"] > 0


def test_walk_forward_rebalances_quarterly_and_charges_turnover_costs():
    start = dt.date(2025, 1, 1)
    dates = [(start + dt.timedelta(days=i)).isoformat() for i in range(200)]
    prices = {
        "AAA": [100.0 * (1.002 ** i) for i in range(200)],
        "BBB": [100.0 for _ in range(200)],
    }
    allocations = [
        {"date": dates[0], "weights": {"AAA": 100.0}},
        {"date": dates[30], "weights": {"BBB": 100.0}},  # trop tôt : ignoré
        {"date": dates[90], "weights": {"BBB": 100.0}},
    ]

    free = simulate_walk_forward(dates, prices, allocations, cost_bps=0.0)
    costly = simulate_walk_forward(dates, prices, allocations, cost_bps=100.0)

    assert free["n_rebalances"] == 2
    assert costly["n_rebalances"] == 2
    assert costly["turnover"] > 0
    assert costly["costs_pct"] > 0
    assert costly["rendement_pct"] < free["rendement_pct"]
