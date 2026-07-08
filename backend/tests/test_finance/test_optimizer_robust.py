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
    # Réglages DE allégés pour le test (la prod utilise tol=1e-6, ~144s/seed sur
    # un problème de cette taille -> beaucoup trop lent en CI).
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 5)
    monkeypatch.setattr(Config, "STARR_DE_TOL", 1e-3)
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


def test_de_calls_on_new_best_with_decreasing_energy(monkeypatch):
    """on_new_best doit être appelé au moins une fois (résultat final garanti),
    et la matrice W qu'il reçoit à chaque appel doit correspondre à une
    allocation faisable (même contrat que la valeur de retour finale)."""
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 5)
    monkeypatch.setattr(Config, "STARR_DE_TOL", 1e-3)
    rng = np.random.default_rng(1)
    n = 20
    R = rng.normal(0.0006, 0.02, (700, n))
    rets = pd.DataFrame(R, columns=[f"T{i}" for i in range(n)])
    access = [[True] for _ in range(n)]

    calls: list[np.ndarray] = []
    W_final, starr = optimize_portfolio_de(
        list(rets.columns), rets, access, ["IBKR"], n_sim=3000,
        on_new_best=lambda W: calls.append(W.copy()),
    )

    assert len(calls) >= 1
    for W in calls:
        assert np.isfinite(W).all()
        assert abs(W.sum() - 1.0) < 1e-6   # capital total investi = 100%, même contrat que le retour final
    # Le dernier appel (post-polish) doit correspondre exactement au résultat final retourné.
    assert np.allclose(calls[-1], W_final)


def test_de_without_on_new_best_is_unaffected(monkeypatch):
    """on_new_best=None (défaut) : comportement 100% identique à avant -- même
    résultat que test_de_returns_feasible_finite_weights, juste sans callback."""
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 5)
    monkeypatch.setattr(Config, "STARR_DE_TOL", 1e-3)
    rng = np.random.default_rng(2)
    n = 10
    R = rng.normal(0.0006, 0.02, (500, n))
    rets = pd.DataFrame(R, columns=[f"T{i}" for i in range(n)])
    access = [[True] for _ in range(n)]

    W, starr = optimize_portfolio_de(
        list(rets.columns), rets, access, ["IBKR"], n_sim=3000,
    )
    assert np.isfinite(W).all()
    assert abs(W.sum() - 1.0) < 1e-6


def test_de_stops_after_should_stop_true(monkeypatch):
    """should_stop() verifie uniquement ENTRE deux seeds : avec should_stop qui
    renvoie True des le debut, on ne fait qu'UN SEUL seed puis on s'arrete."""
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 5)
    monkeypatch.setattr(Config, "STARR_DE_TOL", 1e-3)
    rng = np.random.default_rng(3)
    n = 10
    R = rng.normal(0.0006, 0.02, (500, n))
    rets = pd.DataFrame(R, columns=[f"T{i}" for i in range(n)])
    access = [[True] for _ in range(n)]

    seeds_seen: set[int] = set()
    W, starr = optimize_portfolio_de(
        list(rets.columns), rets, access, ["IBKR"], n_sim=3000,
        progress_cb=lambda seed_num, it, conv: seeds_seen.add(seed_num),
        should_stop=lambda: True,
    )
    assert seeds_seen == {1}   # un seul seed a tourne
    assert np.isfinite(W).all()
    assert abs(W.sum() - 1.0) < 1e-6


def test_de_without_should_stop_runs_exactly_one_seed(monkeypatch):
    """Sans should_stop (defaut None) : exactement 1 seed, jamais de boucle
    infinie -- comportement sur qui remplace l'ancien STARR_DE_N_SEEDS=1 des
    tests existants."""
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 5)
    monkeypatch.setattr(Config, "STARR_DE_TOL", 1e-3)
    rng = np.random.default_rng(4)
    n = 10
    R = rng.normal(0.0006, 0.02, (500, n))
    rets = pd.DataFrame(R, columns=[f"T{i}" for i in range(n)])
    access = [[True] for _ in range(n)]

    seeds_seen: set[int] = set()
    optimize_portfolio_de(
        list(rets.columns), rets, access, ["IBKR"], n_sim=3000,
        progress_cb=lambda seed_num, it, conv: seeds_seen.add(seed_num),
    )
    assert seeds_seen == {1}


def test_de_continues_past_first_seed_when_not_stopped(monkeypatch):
    """should_stop qui renvoie False les 2 premieres fois puis True : verifie
    qu'on fait bien plusieurs seeds avant de s'arreter (pas bloque au 1er)."""
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 5)
    monkeypatch.setattr(Config, "STARR_DE_TOL", 1e-3)
    rng = np.random.default_rng(5)
    n = 10
    R = rng.normal(0.0006, 0.02, (500, n))
    rets = pd.DataFrame(R, columns=[f"T{i}" for i in range(n)])
    access = [[True] for _ in range(n)]

    calls = {"n": 0}
    def should_stop():
        calls["n"] += 1
        return calls["n"] >= 3   # False, False, True -> 3 seeds

    seeds_seen: set[int] = set()
    optimize_portfolio_de(
        list(rets.columns), rets, access, ["IBKR"], n_sim=3000,
        progress_cb=lambda seed_num, it, conv: seeds_seen.add(seed_num),
        should_stop=should_stop,
    )
    assert seeds_seen == {1, 2, 3}
