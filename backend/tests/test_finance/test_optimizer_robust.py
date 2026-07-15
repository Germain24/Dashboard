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
    """should_stop est verifie entre deux GENERATIONS (et entre deux seeds) :
    avec should_stop qui renvoie True des le debut, le seed 1 est interrompu
    des sa 1re generation et le resultat reste exploitable."""
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
    iterations: list[int] = []
    W, starr = optimize_portfolio_de(
        list(rets.columns), rets, access, ["IBKR"], n_sim=3000,
        progress_cb=lambda seed_num, it, conv, best=None: (
            seeds_seen.add(seed_num), iterations.append(it)),
        should_stop=lambda: True,
    )
    assert seeds_seen == {1}       # un seul seed a tourne
    assert max(iterations) == 1    # interrompu des la 1re generation (reactif)
    assert np.isfinite(W).all()
    assert abs(W.sum() - 1.0) < 1e-6


def test_de_stop_mid_seed_is_responsive(monkeypatch):
    """L'arret demande PENDANT un seed prend effet a la generation suivante,
    sans attendre la convergence ni le minimum de generations (#bug rapporte :
    sur ~2900 titres un seed durait des jours, le bouton Arreter etait vain)."""
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 50)   # jamais atteint
    monkeypatch.setattr(Config, "STARR_DE_TOL", 1e-9)             # jamais convergent
    rng = np.random.default_rng(6)
    n = 10
    R = rng.normal(0.0006, 0.02, (500, n))
    rets = pd.DataFrame(R, columns=[f"T{i}" for i in range(n)])
    access = [[True] for _ in range(n)]

    calls = {"n": 0}

    def should_stop():
        calls["n"] += 1
        return calls["n"] >= 3   # demande l'arret pendant le seed 1

    iterations: list[int] = []
    W, starr = optimize_portfolio_de(
        list(rets.columns), rets, access, ["IBKR"], n_sim=3000,
        progress_cb=lambda seed_num, it, conv, best=None: iterations.append(it),
        should_stop=should_stop,
    )
    assert max(iterations) <= 5    # arrete en quelques generations, pas 50
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
        progress_cb=lambda seed_num, it, conv, best=None: seeds_seen.add(seed_num),
    )
    assert seeds_seen == {1}


def test_de_continues_past_first_seed_when_not_stopped(monkeypatch):
    """Tant que should_stop renvoie False, les seeds s'enchainent (pas bloque
    au 1er) ; l'arret intervient des que la condition devient vraie."""
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

    seeds_seen: set[int] = set()
    optimize_portfolio_de(
        list(rets.columns), rets, access, ["IBKR"], n_sim=3000,
        progress_cb=lambda seed_num, it, conv, best=None: seeds_seen.add(seed_num),
        # False tant que les seeds 1 et 2 tournent ; True au debut du seed 3.
        should_stop=lambda: len(seeds_seen) >= 3,
    )
    assert {1, 2, 3} <= seeds_seen


def test_de_vectorized_same_contract(monkeypatch):
    """Evaluation vectorisee (population entiere en 1 matmul, float32, init
    sparse) : le resultat respecte le meme contrat qu'avant (fini, faisable,
    budget deploye)."""
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 600.0, "BoursDirect": 400.0})
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 5)
    monkeypatch.setattr(Config, "STARR_DE_TOL", 1e-3)
    rng = np.random.default_rng(7)
    n = 20
    R = rng.normal(0.0006, 0.02, (500, n))
    rets = pd.DataFrame(R, columns=[f"T{i}" for i in range(n)])
    access = [[(i % 3 != 0), True] for i in range(n)]

    W, starr = optimize_portfolio_de(
        list(rets.columns), rets, access, ["IBKR", "BoursDirect"], n_sim=3000,
        min_position=0.0,
    )
    assert np.isfinite(W).all()
    assert np.isfinite(starr)
    assert abs(W.sum() - 1.0) < 1e-6
    for i in range(n):
        if not access[i][0]:
            assert W[i, 0] == 0.0
    b_ratios = np.array([600.0, 400.0]) / 1000.0
    for j in range(2):
        assert abs(W[:, j].sum() - b_ratios[j]) < 1e-6


def test_neg_starr_batch_matches_scalar():
    """L'objectif vectorise (colonne par colonne) doit coller a neg_starr
    scalaire : meme rendement/downside, CVaR estime a +-1 scenario pres
    (k pires scenarios vs percentile) -> tolerance relative serree."""
    from app.services.finance.buffett.starr import neg_starr, neg_starr_batch

    rng = np.random.default_rng(11)
    n, n_sim, S = 8, 4000, 25
    sim = rng.normal(0.0004, 0.02, (n_sim, n))
    mean_daily = sim.mean(axis=0)
    X = rng.uniform(0.0, 1.0, (n, S))
    X[:, 0] = 0.0                       # colonne degeneree -> 1e6
    batch = neg_starr_batch(X, sim, mean_daily, 0.05, 1.0)
    assert batch[0] == 1e6
    for c in range(1, S):
        scal = neg_starr(X[:, c], sim, mean_daily, 0.05, 1.0)
        assert abs(batch[c] - scal) <= 0.02 * max(abs(scal), 1e-9)


def test_build_init_population_sparse_and_covers_universe():
    """Population initiale : contient l'individu mono-titre demande, couvre
    TOUT l'univers (une coordonnee nulle partout resterait nulle a jamais dans
    un DE), reste sparse, et respecte les bornes [0, 1]."""
    from app.services.finance.buffett.optimizer import build_init_population

    rng = np.random.default_rng(3)
    n, pop_size = 300, 64
    scores = rng.normal(0.5, 0.2, n)
    seed_idx = 42
    pop = build_init_population(n, pop_size, rng, scores, seed_idx,
                                warm_starts=[np.full(n, 0.1)])
    assert pop.shape[0] >= pop_size and pop.shape[1] == n
    assert pop.min() >= 0.0 and pop.max() <= 1.0
    # individu mono-titre (ETF monde / meilleur standalone)
    one_hot = np.zeros(n); one_hot[seed_idx] = 1.0
    assert any(np.array_equal(row, one_hot) for row in pop)
    # couverture : chaque titre est present dans au moins un individu
    assert (pop.max(axis=0) > 0.0).all()
    # sparse : la grande majorite des individus concentres (hors warm-starts)
    n_lines = (pop > 0.0).sum(axis=1)
    assert np.median(n_lines) <= 50


def test_build_init_population_tiny_universe():
    """Petit univers (moins que le minimum scipy de 5 individus requis par
    ligne fixe) : au moins 5 individus, jamais d'erreur d'echantillonnage."""
    from app.services.finance.buffett.optimizer import build_init_population

    rng = np.random.default_rng(4)
    for n in (1, 2, 3, 10):
        pop = build_init_population(n, 16, rng, np.arange(n, dtype=float), 0)
        assert pop.shape[0] >= 5 and pop.shape[1] == n
        assert (pop.max(axis=0) > 0.0).all()
