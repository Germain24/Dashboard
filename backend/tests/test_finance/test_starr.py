"""STARR / CVaR : mesure des grosses chutes."""

import numpy as np
import pytest


def test_portfolio_cvar_is_mean_of_worst_tail():
    from app.services.finance.buffett.starr import portfolio_cvar
    # 100 rendements : -10% (les 5 pires), reste +1%
    r = np.array([-0.10] * 5 + [0.01] * 95)
    # CVaR 5% = moyenne des 5 pires = -(-0.10) = 0.10
    assert abs(portfolio_cvar(r, alpha=0.05) - 0.10) < 1e-9


def test_portfolio_cvar_does_not_dilute_losses_with_ties_at_the_quantile():
    from app.services.finance.buffett.starr import portfolio_cvar

    returns = np.array([-0.20] + [0.0] * 99)
    assert portfolio_cvar(returns, alpha=0.05) == pytest.approx(0.04)


@pytest.mark.parametrize("n_sim", [71, 100, 103])
def test_scalar_and_batch_starr_share_the_same_empirical_tail(n_sim):
    from app.services.finance.buffett.starr import neg_starr, neg_starr_batch

    simulation = np.column_stack([
        np.array([-0.20] + [0.0] * (n_sim - 1)),
        np.full(n_sim, -0.002),
    ])
    weights = np.array([[1.0, 0.3], [0.0, 0.7]])
    means = np.array([0.001, 0.0005])
    batch = neg_starr_batch(weights, simulation, means)
    scalar = [neg_starr(weights[:, i], simulation, means) for i in range(2)]
    np.testing.assert_allclose(batch, scalar, rtol=1e-12)


def test_cvar_penalises_fat_left_tail():
    """Deux séries de même moyenne ; celle avec une grosse chute a un CVaR plus élevé."""
    from app.services.finance.buffett.starr import portfolio_cvar
    calme = np.array([0.005, 0.004, 0.006, 0.005, -0.003] * 20)
    krach = np.array([0.02, 0.02, 0.02, 0.02, -0.40] * 20)  # même moyenne ~ +0.001/j
    assert portfolio_cvar(krach, 0.05) > portfolio_cvar(calme, 0.05)


def test_simulate_scenarios_shape_and_finite():
    from app.services.finance.buffett.starr import simulate_scenarios
    rng = np.random.default_rng(0)
    R = rng.normal(0.0005, 0.02, (400, 4))
    sim = simulate_scenarios(R, n_sim=2000, seed=1)
    assert sim.shape == (2000, 4)
    assert np.isfinite(sim).all()


def test_simulate_small_sample_falls_back_to_bootstrap():
    from app.services.finance.buffett.starr import simulate_scenarios
    R = np.array([[0.01, 0.02], [-0.01, 0.0], [0.005, -0.01]])  # 3 obs -> bootstrap
    sim = simulate_scenarios(R, n_sim=500, seed=1)
    assert sim.shape == (500, 2)
    # chaque ligne simulée est une ligne réelle (bootstrap)
    assert all(any(np.allclose(s, row) for row in R) for s in sim[:20])


def test_regime_windows_use_1y_3y_5y_weights_when_history_is_available():
    from app.services.finance.buffett.starr import resolve_regime_windows

    regimes = resolve_regime_windows(1260)

    assert [r["label"] for r in regimes] == ["1y", "3y", "5y"]
    assert [r["observations"] for r in regimes] == [252, 756, 1260]
    assert [r["weight"] for r in regimes] == [0.25, 0.50, 0.25]


def test_missing_5y_window_is_redistributed_to_1y_and_3y():
    from app.services.finance.buffett.starr import resolve_regime_windows

    regimes = resolve_regime_windows(756)

    assert [r["label"] for r in regimes] == ["1y", "3y"]
    assert regimes[0]["weight"] == pytest.approx(1 / 3)
    assert regimes[1]["weight"] == pytest.approx(2 / 3)


def test_regime_simulation_keeps_total_budget_and_slices_each_window(monkeypatch):
    from app.services.finance.buffett import starr

    calls = []

    def fake_simulate(values, n_sim, seed):
        calls.append((len(values), n_sim, seed))
        return np.full((n_sim, values.shape[1]), float(len(values)))

    monkeypatch.setattr(starr, "simulate_scenarios", fake_simulate)
    R = np.zeros((1260, 3))
    simulated, diagnostics = starr.simulate_regime_scenarios(
        R, n_sim=100, seed=7, stress_weight=0.0
    )

    assert simulated.shape == (100, 3)
    assert calls == [(252, 25, 7), (756, 50, 1016), (1260, 25, 2025)]
    assert sum(w["n_sim"] for w in diagnostics["windows"]) == 100


def test_search_sample_preserves_regime_mixture_instead_of_using_prefix():
    from app.services.finance.buffett.starr import stratified_scenario_indices

    diagnostics = {
        "windows": [
            {"label": "1y", "n_sim": 6000},
            {"label": "3y", "n_sim": 12000},
            {"label": "stress", "n_sim": 2000},
        ]
    }
    indices, counts = stratified_scenario_indices(diagnostics, 8000, seed=7)

    assert len(indices) == len(set(indices)) == 8000
    assert counts == {"1y": 2400, "3y": 4800, "stress": 800}
    assert int((indices < 6000).sum()) == 2400
    assert int(((indices >= 6000) & (indices < 18000)).sum()) == 4800
    assert int((indices >= 18000).sum()) == 800


def test_stratified_sample_distributes_one_place_per_largest_remainder():
    from app.services.finance.buffett.starr import stratified_scenario_indices

    diagnostics = {
        "windows": [{"label": label, "n_sim": 100} for label in ("1y", "3y", "stress")]
    }
    indices, counts = stratified_scenario_indices(diagnostics, 5, seed=7)

    assert len(set(indices)) == 5
    assert counts == {"1y": 2, "3y": 2, "stress": 1}


def test_correlation_stability_flags_recent_regime_shift():
    from app.services.finance.buffett.starr import correlation_stability_diagnostics

    rng = np.random.default_rng(18)
    first = rng.normal(size=(1008, 2))
    recent_x = rng.normal(size=252)
    recent = np.column_stack([recent_x, recent_x])
    R = np.vstack([first, recent])

    diagnostics = correlation_stability_diagnostics(R, ["META", "NVDA"])

    assert diagnostics["available"] is True
    assert diagnostics["n_pairs"] == 1
    assert diagnostics["major_shift_pairs"] == 1
    pair = diagnostics["top_pairs"][0]
    assert pair["ticker_a"] == "META"
    assert pair["ticker_b"] == "NVDA"
    assert pair["correlations"]["1y"] == pytest.approx(1.0)
    assert pair["max_delta"] > 0.5


def test_shrink_correlation_reduces_extremes_and_preserves_diagonal():
    from app.services.finance.buffett.starr import shrink_correlation

    corr = np.array([[1.0, 0.95, 0.10], [0.95, 1.0, 0.20], [0.10, 0.20, 1.0]])
    shrunk = shrink_correlation(corr, intensity=0.50)

    assert np.allclose(np.diag(shrunk), 1.0)
    assert shrunk[0, 1] < corr[0, 1]
    assert shrunk[0, 2] > corr[0, 2]
    assert np.allclose(shrunk, shrunk.T)


def test_stress_scenarios_sample_tail_and_amplify_losses():
    from app.services.finance.buffett.starr import simulate_stress_scenarios

    rng = np.random.default_rng(31)
    factor = rng.normal(0.0002, 0.01, 400)
    returns = np.column_stack([
        factor + rng.normal(0, 0.003, 400),
        factor + rng.normal(0, 0.003, 400),
        -0.3 * factor + rng.normal(0, 0.003, 400),
    ])
    stress = simulate_stress_scenarios(
        returns, n_sim=500, seed=4, vol_multiplier=2.0, target_correlation=0.85
    )

    assert stress.shape == (500, 3)
    assert np.isfinite(stress).all()
    assert stress.mean(axis=1).mean() < returns.mean(axis=1).mean()
    assert np.corrcoef(stress[:, 0], stress[:, 1])[0, 1] > 0.5


def test_neg_starr_finite_and_prefers_low_tail():
    from app.services.finance.buffett.starr import neg_starr
    rng = np.random.default_rng(3)
    n_sim = 5000
    # actif 0 : stable ; actif 1 : même moyenne mais chutes brutales
    a0 = rng.normal(0.0008, 0.01, n_sim)
    a1 = np.where(rng.random(n_sim) < 0.04, -0.25, 0.0008 + 0.012)
    sim = np.column_stack([a0, a1])
    mean_daily = sim.mean(axis=0)
    s0 = neg_starr(np.array([1.0, 0.0]), sim, mean_daily, 0.05)
    s1 = neg_starr(np.array([0.0, 1.0]), sim, mean_daily, 0.05)
    assert np.isfinite(s0) and np.isfinite(s1)
    assert s0 < s1   # -STARR plus petit = meilleur STARR pour l'actif stable
def test_simulation_sanitizer_prevents_float32_overflow():
    from app.services.finance.buffett.starr import sanitize_simulated_returns

    clean, diagnostics = sanitize_simulated_returns(
        np.array([[1e300, -1e300, np.nan, np.inf, -np.inf, 0.02]])
    )

    assert np.isfinite(clean).all()
    assert np.isfinite(clean.astype(np.float32)).all()
    assert clean.min() >= -0.999
    assert clean.max() <= 3.0
    assert diagnostics == {
        "non_finite_replaced": 3,
        "extreme_clipped": 2,
    }
