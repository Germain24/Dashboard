from __future__ import annotations

import pandas as pd
import pytest


def test_resume_throughput_ignores_already_completed(monkeypatch):
    from app.services.finance.buffett import progress_state

    ticks = iter([10.0, 10.0, 10.0, 70.0])
    monkeypatch.setattr(progress_state.time, "monotonic", lambda: next(ticks))
    progress_state.start(run_id=52, total=35_813, already_completed=33_708)
    progress_state.update(done=33_718)
    snapshot = progress_state.snapshot()

    assert snapshot["already_completed"] == 33_708
    assert snapshot["session_processed"] == 10
    assert snapshot["throughput_per_min"] == 10.0


def test_proshares_short_is_inverse_but_short_duration_is_plain():
    from app.services.finance.buffett.leverage_filter import classify_product_strategy

    assert classify_product_strategy("ProShares Short Russell2000") == "inverse"
    assert classify_product_strategy("PGIM Short Duration High Yield ETF") == "plain"
    assert classify_product_strategy("Direxion Daily S&P 500 Bull 3X Shares") == "leveraged"


def test_primary_market_precedes_secondary_volume():
    from app.services.finance.buffett.dedup import deduplicate_tickers

    returns = pd.DataFrame(columns=["OR.PA", "LOR.DE"])
    metadata = pd.DataFrame([
        {
            "Ticker Yahoo Finance": "OR.PA",
            "Nom": "L'Oréal S.A.",
            "Secteur": "Consumer Defensive",
            "Volume": 100.0,
            "ISIN": "FR0000120321",
            "Primary Market": True,
        },
        {
            "Ticker Yahoo Finance": "LOR.DE",
            "Nom": "L'Oréal S.A.",
            "Secteur": "Consumer Defensive",
            "Volume": 1_000.0,
            "ISIN": "FR0000120321",
            "Primary Market": False,
        },
    ])

    selected = deduplicate_tickers(returns, metadata)
    assert list(selected.columns) == ["OR.PA"]


def test_real_broker_positions_are_kept_separate(tmp_path):
    from sqlmodel import Session, SQLModel, create_engine

    from app.models.finance import Position
    from app.services.finance.buffett.broker_positions import current_broker_weights

    engine = create_engine(f"sqlite:///{tmp_path / 'positions.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Position(ticker="OR.PA", broker="Bourse Direct", quantite=2))
        session.add(Position(ticker="GLD", broker="Trading212", quantite=1))
        session.commit()
        weights = current_broker_weights(
            session,
            prices_eur={"OR.PA": 400.0, "GLD": 200.0},
            total_capital_eur=1_000.0,
            active_brokers=["BoursDirect2", "Trading212"],
        )

    assert weights["BoursDirect2"] == {"OR.PA": 0.8}
    assert weights["Trading212"] == {"GLD": 0.2}


def test_first_year_cost_does_not_repeat_the_rebalance_four_times():
    from app.services.finance.buffett.transaction_costs import first_year_cost_summary

    summary = first_year_cost_summary(188.59, 8.89, 28_836.0)

    assert summary["first_year_cost_eur"] == pytest.approx(197.48)
    assert summary["first_year_cost_pct"] == pytest.approx(197.48 / 28_836.0)


def test_scipy_convergence_never_ends_a_continuous_run(monkeypatch):
    """La dispersion scipy ne constitue plus la convergence métier.

    Ce test gardait auparavant `should_start_another_seed` : à la convergence,
    une seed suivante était relancée jusqu'à l'arrêt utilisateur. Le recuit a
    remplacé les seeds indépendantes par UNE recherche continue, et cette
    fonction a disparu — mais l'invariant qu'elle protégeait tient toujours et
    se vérifie désormais sur la boucle elle-même.
    """
    import numpy as np
    import pandas as pd

    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.optimizer import optimize_portfolio_de

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    monkeypatch.setattr(Config, "MIN_DEFENSIVE_PCT", 0.0)
    monkeypatch.setattr(Config, "MAX_COUNTRY_PCT", 1.0)
    monkeypatch.setattr(Config, "STARR_CARD_BETA", 0.0)
    monkeypatch.setattr(Config, "STARR_STRESS_WEIGHT", 0.0)
    monkeypatch.setattr(Config, "TRANSACTION_COSTS_ENABLED", False)
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 1)
    monkeypatch.setattr(Config, "STARR_DE_MAX_GENERATIONS", 60)
    monkeypatch.setattr(Config, "STARR_DE_HOT_CONVERGENCE_GENERATIONS", 5)
    monkeypatch.setattr(Config, "STARR_DE_POPSIZE", 12)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_BATCH_SIZE", 16)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_MAX_BATCHES", 4)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_BATCHES", 2)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_COUNT", 3)
    monkeypatch.setattr(Config, "STARR_DE_POLISH_MAXITER", 2)
    # Tolérance ÉNORME : `converged()` est vrai dès la première génération. Si
    # la convergence suffisait à terminer, le run s'arrêterait aussitôt.
    monkeypatch.setattr(Config, "STARR_DE_TOL", 1e9)

    rng = np.random.default_rng(17)
    jours = int(Config.STARR_MIN_HISTORY_DAYS)
    rets = pd.DataFrame(
        rng.normal(0.0005, 0.02, (jours, 3)), columns=["A", "B", "C"]
    )

    # `should_stop` est aussi consulté pendant l'initialisation et le criblage
    # des élites, pas seulement une fois par génération : on ne peut donc pas
    # déduire un numéro de génération du nombre d'appels.
    appels_avant_arret = 8
    vues = {"n": 0}

    def _should_stop() -> bool:
        vues["n"] += 1
        return vues["n"] > appels_avant_arret

    _poids, score, diagnostics = optimize_portfolio_de(
        ["A", "B", "C"], rets, [[True]] * 3, ["IBKR"], n_sim=300,
        benchmark_returns=rng.normal(0.0004, 0.01, jours),
        should_stop=_should_stop,
        continuous_until_stopped=True,
        return_diagnostics=True,
    )

    assert np.isfinite(score)
    termination = diagnostics["termination"]
    assert termination["reason"] == "user_stop"
    # Le cœur du test : `converged()` était vrai DÈS la première génération, et
    # pourtant la boucle a continué. L'arrêt manuel conclut sur 5 générations
    # chaudes sans amélioration, pas sur la dispersion scipy.
    assert termination["detail"] == "convergence_apres_arret"
    assert termination["generations"] > 1
