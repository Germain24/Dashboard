import numpy as np
import pandas as pd
import pytest

from app.services.finance.buffett.config import Config
from app.services.finance.buffett.transaction_costs import (
    TransactionCostModel,
    estimate_rebalance_costs_by_broker,
    next_rebalance_costs_by_broker,
    ttf_tickers_from_dataframe,
)


def test_bourse_direct_pea_paris_tiers():
    model = TransactionCostModel(["ETF.PA"], [True])
    amounts = np.array([[100.0, 198.0, 500.0, 750.0, 1500.0, 3000.0, 5000.0]])
    assert model.trade_costs_eur("Bourse Direct", amounts) == pytest.approx(
        [0.50, 0.99, 0.99, 1.90, 2.90, 3.80, 4.50]
    )


def test_bourse_direct_uses_the_exchange_specific_pea_schedule():
    model = TransactionCostModel(
        ["PARIS.PA", "FRANKFURT.DE", "LONDON.L", "MADRID.MC"],
        [False] * 4,
    )
    costs = model.trade_costs_eur(
        "Bourse Direct",
        np.array([[100.0], [1_000.0], [1_000.0], [1_000.0]]),
    )
    # Paris: 0,5% jusqu'à 198 €. Francfort est plafonné PEA à 0,5% ;
    # Londres reste hors UE/EEE depuis le Brexit (15 € minimum + change + stamp),
    # tandis que Madrid est plafonné à 0,5%.
    assert costs[0] == pytest.approx(0.50 + 5.00 + 15.00 + 0.80 + 5.00 + 5.00)


def test_bourse_direct_foreign_market_and_fx_fees(monkeypatch):
    monkeypatch.setattr(Config, "BOURSE_DIRECT_FX_FEE_RATE", 0.0008)
    model = TransactionCostModel(["US_STOCK", "ETF.DE"], [False, True])
    costs = model.trade_costs_eur(
        "BoursDirect2", np.array([[5000.0], [1000.0]])
    )
    # US : 8,50 € + 0,08 % FX. Xetra/PEA : minimum 15 € plafonné à 0,5 %.
    assert costs[0] == pytest.approx(8.50 + 4.00 + 5.00)


def test_trading212_fx_stamp_and_ttf(monkeypatch):
    monkeypatch.setattr(Config, "TRADING212_FX_FEE_RATE", 0.0015)
    monkeypatch.setattr(Config, "FRENCH_TRANSACTION_TAX_RATE", 0.004)
    model = TransactionCostModel(
        ["US_STOCK", "UK_STOCK.L", "UK_ETF.L", "FR_STOCK.PA"],
        [False, False, True, False],
        {"FR_STOCK.PA"},
    )
    costs = model.trade_costs_eur("Trading212", np.full((4, 1), 1000.0))
    # USD FX, action UK FX+timbre, ETF UK FX seul, action FR TTF seule.
    assert costs[0] == pytest.approx(1.5 + 6.5 + 1.5 + 4.0)


def test_uk_ptm_uses_gbp_threshold_and_rate():
    model = TransactionCostModel(
        ["UK_STOCK.L"], [False], gbp_eur_rate=1.2
    )
    # 12 001 € dépasse £10 000 à 1,20 EUR/GBP : FX + stamp + £1,50 de PTM.
    cost = model.trade_costs_eur("Trading212", [12_001.0])[0]
    assert cost == pytest.approx(12_001.0 * (0.0015 + 0.005) + 1.5 * 1.2)


def test_bourse_direct_foreign_custody_is_annual_fraction(monkeypatch):
    monkeypatch.setattr(Config, "BOURSE_DIRECT_FOREIGN_CUSTODY_RATE", 0.00036)
    model = TransactionCostModel(["LOCAL.PA", "US_STOCK"], [True, False])
    assert model.annual_holding_cost("Bourse Direct", [0.4, 0.6])[0] == pytest.approx(
        0.00036 * 0.6
    )


def test_ttf_column_requires_explicit_truth(monkeypatch):
    monkeypatch.setattr(Config, "FRENCH_TTF_TICKERS", [])
    df = pd.DataFrame({
        "Ticker Yahoo Finance": ["YES.PA", "EMPTY.PA", "NO.PA"],
        "TTF": [True, np.nan, "non"],
    })
    assert ttf_tickers_from_dataframe(df) == {"YES.PA"}


def test_next_rebalance_costs_are_reserved_per_broker_only():
    diagnostics = {
        "transaction_costs": {
            "brokers": [
                {"broker": "BoursDirect2", "trade_cost_eur": 41.9, "annual_custody_eur": 8.0},
                {"broker": "Trading212", "trade_cost_eur": 1.5, "annual_custody_eur": 0.0},
            ]
        }
    }

    assert next_rebalance_costs_by_broker(diagnostics) == {
        "BoursDirect2": 41.9,
        "Trading212": 1.5,
    }


def test_estimated_reserve_uses_target_and_execution_route(monkeypatch):
    monkeypatch.setattr(Config, "TRANSACTION_COSTS_ENABLED", True)
    reserve = estimate_rebalance_costs_by_broker(
        ["MAIN"],
        np.array([[1.0]]),
        ["Bourse Direct"],
        1_000.0,
        is_etf_tickers=set(),
        execution_routes={("MAIN", "Bourse Direct"): "LONDON.L"},
    )

    # 15 € minimum Londres + 0,5 % de timbre + 0,08 % de change.
    assert reserve["Bourse Direct"] == pytest.approx(20.8)


def test_estimated_reserve_is_zero_when_costs_are_disabled(monkeypatch):
    monkeypatch.setattr(Config, "TRANSACTION_COSTS_ENABLED", False)
    assert estimate_rebalance_costs_by_broker(
        ["A"], np.array([[1.0]]), ["Bourse Direct"], 1_000.0
    ) == {"Bourse Direct": 0.0}
