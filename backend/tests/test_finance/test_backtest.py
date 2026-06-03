"""Backtest buy-and-hold d'une allocation cible (cœur pur)."""

from app.services.finance.backtest import simulate_allocation


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
