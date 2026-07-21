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


def test_best_score_none_until_first_update():
    from app.services.finance.buffett import optimization_progress as op

    op.reset()
    op.start(run_id=1)
    assert op.snapshot()["best_score"] is None


def test_best_score_updated_and_persists_across_calls_without_it():
    from app.services.finance.buffett import optimization_progress as op

    op.reset()
    op.start(run_id=1)
    op.update_de(seed_num=1, iteration=1, convergence=0.1, best_score=0.42)
    assert op.snapshot()["best_score"] == 0.42
    # Un appel sans best_score (None) ne doit pas effacer la dernière valeur connue.
    op.update_de(seed_num=1, iteration=2, convergence=0.2)
    assert op.snapshot()["best_score"] == 0.42
    op.update_de(seed_num=1, iteration=3, convergence=0.3, best_score=0.55)
    assert op.snapshot()["best_score"] == 0.55
    op.reset()


def test_best_score_reset_to_none_by_start():
    from app.services.finance.buffett import optimization_progress as op

    op.reset()
    op.start(run_id=1)
    op.update_de(seed_num=1, iteration=1, convergence=0.1, best_score=0.9)
    op.start(run_id=2)  # nouveau run
    assert op.snapshot()["best_score"] is None
    op.reset()


def test_score_history_keeps_only_strict_improvements():
    from app.services.finance.buffett import optimization_progress as op

    op.reset()
    op.start(run_id=1)
    op.update_de(seed_num=1, iteration=1, convergence=0.1, best_score=-0.2)
    op.update_de(seed_num=1, iteration=2, convergence=0.2, best_score=0.4)
    op.update_de(seed_num=1, iteration=3, convergence=0.3, best_score=0.4)

    state = op.snapshot(history_after=0)
    assert state["best_score"] == 0.4
    assert state["total_iterations"] == 3
    assert state["score_history"] == [
        {"iteration": 2, "seed_num": 1, "seed_iteration": 2, "score": 0.4},
    ]
    assert op.snapshot(history_after=2)["score_history"] == []
    assert "score_history" not in op.snapshot()
    op.reset()


def test_initialization_progress_does_not_expose_negative_best_score():
    from app.services.finance.buffett import optimization_progress as op

    op.reset()
    op.start(run_id=1)
    op.update_initialization(attempt=3, maximum=10, best_score=-0.07)
    state = op.snapshot()
    assert state["phase"] == "initialisation"
    assert state["initialization_attempt"] == 3
    assert state["convergence"] == 0.3
    assert state["best_score"] is None
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
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.optimizer import optimize_portfolio_de

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    # Reglages DE allegés pour le test (la prod utilise tol=1e-6). Pas de
    # should_stop -> exactement 1 seed (comportement par defaut).
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 5)
    monkeypatch.setattr(Config, "STARR_DE_TOL", 1e-3)
    # Univers synthétique de 3 titres: les contraintes réelles (pays <=25 %,
    # défensif >=30 %) peuvent être mathématiquement infaisables ici.
    monkeypatch.setattr(Config, "MIN_DEFENSIVE_PCT", 0.0)
    monkeypatch.setattr(Config, "MAX_COUNTRY_PCT", 1.0)
    monkeypatch.setattr(Config, "STARR_CARD_BETA", 0.0)
    rng = np.random.default_rng(0)
    rets = pd.DataFrame(rng.normal(0.001, 0.02, (300, 3)), columns=["A", "B", "C"])
    matrix = [[True], [True], [True]]

    calls: list[tuple[int, int, float, float]] = []
    weights, sharpe = optimize_portfolio_de(
        ["A", "B", "C"],
        rets,
        matrix,
        ["IBKR"],
        n_sim=2000,
        progress_cb=lambda seed_num, it, conv, best=None: calls.append((seed_num, it, conv, best)),
    )
    assert len(calls) > 0
    assert all(c[0] == 1 for c in calls)  # un seul seed
    # itérations (dans ce seed) strictement croissantes
    iters = [c[1] for c in calls]
    assert iters == sorted(iters)
    assert weights.shape == (3, 1)
    # best_score (4e argument) fourni à chaque appel, jamais None une fois le
    # DE démarré (population_energies[0] est toujours fini dès la génération 1).
    assert all(c[3] is not None for c in calls)
