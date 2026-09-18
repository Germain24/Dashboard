"""Exercise the manual portfolio job with isolated prices, catalog and database."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest
from sqlmodel import Session

from app.models.finance import BuffettRun, BuffettRunResult


@pytest.fixture
def creation_job(monkeypatch, patched_db_engine):
    from app.api.finance.buffett import _run_portfolio_creation
    from app.services.finance import yf_session
    from app.services.finance.buffett import (
        allocation,
        broker_availability,
        broker_budgets,
        dedup,
        equity_lookthrough,
        etf_composition_batches,
        etf_index_registry,
        optimization_progress,
        optimizer,
    )
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "load_params", lambda: None)
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1_000.0})
    monkeypatch.setattr(Config, "FORCED_BUY_TICKERS", set())
    monkeypatch.setattr(Config, "STARR_MIN_HISTORY_DAYS", 3)
    monkeypatch.setattr(Config, "STARR_BENCHMARK_TICKER", "BENCH")
    monkeypatch.setattr(broker_budgets, "apply_live_broker_budgets", lambda: {})
    rows = [
        BuffettRunResult(ticker="FR", nom="France", pays="France", secteur="Technology"),
        BuffettRunResult(ticker="JP", nom="Japan", pays="Japan", secteur="Healthcare"),
        BuffettRunResult(ticker="WORLD", nom="World tracker", secteur="ETF"),
    ]
    with Session(patched_db_engine, expire_on_commit=False) as session:
        run = BuffettRun(run_date=dt.date(2026, 9, 15), statut="termine")
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id
        for row in rows:
            row.run_id = run_id
            row.chance_moat = 95.0
            row.achat = True
            row.volume = 1e9
            session.add(row)
        session.commit()

    table = pd.DataFrame([
        {"Ticker Yahoo Finance": row.ticker, "Nom": row.nom, "Secteur": row.secteur,
         "IBKR": True}
        for row in rows
    ])
    monkeypatch.setattr(broker_availability, "load_broker_table", lambda: table.copy())
    monkeypatch.setattr(broker_availability, "load_etf_tickers", lambda *_: {"WORLD"})
    monkeypatch.setattr(broker_availability, "current_target_weights", lambda *_: {})
    monkeypatch.setattr(broker_availability, "update_broker_file_weights", lambda *_: 0)
    monkeypatch.setattr(
        broker_availability, "merge_broker_columns",
        lambda frame, *_args, **_kwargs: frame.assign(IBKR=True).assign(**{
            "Secteur 1": np.where(frame["Ticker Yahoo Finance"] == "WORLD", "ETF", "Actions"),
            "Secteur 4": np.where(frame["Ticker Yahoo Finance"] == "WORLD", "Monde", ""),
        }),
    )
    monkeypatch.setattr(dedup, "deduplicate_tickers", lambda returns, *_: returns)
    monkeypatch.setattr(dedup, "returns_in_base_currency", lambda returns, *_a, **_k: returns)
    monkeypatch.setattr(etf_index_registry, "resolve_index_registry", lambda *_a, **_k: {})
    prices = pd.DataFrame(
        {ticker: np.linspace(90.0, 100.0, 8) for ticker in ["FR", "JP", "WORLD", "BENCH"]},
        index=pd.date_range("2026-01-01", periods=8),
    )
    monkeypatch.setattr(yf_session, "download_prices_bulk_with_retry", lambda tickers, **_: prices[tickers])
    monkeypatch.setattr(allocation, "close_prices_from_download", lambda raw, _: raw)
    monkeypatch.setattr(allocation, "average_turnover_eur_from_download", lambda *_: {})
    monkeypatch.setattr(allocation, "latest_prices_eur", lambda _raw, tickers: {t: 100.0 for t in tickers})
    monkeypatch.setattr(
        etf_composition_batches, "select_verified_etfs_per_broker",
        lambda returns, frame, *_a, **_k: etf_composition_batches.EtfCompositionBatchResult(
            returns=returns, frame=frame, selection_diagnostics={},
        ),
    )
    sectors = {"WORLD": {"Technology": 0.6, "Healthcare": 0.4}}
    monkeypatch.setattr(
        equity_lookthrough, "index_risk_lookthrough",
        lambda *_: ({"WORLD": {"France": 0.6, "Japan": 0.4}}, sectors.copy(), {}),
    )
    monkeypatch.setattr(equity_lookthrough, "index_sector_country_lookthrough", lambda *_: {})
    seen = {"discretizations": [], "sector_checks": []}

    def discretize(tickers, weights, brokers, _prices, total_cap, **kwargs):
        seen["discretizations"].append(kwargs)
        return [
            {"Ticker": ticker, "Broker": brokers[0], "Poids total (%)": float(weight[0]) * 100,
             "eur": float(weight[0]) * total_cap, "prix": 100.0, "type": "shares", "shares": 1}
            for ticker, weight in zip(tickers, weights, strict=True)
        ]

    monkeypatch.setattr(allocation, "discretize_allocation", discretize)

    def sector_check(_alloc, **kwargs):
        seen["sector_checks"].append(kwargs)
        return {"compliant": True}

    monkeypatch.setattr(allocation, "allocation_sector_diagnostics", sector_check)

    def optimize(tickers, returns, access, brokers, **kwargs):
        seen["optimizer"] = kwargs
        seen["tickers"] = tickers
        weights = np.full((len(tickers), 1), 1.0 / len(tickers))
        kwargs["discretize_cb"](weights)
        return weights, 1.0, {
            "executed_portfolio": {"score": 1.0}, "sector_constraints": {},
            "termination": {"reason": "user_stop"},
        }

    monkeypatch.setattr(optimizer, "optimize_portfolio_de", optimize)
    optimization_progress.reset()
    yield lambda include_etfs=True: _run_portfolio_creation(run_id, 80.0, include_etfs), seen
    optimization_progress.reset()


@pytest.mark.parametrize("include_etfs", [True, False])
def test_manual_creation_preserves_country_and_sector_lookthrough(creation_job, include_etfs):
    from app.services.finance.buffett import optimization_progress

    run, seen = creation_job
    run(include_etfs)

    assert optimization_progress.snapshot()["status"] == "stopped"
    assert seen["optimizer"]["country_exposures"]["FR"] == {"France": 1.0}
    assert seen["optimizer"]["country_exposures"]["JP"] == {"Japan": 1.0}
    assert ("WORLD" in seen["tickers"]) is include_etfs
    expected = seen["optimizer"]["sector_exposures_by_ticker"]
    assert len(seen["discretizations"]) == 2
    assert all(item["sector_exposures_by_ticker"] == expected for item in seen["discretizations"])
    assert seen["sector_checks"][0]["sector_exposures_by_ticker"] == expected


def test_manual_creation_surfaces_preparation_failure(creation_job, monkeypatch):
    from app.services.finance.buffett import broker_budgets, optimization_progress
    from app.services.finance.scheduler_stub import _ANALYSIS_LOCK

    run, _ = creation_job

    def fail():
        raise ValueError("invalid budget")

    monkeypatch.setattr(broker_budgets, "apply_live_broker_budgets", fail)
    run()
    state = optimization_progress.snapshot()
    assert state["status"] == "error"
    assert state["active"] is False
    assert "invalid budget" in state["message"]
    assert not _ANALYSIS_LOCK.locked()


def test_manual_creation_reports_missing_prices_as_error(creation_job, monkeypatch):
    from app.services.finance import yf_session
    from app.services.finance.buffett import optimization_progress

    run, _ = creation_job
    monkeypatch.setattr(yf_session, "download_prices_bulk_with_retry", lambda *_a, **_k: pd.DataFrame())
    run()
    assert optimization_progress.snapshot()["status"] == "error"
    assert optimization_progress.snapshot()["termination_reason"] == "prices_unavailable"
