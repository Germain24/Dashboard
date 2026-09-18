"""Copule : toujours la gaussienne à corrélation COMPLÈTE, jamais la D-vine.

`DVineCopula.simulate()` se termine elle aussi par `multivariate_normal` +
`norm.cdf`, donc par une gaussienne — mais nourrie par `implied_correlation()`,
qui ne lit que l'arbre 1 et ne remplit donc que les n-1 arêtes du chemin D-vine.
À 135 titres : 134 paires renseignées sur 9 045, soit 98,5 % des corrélations
forcées à zéro. Pour un CVaR, cette indépendance fictive fait paraître le
portefeuille bien plus diversifié qu'il n'est et sous-estime les pertes extrêmes.

Le coût était par ailleurs bien réel : > 1 h à 135 titres sans une seule
génération émise (run figé sur « seed 1, 0 génération »).
"""

import numpy as np

from app.services.finance.buffett.config import Config
from app.services.finance.buffett.vine_copula import DVineCopula


def test_vine_is_disabled_by_default():
    assert int(Config.STARR_VINE_MAX_DIM) == 0


def test_simulate_scenarios_never_fits_a_vine(monkeypatch):
    from app.services.finance.buffett import starr

    def boom(*_a, **_k):
        raise AssertionError("la D-vine ne doit plus etre ajustee")

    monkeypatch.setattr(DVineCopula, "fit", boom)
    rng = np.random.default_rng(0)
    returns = rng.normal(0.0, 0.01, (400, 12))

    sim = starr.simulate_scenarios(returns, n_sim=500, seed=1)

    assert sim.shape == (500, 12)
    assert np.isfinite(sim).all()


def test_gaussian_path_keeps_every_pair_correlated():
    """Le fond du probleme : la vine mettait la quasi-totalite des paires a zero."""
    n = 20
    rng = np.random.default_rng(3)
    factor = rng.normal(0.0, 0.01, (600, 1))
    returns = factor + rng.normal(0.0, 0.004, (600, n))  # tous correles entre eux

    u = np.apply_along_axis(
        lambda col: (np.argsort(np.argsort(col)) + 1) / (len(col) + 1), 0, returns
    )
    vine_rho = DVineCopula(family="t").fit(u).implied_correlation()
    off_diag = ~np.eye(n, dtype=bool)
    zeros_vine = int((vine_rho[off_diag] == 0.0).sum())

    # La vine ne renseigne que les n-1 aretes du chemin, comptees deux fois.
    assert zeros_vine == n * (n - 1) - 2 * (n - 1)
    assert zeros_vine / off_diag.sum() > 0.85   # >85 % de paires « independantes »


def test_preparation_milestones_are_reported(monkeypatch):
    """Sans ces jalons, la phase silencieuse ressemble a un blocage."""
    import pandas as pd

    from app.services.finance.buffett.optimizer import optimize_portfolio_de

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    monkeypatch.setattr(Config, "MIN_DEFENSIVE_PCT", 0.0)
    monkeypatch.setattr(Config, "MAX_COUNTRY_PCT", 1.0)
    monkeypatch.setattr(Config, "STARR_CARD_BETA", 0.0)
    monkeypatch.setattr(Config, "STARR_STRESS_WEIGHT", 0.0)
    monkeypatch.setattr(Config, "TRANSACTION_COSTS_ENABLED", False)
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 1)
    monkeypatch.setattr(Config, "STARR_DE_MAX_GENERATIONS", 2)
    monkeypatch.setattr(Config, "STARR_DE_POPSIZE", 8)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_BATCH_SIZE", 16)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_MAX_BATCHES", 5)
    monkeypatch.setattr(Config, "STARR_DE_POLISH_MAXITER", 2)

    rng = np.random.default_rng(5)
    n_days = int(Config.STARR_MIN_HISTORY_DAYS)
    rets = pd.DataFrame(
        rng.normal(0.0006, 0.02, (n_days, 6)), columns=[f"T{i}" for i in range(6)]
    )
    seen: list[str] = []

    def recording_but_broken(message):
        # Enregistre PUIS echoue : verifie du meme coup que les jalons sont bien
        # emis et qu'une progression cassee ne fait jamais tomber l'optimisation.
        seen.append(message)
        raise RuntimeError("UI indisponible")

    weights, _score = optimize_portfolio_de(
        list(rets.columns), rets, [[True]] * 6, ["IBKR"], n_sim=400,
        benchmark_returns=rng.normal(0.0004, 0.01, n_days),
        preparation_cb=recording_but_broken,
    )

    joined = " | ".join(seen)
    assert "Monte-Carlo" in joined
    assert "contraintes" in joined
    assert "depart" in joined or "départ" in joined
    assert np.isfinite(np.asarray(weights, dtype=float)).all()
