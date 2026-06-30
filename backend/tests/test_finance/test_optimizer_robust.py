"""L'optimiseur DE doit renvoyer une allocation FAISABLE et FINIE même avec des
colonnes de rendements dégénérées (variance nulle) et un accès broker clairsemé.

Régression : avec les contraintes d'égalité par (ticker × broker), differential
evolution ne satisfaisait pas les contraintes -> poids infaisables (somme par
broker fausse) + Sharpe -inf -> 0 allocation persistée.
"""

import numpy as np
import pandas as pd


def test_de_returns_feasible_finite_weights(monkeypatch):
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 600.0, "BoursDirect": 400.0})
    rng = np.random.default_rng(0)
    n = 30
    R = rng.normal(0.0006, 0.02, (700, n))
    R[:, 4] = 0.0  # colonne dégénérée (variance nulle)
    rets = pd.DataFrame(R, columns=[f"T{i}" for i in range(n)])
    access = [[(i % 4 != 0), (i % 2 == 0)] for i in range(n)]

    W, sharpe = optimize_portfolio_de(
        list(rets.columns), rets, access, ["IBKR", "BoursDirect"], n_sim=3000,
        min_position=0.0,   # déploiement intégral pour vérifier les sommes par broker
    )

    assert np.isfinite(W).all()
    assert np.isfinite(sharpe) and sharpe > 0          # plus de -inf
    assert abs(W.sum() - 1.0) < 1e-6                    # capital total investi = 100 %
    # disponibilité respectée : aucun poids là où l'accès est False
    for i in range(n):
        for j in range(2):
            if not access[i][j]:
                assert W[i, j] == 0.0
    assert W[4].sum() < 1e-3                             # ticker dégénéré écarté
    assert int((W.sum(axis=1) > 1e-4).sum()) >= 5        # portefeuille diversifié
    # Chaque broker (avec ≥1 titre dispo) déploie 100% de son budget -> pas de
    # sous-investissement. b_ratios = budget/total.
    b_ratios = np.array([600.0, 400.0]) / 1000.0
    for j in range(2):
        assert abs(W[:, j].sum() - b_ratios[j]) < 1e-6


def test_de_all_degenerate_returns_zeros(monkeypatch):
    """Si tout est dégénéré, renvoie des poids nuls sans planter."""
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    from app.services.finance.buffett.config import Config
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    rets = pd.DataFrame(np.zeros((100, 3)), columns=["A", "B", "C"])
    W, sharpe = optimize_portfolio_de(["A", "B", "C"], rets, [[True]] * 3, ["IBKR"])
    assert np.isfinite(W).all()
    assert W.sum() == 0.0
