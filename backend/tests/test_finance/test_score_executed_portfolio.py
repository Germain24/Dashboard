"""Le score doit porter sur le portefeuille RÉELLEMENT ACHETÉ.

`optimize_portfolio_de` note des poids CONTINUS. L'appelant discrétise ensuite en
actions entières (et en pies Trading212) et, jusqu'ici, plus rien ne rescorait le
résultat : seule la conformité sectorielle était revérifiée. L'écart d'arrondi
restait donc invisible, alors qu'il est loin d'être négligeable sur des lignes à
forte valeur unitaire.
"""

import numpy as np
import pandas as pd
import pytest

from app.services.finance.buffett.allocation import alloc_to_weight_matrix
from app.services.finance.buffett.config import Config
from app.services.finance.buffett.optimizer import (
    INVALID_OBJECTIVE_ENERGY,
    InvalidOptimizationObjective,
    find_positive_random_seed,
    optimize_portfolio_de,
)


@pytest.fixture
def _fast_de(monkeypatch):
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 10_000.0})
    monkeypatch.setattr(Config, "MIN_DEFENSIVE_PCT", 0.0)
    monkeypatch.setattr(Config, "MAX_COUNTRY_PCT", 1.0)
    monkeypatch.setattr(Config, "MAX_SECTOR_PCT", 1.0)
    monkeypatch.setattr(Config, "STARR_STRESS_WEIGHT", 0.0)
    monkeypatch.setattr(Config, "TRANSACTION_COSTS_ENABLED", False)
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 1)
    monkeypatch.setattr(Config, "STARR_DE_MAX_GENERATIONS", 3)
    monkeypatch.setattr(Config, "STARR_DE_POPSIZE", 8)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_BATCH_SIZE", 16)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_MAX_BATCHES", 5)
    monkeypatch.setattr(Config, "STARR_DE_POLISH_MAXITER", 2)


def _universe(n=5, seed=5):
    rng = np.random.default_rng(seed)
    days = int(Config.STARR_MIN_HISTORY_DAYS)
    rets = pd.DataFrame(
        rng.normal(0.0006, 0.02, (days, n)), columns=[f"T{i}" for i in range(n)]
    )
    return rets, rng.normal(0.0004, 0.01, days)


def test_executed_portfolio_is_scored_and_its_drift_reported(_fast_de):
    rets, bench = _universe()
    tickers = list(rets.columns)

    def _to_whole_shares(continuous):
        """Discrétisation grossière : arrondi à 5 % près, comme un gros lot."""
        arr = np.asarray(continuous, dtype=float)
        return np.round(arr / 0.05) * 0.05

    _w, _score, diagnostics = optimize_portfolio_de(
        tickers, rets, [[True]] * len(tickers), ["IBKR"], n_sim=400,
        benchmark_returns=bench,
        discretize_cb=_to_whole_shares,
        return_diagnostics=True,
    )

    executed = diagnostics["executed_portfolio"]
    assert executed is not None
    assert np.isfinite(executed["score"])
    assert executed["drift"] == pytest.approx(
        executed["score"] - executed["score_continuous"]
    )
    assert executed["lines_by_broker"]["IBKR"] >= 1
    assert 0.0 <= executed["cash_weight"] <= 1.0
    assert "terms" in executed


def test_without_the_callback_nothing_is_claimed(_fast_de):
    """Mieux vaut None qu'un score d'exécution inventé."""
    rets, bench = _universe()
    _w, _s, diagnostics = optimize_portfolio_de(
        list(rets.columns), rets, [[True]] * 5, ["IBKR"], n_sim=400,
        benchmark_returns=bench, return_diagnostics=True,
    )
    assert diagnostics["executed_portfolio"] is None


def test_a_broken_callback_never_breaks_the_optimisation(_fast_de):
    rets, bench = _universe()

    def _boom(_w):
        raise RuntimeError("discrétisation indisponible")

    weights, _score, diagnostics = optimize_portfolio_de(
        list(rets.columns), rets, [[True]] * 5, ["IBKR"], n_sim=400,
        benchmark_returns=bench, discretize_cb=_boom, return_diagnostics=True,
    )
    assert diagnostics["executed_portfolio"] is None
    assert np.isfinite(np.asarray(weights, dtype=float)).all()


def test_a_wrongly_shaped_callback_is_ignored(_fast_de):
    rets, bench = _universe()
    _w, _s, diagnostics = optimize_portfolio_de(
        list(rets.columns), rets, [[True]] * 5, ["IBKR"], n_sim=400,
        benchmark_returns=bench,
        discretize_cb=lambda _w: np.zeros((2, 2)),
        return_diagnostics=True,
    )
    assert diagnostics["executed_portfolio"] is None


def test_identity_discretisation_leaves_no_drift(_fast_de):
    """Garde-fou de cohérence : même portefeuille => même score, écart nul."""
    rets, bench = _universe()
    _w, _s, diagnostics = optimize_portfolio_de(
        list(rets.columns), rets, [[True]] * 5, ["IBKR"], n_sim=400,
        benchmark_returns=bench,
        discretize_cb=lambda w: np.asarray(w, dtype=float).copy(),
        return_diagnostics=True,
    )
    executed = diagnostics["executed_portfolio"]
    assert executed["drift"] == pytest.approx(0.0, abs=1e-6)


# ── Sentinelle graduée : elle doit rester INVALIDE malgré son gradient ──────


def test_graded_sentinel_is_still_rejected_as_invalid():
    """`base[infaisable] = 1e6 + pénalité` doit rester au-dessus du seuil.

    Sans cet invariant, un candidat infaisable pourrait être accepté comme point
    de départ et toutes les seeds repartiraient d'une erreur numérique.
    """
    def graded_sentinel(X):
        return np.full(np.asarray(X).shape[1], INVALID_OBJECTIVE_ENERGY + 12.5)

    with pytest.raises(InvalidOptimizationObjective):
        find_positive_random_seed(
            6, np.random.default_rng(0), graded_sentinel,
            batch_size=8, max_batches=2,
        )


def test_grading_preserves_the_lexicographic_order():
    """Un candidat faisable reste toujours très loin sous tout infaisable."""
    faisable = -7.9          # un bon score, donc une énergie négative
    proche = INVALID_OBJECTIVE_ENERGY + 0.01
    lointain = INVALID_OBJECTIVE_ENERGY + 250.0
    assert faisable < proche < lointain
    # ... et les infaisables sont désormais ORDONNÉS entre eux (plateau plat avant).
    assert proche != lointain


def test_weight_matrix_round_trip_through_a_discretisation(monkeypatch):
    """Le chemin réel des appelants : discrétiser puis reconstruire les poids."""
    from app.services.finance.buffett.allocation import discretize_allocation

    # Sans budget déclaré pour le broker, la discrétisation ne produit rien.
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    alloc = discretize_allocation(
        ["A", "B"], np.array([[0.5], [0.5]]), ["IBKR"],
        {"A": 100.0, "B": 50.0}, 1000.0,
    )
    matrix = alloc_to_weight_matrix(alloc, ["A", "B"], ["IBKR"], 1000.0)
    assert matrix.shape == (2, 1)
    assert matrix.sum() <= 1.0 + 1e-9
    assert matrix.sum() > 0.0
