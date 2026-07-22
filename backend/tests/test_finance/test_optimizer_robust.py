"""L'optimiseur DE doit renvoyer une allocation FAISABLE et FINIE même avec des
colonnes de rendements dégénérées (variance nulle) et un accès broker clairsemé.

Régression : avec les contraintes d'égalité par (ticker × broker), differential
evolution ne satisfaisait pas les contraintes -> poids infaisables (somme par
broker fausse) + Sharpe -inf -> 0 allocation persistée.
"""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def _relax_real_world_constraints_for_synthetic_universes(monkeypatch):
    """Les petits univers de ce fichier ne peuvent pas respecter pays<=25 %."""
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "MIN_DEFENSIVE_PCT", 0.0)
    monkeypatch.setattr(Config, "MAX_COUNTRY_PCT", 1.0)
    monkeypatch.setattr(Config, "STARR_CARD_BETA", 0.0)
    monkeypatch.setattr(Config, "STARR_DE_MAX_GENERATIONS", 50)
    monkeypatch.setattr(Config, "STARR_DE_STAGNATION_GENERATIONS", 10)
    monkeypatch.setattr(Config, "STARR_DE_MAX_SEEDS", 3)
    monkeypatch.setattr(Config, "STARR_DE_POPSIZE", 32)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_BATCH_SIZE", 32)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_MAX_BATCHES", 10)
    monkeypatch.setattr(Config, "STARR_DE_POLISH_MAXITER", 20)
    # Les scénarios de stress ont leurs propres tests ; les désactiver ici garde
    # les tests DE synthétiques rapides et leurs scénarios exactement contrôlés.
    monkeypatch.setattr(Config, "STARR_STRESS_WEIGHT", 0.0)
    # Le barème est testé séparément ; ces tests isolent les propriétés du DE.
    monkeypatch.setattr(Config, "TRANSACTION_COSTS_ENABLED", False)


@pytest.fixture(autouse=True)
def _default_benchmark_series(monkeypatch):
    """Fournit une série de benchmark par défaut aux appels qui n'en passent pas.

    Le score d'optimisation mesure désormais l'écart à un benchmark, qui est donc
    une entrée obligatoire. Ces tests portent sur la MÉCANIQUE du DE (faisabilité,
    arrêt, reproductibilité), pas sur l'injection du benchmark — couverte par
    ``test_benchmark_injection.py``. On évite ainsi de répéter la même série dans
    quatorze appels sans rien tester de plus.
    """
    from app.services.finance.buffett import optimizer as opt

    original = opt.optimize_portfolio_de

    def _with_default_benchmark(*args, **kwargs):
        if kwargs.get("benchmark_returns") is None:
            kwargs["benchmark_returns"] = pd.Series(
                np.random.default_rng(123).normal(0.0004, 0.012, 800)
            )
        return original(*args, **kwargs)

    monkeypatch.setattr(opt, "optimize_portfolio_de", _with_default_benchmark)


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
    # Le score est un ÉCART au benchmark : il peut légitimement être négatif (le
    # portefeuille perd contre CW8.PA). Seule la finitude est une propriété du DE
    # — c'est la régression d'origine, un -inf qui annulait toute allocation.
    assert np.isfinite(sharpe)
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


def test_find_seed_retries_until_un_candidat_est_admissible():
    """Le critère d'amorçage est la PÉNALITÉ NULLE, pas un score positif.

    Tant que l'objectif était le ratio rendement/risque, « positif » voulait dire
    « rendement > 0 » — presque toujours vrai. Depuis que le score mesure l'écart
    au benchmark, l'exiger reviendrait à demander au tirage aléatoire de battre
    déjà CW8.PA, c'est-à-dire de résoudre le problème avant de commencer.
    """
    from app.services.finance.buffett.optimizer import find_positive_random_seed

    calls = {"n": 0}
    progress: list[tuple[int, int, float | None]] = []

    def feasible(candidates):
        calls["n"] += 1
        mask = np.zeros(candidates.shape[1], dtype=bool)
        if calls["n"] == 2:           # aucun candidat admissible au 1er lot
            mask[3] = True
        return mask

    # Score NÉGATIF partout : il ne doit plus empêcher l'amorçage.
    vector, score, batch = find_positive_random_seed(
        8,
        np.random.default_rng(12),
        lambda candidates: np.full(candidates.shape[1], 0.35),
        batch_size=6,
        max_batches=4,
        progress_cb=lambda current, maximum, best: progress.append((current, maximum, best)),
        feasible=feasible,
    )

    assert batch == 2
    assert score == pytest.approx(-0.35)
    assert vector.shape == (8,)
    assert progress[-1] == (2, 4, pytest.approx(-0.35))


def test_find_seed_fails_quand_aucun_candidat_ne_respecte_les_contraintes():
    """C'est le SEUL cas d'échec qui subsiste, et c'est bien celui que la
    relaxation look-through de l'appelant doit rattraper."""
    from app.services.finance.buffett.optimizer import find_positive_random_seed

    with pytest.raises(RuntimeError, match="Aucun portefeuille admissible"):
        find_positive_random_seed(
            5,
            np.random.default_rng(13),
            lambda candidates: np.full(candidates.shape[1], 0.1),
            batch_size=4,
            max_batches=3,
            feasible=lambda candidates: np.zeros(candidates.shape[1], dtype=bool),
        )


def test_un_score_negatif_ne_bloque_plus_l_amorcage():
    """Régression : le DE doit pouvoir démarrer d'un portefeuille qui perd contre
    le benchmark — c'est justement le point de départ normal."""
    from app.services.finance.buffett.optimizer import find_positive_random_seed

    vector, score, batch = find_positive_random_seed(
        5,
        np.random.default_rng(15),
        lambda candidates: np.full(candidates.shape[1], 4.2),   # score = -4.2
        batch_size=4,
        max_batches=3,
        feasible=lambda candidates: np.ones(candidates.shape[1], dtype=bool),
    )
    assert batch == 1
    assert score == pytest.approx(-4.2)
    assert vector.shape == (5,)


def test_positive_seed_error_has_a_specific_runtime_error_type():
    from app.services.finance.buffett.optimizer import (
        PositiveSeedNotFound,
        find_positive_random_seed,
    )

    with pytest.raises(PositiveSeedNotFound):
        find_positive_random_seed(
            5,
            np.random.default_rng(14),
            lambda candidates: np.full(candidates.shape[1], 0.1),
            batch_size=2,
            max_batches=1,
            feasible=lambda candidates: np.zeros(candidates.shape[1], dtype=bool),
        )


def test_de_retries_without_lookthrough_constraints(monkeypatch, capsys):
    from app.services.finance.buffett import broker_availability, lookthrough
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.optimizer import optimize_portfolio_de

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"PEA": 1000.0})
    monkeypatch.setattr(Config, "MIN_DEFENSIVE_PCT", 0.30)
    monkeypatch.setattr(Config, "MAX_COUNTRY_PCT", 0.25)
    monkeypatch.setattr(Config, "CONSTRAINT_PENALTY", 100.0)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_BATCH_SIZE", 4)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_MAX_BATCHES", 1)
    monkeypatch.setattr(Config, "STARR_DE_POPSIZE", 5)
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 1)
    monkeypatch.setattr(Config, "STARR_DE_MAX_GENERATIONS", 1)
    monkeypatch.setattr(Config, "STARR_DE_POLISH_MAXITER", 1)
    monkeypatch.setattr(broker_availability, "load_etf_tickers", lambda: {"A", "B"})
    monkeypatch.setattr(
        lookthrough,
        "load_lookthrough",
        lambda: ({"A": 0.0, "B": 0.0}, {"A": {"France": 1.0}, "B": {"France": 1.0}}),
    )

    # Rendements positifs mais assez faibles pour que les penalites defensif/pays
    # rendent tous les scores de la premiere passe negatifs.
    values = np.tile([[0.0001, 0.0002], [0.0002, 0.0001]], (30, 1))
    returns = pd.DataFrame(values, columns=["A", "B"])

    weights, score = optimize_portfolio_de(
        ["A", "B"], returns, [[True], [True]], ["PEA"], n_sim=40
    )

    output = capsys.readouterr().out
    assert "nouvelle tentative sans minimum defensif ni plafond par pays" in output
    # Ce test porte sur la RELAXATION des contraintes, pas sur le signe du score :
    # l'écart au benchmark est négatif ici et c'est normal.
    assert np.isfinite(score)
    assert weights.sum() == pytest.approx(1.0)


def _patch_fast_deterministic_de(monkeypatch, returns: pd.DataFrame):
    from app.services.finance.buffett import broker_availability, starr
    from app.services.finance.buffett.config import Config

    scenarios = np.asarray(returns, dtype=float)

    def _deterministic_scenarios(_returns, n_sim, seed):
        """Répète les lignes REÇUES, sans présumer de leur nombre de colonnes.

        L'optimiseur simule désormais le benchmark en même temps que l'univers
        (colonne supplémentaire quand il n'est pas déjà dedans) : un faux qui
        renverrait une largeur fixe ne respecterait plus le contrat de la vraie
        `simulate_scenarios` et provoquerait un décalage de dimensions. Le tuilage
        par LIGNES préserve exactement le contenu de chaque colonne.
        """
        arr = np.asarray(_returns, dtype=float)
        reps = int(np.ceil(n_sim / max(len(arr), 1)))
        return np.tile(arr, (reps, 1))[:n_sim]

    monkeypatch.setattr(starr, "simulate_scenarios", _deterministic_scenarios)
    monkeypatch.setattr(broker_availability, "load_etf_tickers", lambda: set(returns.columns))
    monkeypatch.setattr(Config, "STARR_DE_POPSIZE", 8)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_BATCH_SIZE", 8)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_MAX_BATCHES", 2)
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 1)
    monkeypatch.setattr(Config, "STARR_DE_MAX_GENERATIONS", 20)
    monkeypatch.setattr(Config, "STARR_DE_STAGNATION_GENERATIONS", 2)
    monkeypatch.setattr(Config, "STARR_DE_MAX_SEEDS", 1)
    monkeypatch.setattr(Config, "STARR_DE_POLISH_MAXITER", 1)
    return scenarios


def test_final_score_uses_actual_broker_deployment(monkeypatch):
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.optimizer import optimize_portfolio_de

    returns = pd.DataFrame(
        np.tile(
            [[-0.002, 0.0002, -0.001, 0.0001], [0.003, 0.0003, 0.002, 0.0002]],
            (30, 1),
        ),
        columns=["PEA_A", "T212_A", "PEA_B", "T212_B"],
    )
    scenarios = _patch_fast_deterministic_de(monkeypatch, returns)
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"PEA": 800.0, "Trading212": 200.0})
    access = [[True, False], [False, True], [True, False], [False, True]]

    weights, score, diagnostics = optimize_portfolio_de(
        list(returns.columns),
        returns,
        access,
        ["PEA", "Trading212"],
        n_sim=60,
        seed=17,
        return_diagnostics=True,
    )

    # Le score doit porter sur le déploiement RÉEL par broker (budgets 800/200),
    # pas sur le vecteur de préférences qui le précède. On vérifie la propriété
    # plutôt que de reproduire l'arithmétique interne : la reproduire obligerait à
    # dupliquer le prior par classe, l'alignement du benchmark et sa colonne
    # simulée — un test qui ne casserait plus que sur ses propres copies.
    assert weights[:, 0].sum() == pytest.approx(0.8)
    assert weights[:, 1].sum() == pytest.approx(0.2)
    assert np.isfinite(score)
    assert diagnostics["benchmarks"]["optimized"] == pytest.approx(score)
    # Chaque titre n'est finançable que par SON broker (accès disjoint) : un score
    # calculé sur les préférences brutes ignorerait cette contrainte et donnerait
    # donc une valeur différente de l'équipondéré déployé.
    assert diagnostics["benchmarks"]["equal_weight"] != pytest.approx(score)


def test_stagnation_is_bounded_and_run_is_reproducible(monkeypatch):
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.optimizer import optimize_portfolio_de

    returns = pd.DataFrame(
        np.tile([[0.0001, 0.0001], [0.0002, 0.0002]], (30, 1)),
        columns=["A", "B"],
    )
    _patch_fast_deterministic_de(monkeypatch, returns)
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"Trading212": 1000.0})
    monkeypatch.setattr(Config, "STARR_DE_TOL", -1.0)  # interdit la convergence scipy

    args = (list(returns.columns), returns, [[True], [True]], ["Trading212"])
    first_w, first_score, first_diag = optimize_portfolio_de(
        *args, n_sim=60, seed=23, return_diagnostics=True
    )
    second_w, second_score, second_diag = optimize_portfolio_de(
        *args, n_sim=60, seed=23, return_diagnostics=True
    )

    assert first_diag["termination"]["runs"][0]["reason"] == "stagnation"
    assert first_diag["termination"]["runs"][0]["generations"] <= 3
    assert np.array_equal(first_w, second_w)
    assert first_score == second_score
    assert first_diag == second_diag


def test_diagnostics_signalent_le_portefeuille_detenu_et_le_benchmark(monkeypatch):
    """Le bloc `turnover` a disparu : sa pénalité faisait DOUBLON avec les frais de
    transaction, qui modélisent déjà le coût en euros des ordres. Les positions
    courantes restent utilisées (frais + amorçage de la population), et les
    diagnostics doivent le refléter — ainsi que les repères du benchmark, qui
    donnent son sens au score."""
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.optimizer import optimize_portfolio_de

    returns = pd.DataFrame(
        np.tile([[0.0001, 0.0003], [0.0002, 0.0004]], (30, 1)),
        columns=["A", "B"],
    )
    _patch_fast_deterministic_de(monkeypatch, returns)
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"Trading212": 1000.0})

    _, _, diagnostics = optimize_portfolio_de(
        ["A", "B"],
        returns,
        [[True], [True]],
        ["Trading212"],
        n_sim=60,
        seed=29,
        current_weights={"A": 0.8, "B": 0.2},
        return_diagnostics=True,
    )

    assert "turnover" not in diagnostics
    assert diagnostics["current_weights_available"] is True
    assert diagnostics["schema_version"] == 3
    assert diagnostics["estimation"]["mean_prior"] == "per_asset_class_median"
    bench = diagnostics["benchmark_relative"]
    assert bench["ticker"] == Config.STARR_BENCHMARK_TICKER
    assert np.isfinite(bench["cvar_pct"]) and bench["cvar_pct"] >= 0.0
