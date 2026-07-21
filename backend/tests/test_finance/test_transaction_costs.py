import numpy as np
import pandas as pd
import pytest

from app.services.finance.buffett.config import Config
from app.services.finance.buffett.transaction_costs import (
    TransactionCostModel,
    ttf_tickers_from_dataframe,
)


def test_bourse_direct_pea_paris_tiers():
    model = TransactionCostModel(["ETF.PA"], [True])
    amounts = np.array([[100.0, 198.0, 500.0, 750.0, 1500.0, 3000.0, 5000.0]])
    assert model.trade_costs_eur("Bourse Direct", amounts) == pytest.approx(
        [0.50, 0.99, 0.99, 1.90, 2.90, 3.80, 4.50]
    )


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
