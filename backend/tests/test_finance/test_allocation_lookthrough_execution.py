"""L'arrondi conserve le budget achetable et tous les plafonds transparisés."""

import numpy as np
import pytest

from app.services.finance.buffett.allocation import (
    discretize_allocation,
    enforce_discrete_sector_cap,
)
from app.services.finance.buffett.config import Config


@pytest.mark.parametrize("missing_price", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_quote_does_not_poison_broker_budget(monkeypatch, missing_price):
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"BoursDirect2": 1000.0})
    allocation = discretize_allocation(
        ["MISSING", "VALID"], np.array([[0.5], [0.5]]), ["BoursDirect2"],
        {"MISSING": missing_price, "VALID": 100.0}, total_cap=1000.0,
    )

    assert len(allocation) == 1
    assert allocation[0]["Ticker"] == "VALID"
    assert allocation[0]["eur"] == 1000.0


@pytest.mark.parametrize("broker", ["BoursDirect2", "Trading212"])
def test_cash_released_by_sector_cap_is_reinvested_with_lookthrough(monkeypatch, broker):
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {broker: 1000.0})
    monkeypatch.setattr(Config, "MAX_SECTOR_PCT", 0.50)
    monkeypatch.setattr(Config, "MAX_SECTOR_PCT_OVERRIDES", {})
    monkeypatch.setattr(
        "app.services.finance.buffett.sector_constraints.load_classification",
        lambda: ({}, {}),
    )
    fractions = {"TECH": {"Tech": 1.0}, "OTHER": {"Health": 0.60, "Industry": 0.40}}
    allocation = discretize_allocation(
        ["TECH", "OTHER"],
        np.array([[0.60], [0.40]]),
        [broker],
        {"TECH": 10.0, "OTHER": 10.0},
        total_cap=1000.0,
        sector_exposures_by_ticker=fractions,
        is_etf_tickers={"TECH", "OTHER"},
    )

    values = {item["AnalysisTicker"]: item["eur"] for item in allocation}
    assert values == {"TECH": 500.0, "OTHER": 500.0}
    assert sum(values.values()) == 1000.0
    assert values["OTHER"] * 0.60 <= 500.0
    assert values["OTHER"] * 0.40 <= 500.0


def test_lookthrough_refill_checks_every_sector_and_keeps_infeasible_cash(monkeypatch):
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"Trading212": 1000.0})
    monkeypatch.setattr(Config, "MAX_SECTOR_PCT", 0.50)
    monkeypatch.setattr(Config, "MAX_SECTOR_PCT_OVERRIDES", {})
    monkeypatch.setattr(
        "app.services.finance.buffett.sector_constraints.load_classification",
        lambda: ({}, {}),
    )
    allocation = discretize_allocation(
        ["TECH", "MIXED"], np.array([[0.60], [0.40]]), ["Trading212"], {},
        total_cap=1000.0,
        sector_exposures_by_ticker={"TECH": {"Tech": 1.0}, "MIXED": {"Tech": 0.5, "Health": 0.5}},
        is_etf_tickers={"TECH", "MIXED"},
    )

    values = {item["AnalysisTicker"]: item["eur"] for item in allocation}
    assert values["TECH"] + 0.5 * values["MIXED"] <= 500.0
    assert sum(values.values()) < 1000.0


def test_sector_rounding_uses_small_share_when_large_etf_would_overshoot(monkeypatch):
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"BoursDirect2": 1000.0})
    monkeypatch.setattr(
        "app.services.finance.buffett.sector_constraints.load_classification",
        lambda: ({}, {}),
    )
    allocation = [
        {"Ticker": "BIG", "Broker": "BoursDirect2", "type": "shares", "shares": 1, "prix": 300.0, "eur": 300.0},
        {"Ticker": "SMALL", "Broker": "BoursDirect2", "type": "shares", "shares": 41, "prix": 5.0, "eur": 205.0},
    ]
    result = enforce_discrete_sector_cap(
        allocation,
        total_cap=1000.0,
        max_sector_pct=0.50,
        is_etf_tickers={"BIG", "SMALL"},
        sector_exposures_by_ticker={"BIG": {"Tech": 1.0}, "SMALL": {"Tech": 1.0}},
        broker_spend_caps={"BoursDirect2": 505.0},
    )

    shares = {item["Ticker"]: item["shares"] for item in result}
    assert shares == {"BIG": 1, "SMALL": 40}
    assert sum(item["eur"] for item in result) == 500.0
