import numpy as np
import pandas as pd
import pytest

from app.services.finance.buffett.config import Config
from app.services.finance.buffett.etf_selection import (
    _spearman_correlation,
    select_etfs_per_broker,
    select_index_representatives_before_history,
)


def test_missing_broker_column_never_grants_access(monkeypatch):
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"Known": 1000, "Missing": 1000})
    frame = pd.DataFrame({
        "Ticker Yahoo Finance": ["FUND", "STOCK"],
        "Secteur": ["ETF", "Technology"],
        "Known": [True, True],
    })
    returns = pd.DataFrame({"FUND": np.arange(80), "STOCK": np.arange(80)})
    _, selected, diagnostics = select_etfs_per_broker(
        returns, frame, maximum=1, returns_are_base_currency=True
    )
    assert diagnostics["brokers"]["Missing"]["selected_tickers"] == []
    assert not selected["Missing"].any()
    assert diagnostics["brokers"]["Known"]["selected_tickers"] == ["FUND"]


def test_index_selection_preserves_unknown_access_and_excel_numeric_columns(monkeypatch):
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"Known": 1000, "Missing": 1000})
    frame = pd.DataFrame({
        "Ticker Yahoo Finance": ["FUND", "STOCK"],
        "Secteur": ["ETF", "Technology"],
        "Known": [1.0, np.nan],
    })
    _, selected, diagnostics = select_index_representatives_before_history(
        frame, {"FUND": {"index_name": "MSCI World"}}, etf_tickers={"FUND"}
    )
    assert diagnostics["brokers"]["Missing"]["selected_tickers"] == []
    assert not selected["Missing"].any()
    assert selected.loc[selected["Ticker Yahoo Finance"] == "FUND", "Known"].iloc[0]
    assert pd.isna(selected.loc[selected["Ticker Yahoo Finance"] == "STOCK", "Known"].iloc[0])


def test_incomplete_correlated_series_does_not_look_independent(monkeypatch):
    monkeypatch.setattr(Config, "STARR_CORRELATION_SHRINKAGE", 0.0)
    values = np.random.default_rng(21).normal(size=100)
    returns = pd.DataFrame({"A": values, "B": values * 2, "C": -values})
    returns.loc[3, "B"] = np.nan
    corr = _spearman_correlation(returns, list(returns.columns))
    assert corr[0, 1] > 0.99
    assert corr[1, 2] < -0.99


def test_unknown_correlations_keep_conservative_fallback():
    values = np.random.default_rng(22).normal(size=100)
    returns = pd.DataFrame({"A": values, "B": -values, "FLAT": 0.0, "EMPTY": np.nan})
    corr = _spearman_correlation(returns, list(returns.columns))
    assert corr[0, 2] == pytest.approx(0.75)
    assert corr[0, 3] == pytest.approx(0.75)
    assert corr[2, 3] == pytest.approx(0.75)
    assert np.all(np.diag(corr) == 1.0)


def test_single_fund_correlation_has_consistent_shape():
    assert np.array_equal(_spearman_correlation(pd.DataFrame({"FUND": [0.0]}), ["FUND"]), [[1.0]])
