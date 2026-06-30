"""STARR / CVaR : mesure des grosses chutes."""

import numpy as np


def test_portfolio_cvar_is_mean_of_worst_tail():
    from app.services.finance.buffett.starr import portfolio_cvar
    # 100 rendements : -10% (les 5 pires), reste +1%
    r = np.array([-0.10] * 5 + [0.01] * 95)
    # CVaR 5% = moyenne des 5 pires = -(-0.10) = 0.10
    assert abs(portfolio_cvar(r, alpha=0.05) - 0.10) < 1e-9


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
