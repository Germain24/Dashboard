"""L'optimiseur DE doit renvoyer une allocation FAISABLE et FINIE même avec des
colonnes de rendements dégénérées (variance nulle) et un accès broker clairsemé.

Régression : avec les contraintes d'égalité par (ticker × broker), differential
evolution ne satisfaisait pas les contraintes -> poids infaisables (somme par
broker fausse) + Sharpe -inf -> 0 allocation persistée.
"""

import numpy as np
import pandas as pd
import pytest


def test_temperature_children_scale_from_local_to_global():
    from app.services.finance.buffett.optimizer import temperature_child_kick_sizes

    low_rng = np.random.default_rng(7)
    high_rng = np.random.default_rng(7)
    low = [
        temperature_child_kick_sizes(
            low_rng,
            active_lines=20,
            line_budget=40,
            temperature=0.25,
            child_rank=rank,
            children_per_parent=8,
        )
        for rank in range(8)
    ]
    high = [
        temperature_child_kick_sizes(
            high_rng,
            active_lines=20,
            line_budget=40,
            temperature=1.0,
            child_rank=rank,
            children_per_parent=8,
        )
        for rank in range(8)
    ]

    assert low[0][1] == 1
    assert low[-1][1] == 5
    assert high[0][1] >= low[0][1]
    assert high[0][1] == 2
    assert high[-1][1] == 20
    assert high[-1][0] == "global"


def test_only_the_global_best_gets_four_guaranteed_local_children():
    from app.services.finance.buffett.optimizer import local_child_kick_sizes

    rng = np.random.default_rng(9)
    children = [
        local_child_kick_sizes(
            rng,
            active_lines=20,
            line_budget=40,
            child_rank=rank,
            local_children=4,
        )
        for rank in range(4)
    ]

    assert [item[1] for item in children] == [1, 1, 2, 2]
    assert all(item[0] == "local" for item in children)


def test_parent_selection_never_keeps_duplicate_supports():
    from app.services.finance.buffett.optimizer import (
        select_unique_support_candidates,
        support_signature,
    )

    candidates = [
        (1.0, np.array([0.7, 0.3, 0.0, 0.0])),
        (1.1, np.array([0.4, 0.6, 0.0, 0.0])),  # même support
        (1.2, np.array([0.0, 0.6, 0.4, 0.0])),
        (1.3, np.array([0.0, 0.0, 0.6, 0.4])),
    ]
    selected = select_unique_support_candidates(
        candidates,
        count=3,
        min_position=0.0,
        min_distance=0.0,
    )
    signatures = [support_signature(vector, 0.0) for _energy, vector in selected]

    assert len(selected) == 3
    assert len(signatures) == len(set(signatures))
    assert selected[0][0] == 1.0


def test_novel_selection_prefers_a_distant_support_over_a_better_clone():
    from app.services.finance.buffett.optimizer import (
        select_novel_support_candidates,
        support_signature,
    )

    anchor = np.array([0.5, 0.5, 0.0, 0.0, 0.0])
    close_but_better = np.array([0.7, 0.3, 0.0, 0.0, 0.0])
    distant = np.array([0.0, 0.0, 0.4, 0.3, 0.3])
    selected = select_novel_support_candidates(
        [(1.0, close_but_better), (2.0, distant)],
        count=1,
        min_position=0.0,
        anchors=[anchor],
    )

    assert support_signature(selected[0][1], 0.0) == frozenset({2, 3, 4})


@pytest.fixture(autouse=True)
def _relax_real_world_constraints_for_synthetic_universes(monkeypatch):
    """Les petits univers de ce fichier ne peuvent pas respecter pays<=25 %."""
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett import lookthrough, optimizer, sector_constraints

    # Univers synthétiques : ne pas relire le catalogue personnel (ni ses
    # milliers de compositions) pour chaque essai de l'optimiseur.
    monkeypatch.setattr(optimizer, "load_etf_tickers", lambda: set())
    monkeypatch.setattr(optimizer, "load_asset_classes", lambda: {})
    monkeypatch.setattr(lookthrough, "load_lookthrough", lambda: ({}, {}))
    monkeypatch.setattr(sector_constraints, "load_classification", lambda: ({}, {}))

    monkeypatch.setattr(Config, "MIN_DEFENSIVE_PCT", 0.0)
    monkeypatch.setattr(Config, "MAX_COUNTRY_PCT", 1.0)
    monkeypatch.setattr(Config, "MAX_REGION_PCT", 1.0)
    monkeypatch.setattr(Config, "STARR_CARD_BETA", 0.0)
    monkeypatch.setattr(Config, "STARR_DE_MAX_GENERATIONS", 50)
    monkeypatch.setattr(Config, "STARR_DE_MAX_SEEDS", 3)
    monkeypatch.setattr(Config, "STARR_DE_POPSIZE", 32)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_BATCH_SIZE", 32)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_MAX_BATCHES", 10)
    # Le screening élitiste des seeds froides est borné ici aussi : sa valeur de
    # production (~25 600 tirages) n'apporte rien sur ces univers minuscules.
    monkeypatch.setattr(Config, "STARR_DE_ELITE_BATCHES", 4)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_COUNT", 8)
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


def test_unknown_etf_composition_is_descriptive_only(monkeypatch):
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.optimizer import optimize_portfolio_de

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 5)
    monkeypatch.setattr(Config, "STARR_DE_TOL", 1e-3)
    rng = np.random.default_rng(321)
    tickers = ["ETF_UNKNOWN", "ETF_HALF", *[f"STOCK{i}" for i in range(6)]]
    returns = pd.DataFrame(
        rng.normal(0.0005, 0.018, (500, len(tickers))),
        columns=tickers,
    )

    weights, score, diagnostics = optimize_portfolio_de(
        tickers,
        returns,
        [[True] for _ in tickers],
        ["IBKR"],
        n_sim=1500,
        max_generations=6,
        economic_unknown_exposures={"ETF_UNKNOWN": 1.0, "ETF_HALF": 0.5},
        return_diagnostics=True,
    )

    global_weights = weights.sum(axis=1)
    unknown_weight = global_weights[0] + 0.5 * global_weights[1]
    assert np.isfinite(score)
    unknown = diagnostics["unknown_equity_composition"]
    assert unknown["method"] == "descriptive_weighted_residual"
    assert unknown["descriptive_only"] is True
    assert "hard_cap" not in unknown
    assert "compliant" not in unknown
    assert unknown["actual_weight"] == pytest.approx(unknown_weight)
    assert diagnostics["economic_action_concentration"]["descriptive_only"] is True
    assert diagnostics["economic_action_concentration"]["objective_penalty_points"] == 0
    evolution = diagnostics["termination"]["annealing"]["evolutionary_generation"]
    generations = evolution["generations"]
    assert generations >= 1
    assert evolution["unique_other_parents"] == 12 * generations
    assert evolution["parents"] == 13 * generations
    # Quatre enfants exploitent directement le meilleur global ; les huit
    # autres enfants sont produits pour chacune des douze lignées secondaires.
    assert evolution["children"] == (4 + 12 * 8) * generations
    assert evolution["random"] == 10 * generations
    assert evolution["feasible"] + evolution["rejected"] == (
        evolution["children"] + evolution["random"]
    )
    assert evolution["injected"] >= evolution["survivors"]


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
    """Avec should_stop a True des le debut : la seed 1 va quand meme jusqu'a sa
    fin naturelle (convergence/stagnation) -- l'arret annule seulement le
    lancement d'une seed SUIVANTE. Un portefeuille a moitie optimise n'est pas
    un resultat exploitable, d'ou l'abandon de l'interruption a chaud."""
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
    # La seed n'est PAS coupee a la 1re generation : elle atteint au moins son
    # minimum de generations avant de se terminer naturellement.
    assert max(iterations) >= 5
    assert np.isfinite(W).all()
    assert abs(W.sum() - 1.0) < 1e-6


def test_de_stop_lets_current_seed_finish(monkeypatch):
    """L'arret demande PENDANT une seed ne la coupe pas : elle continue jusqu'a
    sa fin naturelle (ici la stagnation), puis aucune nouvelle seed n'est
    lancee. Demande utilisateur : le bouton Arreter doit rendre un portefeuille
    reellement optimise, pas l'etat intermediaire de la generation courante."""
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 10)
    monkeypatch.setattr(Config, "STARR_DE_TOL", 1e-9)             # jamais convergent
    rng = np.random.default_rng(6)
    n = 10
    R = rng.normal(0.0006, 0.02, (500, n))
    rets = pd.DataFrame(R, columns=[f"T{i}" for i in range(n)])
    access = [[True] for _ in range(n)]

    calls = {"n": 0}

    def should_stop():
        calls["n"] += 1
        return calls["n"] >= 3   # demande l'arret pendant la seed 1

    seeds_seen: set[int] = set()
    iterations: list[int] = []
    W, starr = optimize_portfolio_de(
        list(rets.columns), rets, access, ["IBKR"], n_sim=3000,
        progress_cb=lambda seed_num, it, conv, best=None: (
            seeds_seen.add(seed_num), iterations.append(it)),
        should_stop=should_stop,
    )
    assert seeds_seen == {1}       # pas de seed suivante apres l'arret demande
    assert max(iterations) >= 10   # la seed en cours est allee a son terme
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


def test_de_keeps_searching_until_stopped(monkeypatch):
    """Tant que should_stop renvoie False, la recherche continue.

    Ce test enchaînait auparavant plusieurs SEEDS. Le recuit les a remplacées
    par UNE recherche continue — jeter la population à chaque redémarrage
    coûtait des milliers de générations d'apprentissage. L'exigence demeure :
    ne pas rester bloqué au début, et s'arrêter dès que la condition est vraie.
    Elle se mesure désormais en générations, le numéro de seed ne bougeant plus.
    """
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
    generations: list[int] = []

    def _cb(seed_num, it, conv, best=None, **_kwargs):
        seeds_seen.add(seed_num)
        generations.append(it)

    optimize_portfolio_de(
        list(rets.columns), rets, access, ["IBKR"], n_sim=3000,
        progress_cb=_cb,
        should_stop=lambda: len(generations) >= 6,
    )
    # UNE seule seed, mais la recherche a bien dépassé les premières générations.
    assert seeds_seen == {1}
    assert len(generations) >= 6
    # Invariant du graphe : générations uniques et strictement croissantes.
    assert generations == sorted(generations)
    assert len(set(generations)) == len(generations)


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


def test_build_init_population_contains_action_and_etf_stratified_starts():
    from app.services.finance.buffett.optimizer import build_init_population

    flags = np.array([False] * 6 + [True] * 6)
    pop = build_init_population(
        12,
        24,
        np.random.default_rng(7),
        np.arange(12, dtype=float),
        None,
        is_etf=flags,
    )

    supports = pop > 0
    assert any(row[~flags].any() and not row[flags].any() for row in supports)
    assert any(row[flags].any() and not row[~flags].any() for row in supports)


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


def test_invalid_objective_sentinel_stops_before_de_seeds():
    from app.services.finance.buffett.optimizer import (
        InvalidOptimizationObjective,
        find_positive_random_seed,
    )

    with pytest.raises(
        InvalidOptimizationObjective,
        match="objectif numérique invalide",
    ):
        find_positive_random_seed(
            5,
            np.random.default_rng(16),
            lambda candidates: np.full(candidates.shape[1], 1e6),
            batch_size=4,
            max_batches=200,
            feasible=lambda candidates: np.ones(candidates.shape[1], dtype=bool),
        )


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
    from app.services.finance.buffett import broker_availability, lookthrough, optimizer
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
    # optimizer importe cette fonction au niveau module : patcher aussi la
    # reference locale rend le test independant de l'ordre d'import des fichiers.
    monkeypatch.setattr(optimizer, "load_etf_tickers", lambda: {"A", "B"})
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


def test_actions_only_disables_geography_but_keeps_defensive_floor(monkeypatch):
    from app.services.finance.buffett import lookthrough, optimizer
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.optimizer import optimize_portfolio_de

    tickers = ["FR_GROWTH", "FR_DEFENSIVE", "FR_BALANCED"]
    returns = pd.DataFrame(
        np.tile(
            [
                [0.0010, 0.0002, 0.0007],
                [-0.0004, 0.0001, -0.0002],
            ],
            (40, 1),
        ),
        columns=tickers,
    )

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"PEA": 1000.0})
    monkeypatch.setattr(Config, "MIN_DEFENSIVE_PCT", 0.30)
    monkeypatch.setattr(Config, "MAX_COUNTRY_PCT", 0.25)
    monkeypatch.setattr(Config, "MAX_REGION_PCT", 0.50)
    monkeypatch.setattr(Config, "MAX_POSITION_PCT", 1.0)
    monkeypatch.setattr(Config, "MAX_SECTOR_PCT", 1.0)
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 1)
    monkeypatch.setattr(Config, "STARR_DE_MAX_GENERATIONS", 2)
    monkeypatch.setattr(Config, "STARR_DE_POPSIZE", 8)
    monkeypatch.setattr(Config, "STARR_DE_POLISH_MAXITER", 1)
    monkeypatch.setattr(optimizer, "load_etf_tickers", lambda: set())
    monkeypatch.setattr(
        optimizer,
        "load_asset_classes",
        lambda: {ticker: "actions" for ticker in tickers},
    )
    monkeypatch.setattr(
        lookthrough,
        "load_lookthrough",
        lambda: (
            {"FR_GROWTH": 0.0, "FR_DEFENSIVE": 1.0, "FR_BALANCED": 0.5},
            {ticker: {"France": 1.0} for ticker in tickers},
        ),
    )

    weights, _score, diagnostics = optimize_portfolio_de(
        tickers,
        returns,
        [[True]] * len(tickers),
        ["PEA"],
        n_sim=40,
        seed=17,
        return_diagnostics=True,
    )

    assert diagnostics["asset_universe"]["actions_only"] is True
    assert diagnostics["asset_universe"]["geographic_hard_constraints_disabled"] is True
    assert diagnostics["asset_universe"]["defensive_floor_enabled"] is True
    assert diagnostics["country_constraints"]["hard_cap_enabled"] is False
    assert diagnostics["region_constraints"]["hard_cap_enabled"] is False
    assert diagnostics["country_constraints"]["compliant"] is True
    assert diagnostics["region_constraints"]["compliant"] is True
    assert diagnostics["country_constraints"]["exposures"]["France"] > 0.25
    defensive_share = np.array([0.0, 1.0, 0.5]) @ weights[:, 0]
    assert defensive_share >= 0.30 - 1e-8
    assert float(weights[:, 0].sum()) == pytest.approx(1.0)


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
    # Ce test porte sur la ventilation 80/20 et le score broker-aware. Avec
    # seulement deux titres accessibles au PEA, le plafond action de 15 %
    # rendrait mécaniquement impossible d'y déployer 80 % et testerait une
    # contrainte sans rapport avec son objet.
    monkeypatch.setattr(Config, "MAX_POSITION_PCT", 1.0)
    monkeypatch.setattr(Config, "MAX_SECTOR_PCT", 1.0)
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


def test_small_broker_uses_global_one_percent_line_floor(monkeypatch):
    """Un broker à 3,5 % du capital ne peut ouvrir que trois vraies lignes.

    C'est la CAPACITÉ ÉCONOMIQUE : le plancher de 1 % du portefeuille global
    rendu opérationnel. À ne pas confondre avec `STARR_MAX_LINES_PER_BROKER`,
    qui est le SEUIL DU MALUS — plat pour tous, sans effet en dessous.

    Confondre les deux a coûté deux régressions successives : tronquer au seuil
    rendait le malus inatteignable, puis un plafond plat a laissé ce broker
    étaler ses 3,5 % sur des dizaines de micro-lignes, toutes annulées par le
    filtre du plancher — son budget entier ressortait NON INVESTI.
    """
    from app.services.finance.buffett import optimizer
    from app.services.finance.buffett.config import Config

    tickers = ["PEA_CORE", *[f"T212_{index}" for index in range(8)]]
    alternating = np.tile([-1.0, 1.0], 40)
    returns = pd.DataFrame(
        {
            ticker: 0.0002 + (0.0005 + index * 0.00003) * alternating
            for index, ticker in enumerate(tickers)
        }
    )
    _patch_fast_deterministic_de(monkeypatch, returns)
    monkeypatch.setattr(
        Config,
        "BUDGET_BROKERS",
        {"PEA": 96_500.0, "Trading212": 3_500.0},
    )
    monkeypatch.setattr(Config, "MIN_ALLOCATION_THRESHOLD", 0.01)
    monkeypatch.setattr(Config, "MAX_POSITION_PCT", 1.0)
    monkeypatch.setattr(Config, "MAX_SECTOR_PCT", 1.0)
    monkeypatch.setattr(optimizer, "load_etf_tickers", lambda: set(tickers))
    access = [[True, False], *[[False, True] for _ in range(8)]]

    weights, _, diagnostics = optimizer.optimize_portfolio_de(
        tickers,
        returns,
        access,
        ["PEA", "Trading212"],
        n_sim=60,
        seed=19,
        return_diagnostics=True,
    )

    t212 = weights[:, 1]
    assert int(np.count_nonzero(t212 > 1e-9)) <= 100
    assert t212.sum() == pytest.approx(0.035)
    assert np.all(t212[t212 > 1e-9] >= 0.035 / 100.0 - 1e-9)
    # Le malus de cardinalité est désactivé : le PEA peut utiliser sa capacité
    # économique et T212 ses 100 points de pie locaux.
    assert diagnostics["line_diversification"]["effective_max_by_broker"] == {
        "PEA": 96,
        "Trading212": 100,
    }
    # Et le budget du petit broker est bien INVESTI, pas évaporé.
    assert float(t212.sum()) == pytest.approx(0.035)


def test_final_matrix_keeps_hard_per_broker_line_cap_with_lookthrough(monkeypatch):
    """La projection finale ne doit pas rouvrir les micro-lignes filtrees par le DE.

    Le meilleur signal brut est volontairement non defensif. La contrainte hard
    impose donc de lui ajouter du defensif. Une projection quadratique autorisee a
    utiliser tout l'univers repartit cette correction sur chaque titre defensif et
    depasse le plafond de lignes ; le chemin final doit au contraire conserver une
    allocation sparse et faisable.
    """
    from app.services.finance.buffett import lookthrough, optimizer
    from app.services.finance.buffett.config import Config

    tickers = ["GROWTH_A", "GROWTH_B", *[f"DEF_{i}" for i in range(6)]]
    alternating = np.tile([-1.0, 1.0], 40)
    returns = pd.DataFrame({
        "GROWTH_A": 0.0100 + 0.0010 * alternating,
        "GROWTH_B": 0.0080 + 0.0012 * alternating,
        **{
            f"DEF_{i}": -0.0020 + (0.0008 + i * 0.00005) * alternating
            for i in range(6)
        },
    })
    _patch_fast_deterministic_de(monkeypatch, returns)

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"PEA": 1000.0})
    monkeypatch.setattr(Config, "STARR_MAX_LINES_PER_BROKER", 3)
    monkeypatch.setattr(Config, "MAX_POSITION_PCT", 1.0)
    monkeypatch.setattr(Config, "MAX_SECTOR_PCT", 1.0)
    monkeypatch.setattr(Config, "MIN_DEFENSIVE_PCT", 0.40)
    monkeypatch.setattr(Config, "MAX_COUNTRY_PCT", 0.80)
    # L'ancienne recherche peut payer ce malus doux, puis compter sur la
    # projection finale pour rendre le portefeuille faisable. Le correctif doit
    # appliquer la faisabilite au portefeuille sparse reellement retourne.
    monkeypatch.setattr(Config, "CONSTRAINT_PENALTY", 1e-4)
    monkeypatch.setattr(optimizer, "load_etf_tickers", lambda: set(tickers))
    monkeypatch.setattr(
        optimizer,
        "load_asset_classes",
        lambda: {ticker: "actions" for ticker in tickers},
    )
    monkeypatch.setattr(
        lookthrough,
        "load_lookthrough",
        lambda: (
            {ticker: float(ticker.startswith("DEF_")) for ticker in tickers},
            {ticker: {f"COUNTRY_{i}": 1.0} for i, ticker in enumerate(tickers)},
        ),
    )

    weights, score, diagnostics = optimizer.optimize_portfolio_de(
        tickers,
        returns,
        [[True]] * len(tickers),
        ["PEA"],
        n_sim=80,
        seed=31,
        return_diagnostics=True,
    )

    assert np.isfinite(score)
    assert diagnostics["constraints_relaxed"] is False
    assert weights[:, 0].sum() == pytest.approx(1.0)
    # Plus de plafond de POLITIQUE sur le nombre de lignes : au-delà du seuil,
    # le malus exponentiel gouverne seul. L'invariant qui compte ici — et que
    # décrit la docstring — est qu'aucune micro-ligne ne subsiste : chaque ligne
    # ouverte pèse au moins le plancher global.
    ouvertes = weights[:, 0][weights[:, 0] > 1e-9]
    assert ouvertes.size >= 1
    assert float(ouvertes.min()) >= float(Config.MIN_ALLOCATION_THRESHOLD) - 1e-9
    defensive = np.array([ticker.startswith("DEF_") for ticker in tickers], dtype=float)
    assert defensive @ weights[:, 0] >= 0.40 - 1e-8
    assert weights[:, 0].max() <= 0.80 + 1e-8


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
    # La stagnation ne termine plus la recherche, elle la RÉCHAUFFE : le garde-fou
    # du mode borné est désormais le nombre de réchauffages stériles. On le place
    # sous le plafond de générations (20) pour que ce soit bien LUI qui coupe —
    # sinon le test ne prouverait que l'existence du plafond.
    monkeypatch.setattr(Config, "STARR_DE_MAX_REHEATS", 3)

    args = (list(returns.columns), returns, [[True], [True]], ["Trading212"])
    first_w, first_score, first_diag = optimize_portfolio_de(
        *args, n_sim=60, seed=23, return_diagnostics=True
    )
    second_w, second_score, second_diag = optimize_portfolio_de(
        *args, n_sim=60, seed=23, return_diagnostics=True
    )

    # La liste `runs` a disparu avec les seeds multiples : une seule recherche
    # continue, donc une seule terminaison. La convergence scipy étant interdite
    # (TOL négatif), la sortie ne peut venir que d'un garde-fou du mode borné.
    termination = first_diag["termination"]
    assert termination["continuous"] is False
    assert termination["reason"] == "epuisement"
    # Coupé par l'épuisement, AVANT le plafond de générations.
    assert termination["generations"] < int(Config.STARR_DE_MAX_GENERATIONS)
    assert termination["annealing"]["sterile_reheats"] >= 3
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
        current_broker_holdings={"Trading212": {"B": 1.0}},
        return_diagnostics=True,
    )

    assert "turnover" not in diagnostics
    assert diagnostics["current_weights_available"] is True
    champion = diagnostics["previous_run_champion"]
    assert champion["available"] is True
    assert champion["accepted_as_initial_incumbent"] is True
    assert champion["score_recomputed_with_current_run_inputs"] is True
    assert np.isfinite(champion["recomputed_score"])
    assert diagnostics["schema_version"] == 5
    assert diagnostics["best_action_candidate"]["found"] is True
    assert diagnostics["best_action_candidate"]["action_weight"] > 0
    assert diagnostics["best_action_candidate"]["selection_is_constrained"] is False
    assert diagnostics["estimation"]["mean_prior"] == "per_asset_class_median"
    bench = diagnostics["benchmark_relative"]
    assert bench["ticker"] == Config.STARR_BENCHMARK_TICKER
    assert np.isfinite(bench["cvar_pct"]) and bench["cvar_pct"] >= 0.0
