"""Barre de progression de l'optimisation de portefeuille (Differential Evolution)."""

import numpy as np
import pandas as pd
import pytest


def test_score_threshold_does_not_keep_previous_allocation_below_80():
    from app.services.finance.buffett.optimizer import (
        meets_optimization_score_threshold,
    )

    assert not meets_optimization_score_threshold("HEN3.DE", 78.16, 80.0)
    assert meets_optimization_score_threshold("QUAL.PA", 80.0, 80.0)
    assert meets_optimization_score_threshold("ETF.PA", 0.0, 80.0, is_etf=True)
    assert meets_optimization_score_threshold(
        "FORCED.PA",
        12.0,
        80.0,
        {"forced.pa"},
    )


def test_v3_threshold_filters_quality_confidence_and_comparability():
    from app.services.finance.buffett.optimizer import (
        meets_optimization_score_threshold,
    )

    base = dict(
        ticker="QUALITY", score=75.0, threshold=80.0,
        quality_score=85.0, confidence_pct=40.0,
    )
    assert meets_optimization_score_threshold(**base)
    assert not meets_optimization_score_threshold(**(base | {"quality_score": 79.9}))
    assert not meets_optimization_score_threshold(**(base | {"confidence_pct": 34.9}))
    assert not meets_optimization_score_threshold(
        **base, comparable_to_standard=False
    )


def test_optimization_progress_lifecycle():
    from app.services.finance.buffett import optimization_progress as op

    op.reset()
    op.start(run_id=1)
    op.update_de(1, 1, 0.1, 1.0, seed_score=1.0, temperature=0.7)
    op.update_de(1, 2, 0.2, 1.0, seed_score=1.0)  # appelant historique
    points = op.snapshot(history_after=0)["score_history"]
    assert points[0]["temperature"] == 0.7
    assert "temperature" not in points[1]
    op.reset()
    assert op.snapshot()["active"] is False

    op.start(run_id=5, message="Préparation")
    s = op.snapshot()
    assert s["active"] is True
    assert s["run_id"] == 5
    assert isinstance(s["optimization_id"], str)
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


def test_preparation_progress_exposes_item_and_stall_age(monkeypatch):
    from app.services.finance.buffett import optimization_progress as op

    op.start(run_id=62, message="Préparation")
    op.set_phase(
        "preparation",
        "Indices officiels 12/100 · TOPIX",
        done=12,
        total=100,
        current_item="TOPIX",
    )
    active = op.snapshot()
    monkeypatch.setattr(op.time, "time", lambda: active["last_activity_at"] + 121)
    stalled = op.snapshot()

    assert stalled["phase_done"] == 12
    assert stalled["phase_total"] == 100
    assert stalled["progress_pct"] == 12.0
    assert stalled["current_item"] == "TOPIX"
    assert stalled["stalled"] is True


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


def test_start_creates_new_optimization_identity_for_same_run():
    from app.services.finance.buffett import optimization_progress as op

    op.reset()
    op.start(run_id=7)
    first = op.snapshot()["optimization_id"]
    op.update_de(seed_num=1, iteration=1, convergence=0.1, best_score=0.4)

    op.start(run_id=7)
    state = op.snapshot(history_after=0)
    assert state["run_id"] == 7
    assert state["optimization_id"] != first
    assert state["total_iterations"] == 0
    assert state["score_history"] == []
    op.reset()
    op.start(run_id=1)
    op.update_de(seed_num=1, iteration=1, convergence=0.1, best_score=0.9)
    op.start(run_id=2)  # nouveau run
    assert op.snapshot()["best_score"] is None
    op.reset()


def test_score_history_keeps_every_generation_and_separates_seed_score():
    from app.services.finance.buffett import optimization_progress as op

    op.reset()
    op.start(run_id=1)
    op.update_de(
        seed_num=1,
        iteration=1,
        convergence=0.1,
        best_score=0.6,
        seed_score=0.2,
    )
    op.update_de(
        seed_num=1,
        iteration=2,
        convergence=0.2,
        best_score=0.6,
        seed_score=0.4,
    )
    op.update_de(
        seed_num=2,
        iteration=1,
        convergence=0.3,
        best_score=0.7,
        seed_score=0.7,
    )

    state = op.snapshot(history_after=0)
    assert state["best_score"] == 0.7
    assert state["seed_score"] == 0.7
    assert state["total_iterations"] == 3
    assert state["score_history"] == [
        {
            "iteration": 1,
            "seed_num": 1,
            "seed_iteration": 1,
            "score": 0.2,
            "global_best_score": 0.6,
        },
        {
            "iteration": 2,
            "seed_num": 1,
            "seed_iteration": 2,
            "score": 0.4,
            "global_best_score": 0.6,
        },
        {
            "iteration": 3,
            "seed_num": 2,
            "seed_iteration": 1,
            "score": 0.7,
            "global_best_score": 0.7,
        },
    ]
    assert op.snapshot(history_after=2)["score_history"] == [
        {
            "iteration": 3,
            "seed_num": 2,
            "seed_iteration": 1,
            "score": 0.7,
            "global_best_score": 0.7,
        }
    ]
    assert "score_history" not in op.snapshot()
    op.reset()


def test_seed_score_keeps_the_seed_maximum_and_resets_on_new_seed():
    from app.services.finance.buffett import optimization_progress as op

    op.reset()
    op.start(run_id=1)
    op.update_de(seed_num=1, iteration=1, convergence=0.1, best_score=1.0, seed_score=1.0)
    op.update_de(seed_num=1, iteration=2, convergence=0.2, best_score=1.0, seed_score=0.5)
    assert op.snapshot()["seed_score"] == pytest.approx(1.0)
    assert [point["score"] for point in op.snapshot(history_after=0)["score_history"]] == [1.0, 1.0]

    op.update_de(seed_num=2, iteration=1, convergence=0.1, best_score=1.0, seed_score=0.2)
    assert op.snapshot()["seed_score"] == pytest.approx(0.2)
    op.reset()


def test_initialization_progress_reports_negative_benchmark_relative_score():
    from app.services.finance.buffett import optimization_progress as op

    op.reset()
    op.start(run_id=1)
    op.update_initialization(attempt=3, maximum=10, best_score=-0.07)
    state = op.snapshot()
    assert state["phase"] == "initialisation"
    assert state["initialization_attempt"] == 3
    assert state["convergence"] == 0.3
    assert state["best_score"] == pytest.approx(-0.07)
    op.update_initialization(attempt=4, maximum=10, best_score=-0.2)
    assert op.snapshot()["best_score"] == pytest.approx(-0.07)
    op.update_initialization(attempt=5, maximum=10, best_score=0.0)
    assert op.snapshot()["best_score"] == 0.0
    op.reset()


@pytest.mark.parametrize("score", [float("nan"), float("inf"), float("-inf")])
def test_progress_ignores_nonfinite_scores(score):
    from app.services.finance.buffett import optimization_progress as op

    op.start(run_id=1)
    op.update_initialization(attempt=1, maximum=10, best_score=score)
    op.update_de(seed_num=1, iteration=1, convergence=0.1, best_score=score)
    assert op.snapshot()["best_score"] is None
    op.update_de(seed_num=1, iteration=2, convergence=0.2, best_score=-1.5)
    assert op.snapshot()["best_score"] == -1.5
    op.reset()


def test_request_stop_sets_flag_reset_by_start():
    from app.services.finance.buffett import optimization_progress as op

    op.reset()
    assert op.snapshot()["stop_requested"] is False
    # Un arrêt hors optimisation est ignoré; une optimisation active l'accepte.
    assert op.request_stop() is False
    op.start(run_id=1)
    assert op.request_stop() is True
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
    # Le score mesure désormais l'écart à un benchmark : celui-ci est une entrée
    # obligatoire de l'optimiseur (cf. test_benchmark_injection.py).
    # Au moins STARR_MIN_HISTORY_DAYS points : l'optimiseur refuse un benchmark
    # trop court. Seules les dernières lignes, alignées sur `rets`, sont utilisées.
    benchmark = pd.Series(rng.normal(0.0008, 0.018, 800))
    weights, sharpe = optimize_portfolio_de(
        ["A", "B", "C"],
        rets,
        matrix,
        ["IBKR"],
        n_sim=2000,
        benchmark_returns=benchmark,
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


def test_optimizer_returns_at_generation_boundary_for_etf_refresh(monkeypatch):
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.optimizer import optimize_portfolio_de

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 1)
    monkeypatch.setattr(Config, "STARR_DE_MAX_GENERATIONS", 10)
    monkeypatch.setattr(Config, "STARR_DE_POPSIZE", 16)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_BATCH_SIZE", 16)
    monkeypatch.setattr(Config, "MIN_DEFENSIVE_PCT", 0.0)
    monkeypatch.setattr(Config, "MAX_COUNTRY_PCT", 1.0)
    monkeypatch.setattr(Config, "STARR_CARD_BETA", 0.0)
    monkeypatch.setattr(Config, "TRANSACTION_COSTS_ENABLED", False)
    rng = np.random.default_rng(44)
    rets = pd.DataFrame(
        rng.normal(0.001, 0.02, (300, 3)),
        columns=["A", "B", "C"],
    )
    benchmark = pd.Series(rng.normal(0.0008, 0.018, 800))
    progress = []
    weights, score, diagnostics = optimize_portfolio_de(
        list(rets.columns),
        rets,
        [[True], [True], [True]],
        ["IBKR"],
        n_sim=500,
        benchmark_returns=benchmark,
        should_restart=lambda: True,
        seed_number_offset=4,
        progress_cb=lambda seed_num, *_args, **_kwargs: progress.append(seed_num),
        return_diagnostics=True,
    )
    assert diagnostics["termination"]["reason"] == "etf_composition_refresh"
    # La recherche tient désormais en UNE seed continue : plus de liste `runs`,
    # mais le nombre de générations effectuées avant la reprise.
    assert diagnostics["termination"]["generations"] >= 1
    assert diagnostics["termination"]["continuous"] is False
    # `seed_number_offset` numérote toujours les CYCLES de rafraîchissement ETF,
    # ce dont le graphe se sert pour séparer ses séries.
    assert progress == [5]
    assert weights.shape == (3, 1)
    assert np.isfinite(score)


def test_objective_refresh_resets_best_but_keeps_history():
    from app.services.finance.buffett import optimization_progress as op

    op.start(run_id=99)
    op.update_de(1, 1, 0.2, 3.5, seed_score=3.5)
    before = op.snapshot(0)
    op.reset_objective_score("Nouvelle composition ETF")
    after = op.snapshot(0)
    assert before["best_score"] == 3.5
    assert after["best_score"] is None
    assert after["total_iterations"] == before["total_iterations"]
    assert after["score_history"] == before["score_history"]
    op.reset()


def test_history_point_carries_the_temperature_that_produced_it():
    """La courbe du front est colorée par la température de CHAQUE génération.

    Elle doit donc voyager dans le point d'historique, et non seulement dans
    l'état courant : sinon tous les points anciens se verraient attribuer la
    dernière température connue.
    """
    from app.services.finance.buffett import optimization_progress as op

    op.reset()
    op.start(run_id=1)
    op.update_de(1, 1, 0.1, 1.0, seed_score=1.0, temperature=0.9)
    op.update_de(1, 2, 0.2, 1.0, seed_score=1.0, temperature=0.2)
    points = op.snapshot(history_after=0)["score_history"]
    assert [p["temperature"] for p in points] == [0.9, 0.2]
    op.reset()


def test_a_caller_without_temperature_leaves_the_point_untouched():
    """Rétro-compatibilité : sans température fournie, aucune clé n'apparaît.

    On n'hérite PAS de la dernière température connue — un point porterait alors
    une valeur qui n'est pas la sienne, et la courbe mentirait.
    """
    from app.services.finance.buffett import optimization_progress as op

    op.reset()


def test_history_point_carries_the_retained_forced_tickers():
    from app.services.finance.buffett import optimization_progress as op

    op.reset()
    op.start(run_id=1)
    op.update_de(
        1,
        12,
        0.4,
        2.0,
        seed_score=1.8,
        temperature=1.0,
        forced_labels=["CW8.PA ≥ 10.0%", "DFEN.DE ≥ 2.9% (max broker)"],
        forced_action_count=1,
        forced_etf_count=1,
    )
    point = op.snapshot(history_after=0)["score_history"][0]
    assert point["forced_labels"] == [
        "CW8.PA ≥ 10.0%",
        "DFEN.DE ≥ 2.9% (max broker)",
    ]
    assert point["forced_action_count"] == 1
    assert point["forced_etf_count"] == 1
    op.reset()
