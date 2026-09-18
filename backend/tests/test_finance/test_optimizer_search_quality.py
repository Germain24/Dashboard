"""Régressions de qualité : support, poids et score du capital réellement investi."""

import numpy as np
import pandas as pd
import pytest

from app.services.finance.buffett import optimizer, starr
from app.services.finance.buffett.config import Config


@pytest.mark.parametrize("guided", [False, True])
def test_single_line_replacement_preserves_all_other_allocations(guided):
    parent = np.zeros(300)
    parent[:40] = 1.0 / 40
    options = {}
    method = optimizer.kick_portfolio
    if guided:
        method = optimizer.guided_kick_portfolio
        options = {"standalone_scores": np.zeros(300), "correlation": np.eye(300)}
    child = method(parent, np.random.default_rng(7), n_drop=1, n_add=1, **options)
    retained = (parent > 0) & (child > 0)
    assert np.count_nonzero(retained) == 39
    assert np.count_nonzero((parent == 0) & (child > 0)) == 1
    assert child[retained] == pytest.approx(parent[retained])
    assert child.sum() == pytest.approx(parent.sum())
    assert child.max() == pytest.approx(1.0 / 40)


def test_jittered_champion_remains_a_nearby_sparse_portfolio():
    parent = np.zeros(3000)
    parent[:20] = 0.05
    population = optimizer.build_init_population(
        3000, 128, np.random.default_rng(12), np.arange(3000), None,
        warm_starts=[parent], jitter=0.02,
    )
    row = next(i for i, vector in enumerate(population) if np.array_equal(vector, parent))
    neighbor = population[row + 1]
    assert np.count_nonzero(neighbor) == 20
    assert neighbor.sum() == pytest.approx(1.0)
    assert np.linalg.norm(neighbor - parent, ord=1) < 0.05


def test_weight_refinement_moves_along_a_binding_group_budget():
    start = np.array([0.10, 0.30, 0.50, 0.10, 0.0])
    target = np.array([0.25, 0.15, 0.20, 0.40, 0.0])

    def constrained_objective(values):
        energy = np.sum((values - target[:, None]) ** 2, axis=0)
        # Deux groupes entièrement financés : seuls les transferts internes
        # permettent de progresser, les pas coordonnée par coordonnée échouent.
        feasible = np.abs(values[:2].sum(axis=0) - 0.4) < 1e-10
        return np.where(feasible, energy, optimizer.INVALID_OBJECTIVE_ENERGY)

    result, energy = optimizer.refine_portfolio_weights(
        start, constrained_objective, max_rounds=40
    )
    assert result[:2].sum() == pytest.approx(0.4)
    assert result.sum() == pytest.approx(1.0)
    assert result[4] == 0.0
    assert energy < 1e-5


@pytest.fixture
def deterministic_search(monkeypatch):
    config = {
        "BUDGET_BROKERS": {"IBKR": 10000.0},
        "MAX_POSITION_PCT": 0.8,
        "MAX_SECTOR_PCT": 1.0,
        "MAX_SECTOR_PCT_OVERRIDES": {},
        "MIN_DEFENSIVE_PCT": 0.0,
        "MAX_COUNTRY_PCT": 1.0,
        "MAX_REGION_PCT": 1.0,
        "STARR_CARD_BETA": 0.0,
        "STARR_STRESS_WEIGHT": 0.0,
        "STARR_REGIME_WINDOWS": [{"label": "test", "days": 800, "weight": 1.0}],
        "STARR_MEAN_SIGNAL_WEIGHT": 1.0,
        "TRANSACTION_COSTS_ENABLED": False,
        "STARR_SECTOR_RISK_PENALTY": 0.0,
        "STARR_SECTOR_RISK_PENALTY_OVERRIDES": {},
        "STARR_COUNTRY_RISK_PENALTY": 0.0,
        "STARR_REGION_RISK_PENALTY": 0.0,
        "STARR_SECTOR_COUNTRY_DIVERSIFICATION_BONUS": 0.0,
        "STARR_SECTOR_COUNTRY_DEFICIT_PENALTY": 0.0,
        "STARR_GEOGRAPHIC_DIVERSIFICATION_BONUS": 0.0,
        "STARR_DIRECT_ACTION_QUALITY_BONUS": 0.0,
        "STARR_DE_POPSIZE": 12,
        "STARR_DE_POSITIVE_INIT_BATCH_SIZE": 8,
        "STARR_DE_POSITIVE_INIT_MAX_BATCHES": 2,
        "STARR_DE_ELITE_BATCHES": 1,
        "STARR_DE_ELITE_COUNT": 2,
        "STARR_DE_MIN_GENERATIONS": 1,
        "STARR_DE_MAX_GENERATIONS": 12,
        "STARR_DE_POLISH_MAXITER": 30,
        "STARR_EVOLUTION_PARENT_COUNT": 2,
        "STARR_EVOLUTION_CHILDREN_PER_PARENT": 2,
        "STARR_EVOLUTION_GLOBAL_LOCAL_CHILDREN": 2,
        "STARR_EVOLUTION_RANDOM_CANDIDATES": 2,
        "STARR_COOPERATIVE_YIELD_SECONDS": 0.0,
    }
    for name, value in config.items():
        monkeypatch.setattr(Config, name, value)
    monkeypatch.setattr(
        optimizer, "load_asset_classes", lambda: {"A": "actions", "B": "actions"}
    )
    monkeypatch.setattr(
        "app.services.finance.buffett.lookthrough.load_lookthrough", lambda: ({}, {})
    )
    monkeypatch.setattr(
        "app.services.finance.buffett.sector_constraints.load_classification", lambda: ({}, {})
    )

    def simulate(values, n_sim, seed):
        values = np.asarray(values, dtype=float)
        return np.tile(values, (int(np.ceil(n_sim / len(values))), 1))[:n_sim]

    monkeypatch.setattr(starr, "simulate_scenarios", simulate)
    alternating = np.tile([-1.0, 1.0], 400)
    returns = pd.DataFrame({
        "A": 0.001 + 0.012 * alternating,
        "B": 0.001 - 0.020 * alternating,
    })
    benchmark = 0.0003 + 0.010 * alternating
    return returns, benchmark


@pytest.mark.parametrize("with_etf", [False, True])
def test_complete_optimizer_reaches_known_hedged_optimum(
    monkeypatch, deterministic_search, with_etf
):
    """Référence calculée exhaustivement, pas simplement 'un score a augmenté'."""
    returns, benchmark = deterministic_search
    monkeypatch.setattr(optimizer, "load_etf_tickers", lambda: {"A"} if with_etf else set())
    weights, score, diagnostics = optimizer.optimize_portfolio_de(
        ["A", "B"], returns, [[True], [True]], ["IBKR"],
        current_weights={"A": 0.8, "B": 0.2},
        benchmark_returns=benchmark, n_sim=400, min_position=0.0,
        seed=17, return_diagnostics=True, discretize_cb=lambda matrix: matrix.copy(),
    )
    scenarios = returns.to_numpy()[:400]
    mean = returns.to_numpy().mean(axis=0)
    bench = starr.benchmark_stats(benchmark[:400], float(benchmark.mean()), Config.STARR_ALPHA, 0.0)
    grid = np.linspace(0.2, 0.8, 1001)
    exhaustive_scores = -starr.neg_benchmark_relative_batch(
        np.vstack((grid, 1.0 - grid)), scenarios, mean, bench,
        Config.STARR_ALPHA, Config.STARR_DOWNSIDE_WEIGHT,
        normalize_weights=False,
    )
    initial_score = -starr.neg_benchmark_relative(
        np.array([0.8, 0.2]), scenarios, mean, bench,
        Config.STARR_ALPHA, Config.STARR_DOWNSIDE_WEIGHT,
        normalize_weights=False,
    )
    assert weights.sum() == pytest.approx(1.0)
    assert score >= float(exhaustive_scores.max()) - 0.05
    available_gain = float(exhaustive_scores.max()) - initial_score
    assert available_gain > 0.5
    assert score > initial_score + 0.95 * available_gain
    executed = diagnostics["executed_portfolio"]
    assert executed["feasible_under_current_constraints"] is True
    assert executed["objective_score"] == pytest.approx(score, abs=1e-5)
    assert diagnostics["previous_run_champion"]["recomputed_executed_objective_score"] == pytest.approx(initial_score)
