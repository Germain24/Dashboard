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
            "Operating Cash Flow": [30.0, 20.0],
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
    assert ratios["fcf_to_net_income"] == pytest.approx(17.0 / 12.0)
    assert ratios["fcf_margin"] == pytest.approx(0.17)
    assert ratios["share_count_growth"] == pytest.approx(0.0)
    # NOPAT / capital investi = 20 × (1 - 4/18) / 70.
    assert ratios["roic"] == pytest.approx(20.0 * (1.0 - 4.0 / 18.0) / 70.0)
    assert 0 < metrics["score_coverage_pct"] <= 100
    assert metrics["buffett_rules_score"] > 0
    assert metrics["score_v2"]["model_version"] == 3
    assert metrics["ranking_score"] <= metrics["buffett_quality_score"]


def test_negative_accounting_denominators_are_invalid_not_reversed():
    dates = pd.to_datetime(["2024-12-31", "2025-12-31"])
    income = pd.DataFrame({
        "Total Revenue": [100.0, 100.0], "Gross Profit": [20.0, -50.0],
        "Selling General And Administration": [5.0, 5.0],
        "Interest Expense": [1.0, 2.0], "Operating Income": [10.0, -5.0],
        "Pretax Income": [8.0, -10.0], "Tax Provision": [2.0, 0.0],
        "Net Income": [5.0, 100.0],
    }, index=dates)
    balance = pd.DataFrame({
        "Ordinary Shares Number": [10.0, 10.0], "Total Debt": [20.0, 20.0],
        "Long Term Debt": [10.0, 10.0], "Total Assets": [100.0, 100.0],
        "Current Assets": [30.0, 30.0], "Current Liabilities": [20.0, 20.0],
        "Stockholders Equity": [50.0, -200.0],
        "Invested Capital": [70.0, -100.0],
    }, index=dates)
    cashflow = pd.DataFrame({
        "Operating Cash Flow": [8.0, 8.0], "Capital Expenditure": [-2.0, -2.0],
    }, index=dates)

    _, metrics = analyze_financials(
        "NEG", {"income": income, "balance": balance, "cashflow": cashflow, "info": {}},
        etf_tickers=set(),
    )
    recent = metrics["ratios_recents"]
    assert recent["gpm"] == pytest.approx(-0.5)
    assert recent["roe"] is None
    assert recent["roic"] is None
    assert recent["lt_debt_ratio"] is None
    assert recent["interest_exp"] is None
    assert recent["metric_states"]["roe"] == "ECONOMICALLY_INVALID"
    assert recent["metric_states"]["roic"] == "ECONOMICALLY_INVALID"
    assert recent["metric_states"]["lt_debt_ratio"] == "ECONOMICALLY_INVALID"


def test_union_of_financial_years_keeps_income_year_without_cashflow():
    dates = pd.to_datetime(["2023-12-31", "2024-12-31", "2025-12-31"])
    income = pd.DataFrame({
        "Total Revenue": [80.0, 90.0, 100.0], "Gross Profit": [30.0, 36.0, 45.0],
        "Operating Income": [8.0, 9.0, 11.0], "Pretax Income": [7.0, 8.0, 10.0],
        "Tax Provision": [1.0, 1.0, 2.0], "Net Income": [5.0, 6.0, 8.0],
    }, index=dates)
    balance = pd.DataFrame({
        "Ordinary Shares Number": [10.0, 10.0, 10.0],
        "Total Assets": [80.0, 90.0, 100.0],
        "Stockholders Equity": [40.0, 45.0, 50.0],
        "Invested Capital": [50.0, 55.0, 60.0],
    }, index=dates)
    cashflow = pd.DataFrame({
        "Operating Cash Flow": [9.0, 12.0], "Capital Expenditure": [-2.0, -3.0],
    }, index=dates[1:])

    _, metrics = analyze_financials(
        "UNION", {"income": income, "balance": balance, "cashflow": cashflow, "info": {}},
        etf_tickers=set(),
    )
    assert metrics["score_v2"]["history_years"] == 3
    assert metrics["score_v2"]["family_scores"]["margins_pricing"]["coverage_pct"] > 0
