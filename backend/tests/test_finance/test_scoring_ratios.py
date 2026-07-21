"""Régressions sur l'extraction des ratios financiers du score MOAT."""

from __future__ import annotations

import pandas as pd
import pytest

from app.services.finance.buffett.scoring import analyze_financials


def test_latest_ratios_debt_roic_and_capex_are_financially_consistent():
    old, recent = pd.to_datetime(["2024-12-31", "2025-12-31"])
    index = [old, recent]
    income = pd.DataFrame(
        {
            "Total Revenue": [100.0, 100.0],
            "Gross Profit": [40.0, 80.0],
            "Selling General And Administration": [20.0, 20.0],
            "Research And Development": [5.0, 5.0],
            "Reconciled Depreciation": [4.0, 4.0],
            "Interest Expense": [2.0, 2.0],
            "Operating Income": [10.0, 20.0],
            "Pretax Income": [8.0, 18.0],
            "Tax Provision": [2.0, 4.0],
            "Net Income": [5.0, 12.0],
        },
        index=index,
    )
    balance = pd.DataFrame(
        {
            "Ordinary Shares Number": [10.0, 10.0],
            "Total Debt": [20.0, 30.0],
            "Long Term Debt And Capital Lease Obligation": [5.0, 3.0],
            "Total Assets": [100.0, 100.0],
            "Current Assets": [50.0, 50.0],
            "Current Liabilities": [25.0, 25.0],
            "Stockholders Equity": [50.0, 50.0],
            "Invested Capital": [70.0, 70.0],
            "Retained Earnings": [10.0, 12.0],
            "Cash Cash Equivalents And Short Term Investments": [5.0, 6.0],
        },
        index=index,
    )
    cashflow = pd.DataFrame(
        {
            # Yahoo représente bien l'achat d'immobilisations comme une sortie négative.
            "Capital Expenditure": [-20.0, -3.0],
            "Issuance Of Capital Stock": [0.0, 0.0],
            "Repurchase Of Capital Stock": [-1.0, -1.0],
        },
        index=index,
    )
    data = {
        "income": income.iloc[::-1],
        "balance": balance.iloc[::-1],
        "cashflow": cashflow.iloc[::-1],
        "info": {
            "sector": "Technology",
            "industry": "Software - Infrastructure",
            "country": "United States",
            "currentPrice": 10.0,
            "trailingEps": 1.0,
            "trailingPE": 10.0,
        },
    }

    _, metrics = analyze_financials("TEST", data, etf_tickers=set())
    ratios = metrics["ratios_recents"]

    assert ratios["gpm"] == pytest.approx(0.80)
    assert ratios["debt_ratio"] == pytest.approx(0.30)
    assert ratios["lt_debt_ratio"] == pytest.approx(3.0 / 18.0)
    assert ratios["debt_eq"] == pytest.approx(0.60)
    assert ratios["capex"] == pytest.approx(3.0 / 12.0)
    # NOPAT / capital investi = 20 × (1 - 4/18) / 70.
    assert ratios["roic"] == pytest.approx(20.0 * (1.0 - 4.0 / 18.0) / 70.0)
    assert 0 < metrics["score_coverage_pct"] <= 100
