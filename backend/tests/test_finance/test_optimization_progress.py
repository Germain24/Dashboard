"""Barre de progression de l'optimisation de portefeuille (Differential Evolution)."""

import numpy as np
import pandas as pd


def test_optimization_progress_lifecycle():
    from app.services.finance.buffett import optimization_progress as op

    op.reset()
    assert op.snapshot()["active"] is False

    op.start(run_id=5, message="Préparation")
    s = op.snapshot()
    assert s["active"] is True
    assert s["run_id"] == 5
    assert s["message"] == "Préparation"

    op.update_de(seed_num=1, iteration=3, convergence=0.4)
    s = op.snapshot()
    assert s["seed_num"] == 1
    assert s["iteration"] == 3
    assert abs(s["convergence"] - 0.4) < 1e-9
    assert s["phase"] == "optimisation"

    op.finish(message="Terminé")
    s = op.snapshot()
    assert s["active"] is False
    assert s["message"] == "Terminé"


def test_optimization_progress_convergence_clamped_0_1():
    from app.services.finance.buffett import optimization_progress as op

    op.reset()
    op.start(run_id=1)
    op.update_de(seed_num=1, iteration=1, convergence=5.0)  # scipy peut dépasser 1
    assert op.snapshot()["convergence"] == 1.0
    op.update_de(seed_num=1, iteration=2, convergence=-0.2)
    assert op.snapshot()["convergence"] == 0.0
    op.reset()


def test_update_de_tracks_seed_num():
    from app.services.finance.buffett import optimization_progress as op

    op.reset()
    op.start(run_id=1)
    op.update_de(seed_num=1, iteration=5, convergence=0.1)
    assert op.snapshot()["seed_num"] == 1
    op.update_de(seed_num=4, iteration=12, convergence=0.3)
    assert op.snapshot()["seed_num"] == 4
    assert op.snapshot()["iteration"] == 12
    op.reset()


def test_request_stop_sets_flag_reset_by_start():
    from app.services.finance.buffett import optimization_progress as op

    op.reset()
    assert op.snapshot()["stop_requested"] is False
    op.request_stop()
    assert op.snapshot()["stop_requested"] is True
    # Un nouveau start() (nouveau run) doit remettre le flag a zero.
    op.start(run_id=2)
    assert op.snapshot()["stop_requested"] is False
    op.reset()


def test_optimize_portfolio_de_reports_progress(monkeypatch):
    """optimize_portfolio_de doit appeler progress_cb(seed_num, iteration,
    convergence) à chaque génération du Differential Evolution."""
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    # Reglages DE allegés pour le test (la prod utilise tol=1e-6). Pas de
    # should_stop -> exactement 1 seed (comportement par defaut).
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 5)
    monkeypatch.setattr(Config, "STARR_DE_TOL", 1e-3)
    rng = np.random.default_rng(0)
    rets = pd.DataFrame(rng.normal(0.001, 0.02, (300, 3)), columns=["A", "B", "C"])
    matrix = [[True], [True], [True]]

    calls: list[tuple[int, int, float]] = []
    weights, sharpe = optimize_portfolio_de(
        ["A", "B", "C"], rets, matrix, ["IBKR"], n_sim=2000,
        progress_cb=lambda seed_num, it, conv: calls.append((seed_num, it, conv)),
    )
    assert len(calls) > 0
    assert all(c[0] == 1 for c in calls)   # un seul seed
    # itérations (dans ce seed) strictement croissantes
    iters = [c[1] for c in calls]
    assert iters == sorted(iters)
    assert weights.shape == (3, 1)
