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

    op.update_de(iteration=3, convergence=0.4)
    s = op.snapshot()
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
    op.update_de(iteration=1, convergence=5.0)  # scipy peut dépasser 1
    assert op.snapshot()["convergence"] == 1.0
    op.update_de(iteration=2, convergence=-0.2)
    assert op.snapshot()["convergence"] == 0.0
    op.reset()


def test_optimize_portfolio_de_reports_progress(monkeypatch):
    """optimize_portfolio_de doit appeler progress_cb(iteration, convergence)
    à chaque génération du Differential Evolution."""
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    rng = np.random.default_rng(0)
    rets = pd.DataFrame(rng.normal(0.001, 0.02, (300, 3)), columns=["A", "B", "C"])
    matrix = [[True], [True], [True]]

    calls: list[tuple[int, float]] = []
    weights, sharpe = optimize_portfolio_de(
        ["A", "B", "C"], rets, matrix, ["IBKR"], n_sim=2000,
        progress_cb=lambda it, conv: calls.append((it, conv)),
    )
    assert len(calls) > 0
    # itérations strictement croissantes
    iters = [c[0] for c in calls]
    assert iters == sorted(iters)
    assert weights.shape == (3, 1)
