from __future__ import annotations

import pandas as pd

from app.services.finance.buffett.fundamentals_cache import FundamentalsCache


def test_fundamentals_are_shared_by_isin_and_fiscal_year(tmp_path):
    cache = FundamentalsCache(tmp_path / "finance.db")
    data = {
        "info": {"isin": "US0378331005", "longName": "Apple"},
        "income": pd.DataFrame(
            {"Revenue": [100.0, 120.0]},
            index=pd.to_datetime(["2024-09-30", "2025-09-30"]),
        ),
    }
    cache.save("AAPL", data)
    cache.save("APC.F", {"info": {"isin": "US0378331005", "longName": "Apple Frankfurt"}})
    loaded = cache.load("AAPL")
    assert loaded["info"]["longName"] == "Apple"
    assert list(loaded["income"]["Revenue"]) == [100.0, 120.0]
    assert list(cache.load("APC.F")["income"]["Revenue"]) == [100.0, 120.0]


def test_daily_metadata_can_exist_without_fundamentals(tmp_path):
    cache = FundamentalsCache(tmp_path / "finance.db")
    cache.save("CW8.PA", {"info": {"quoteType": "ETF"}})
    assert cache.load("CW8.PA")["info"]["quoteType"] == "ETF"


def test_explicit_isin_loads_primary_fundamentals_for_secondary_quote(tmp_path):
    cache = FundamentalsCache(tmp_path / "finance.db")
    income = pd.DataFrame(
        {"Revenue": [10.0, 12.0]},
        index=pd.to_datetime(["2024-12-31", "2025-12-31"]),
    )
    cache.save(
        "FGR.PA",
        {"info": {"longName": "Eiffage"}, "income": income},
        identity_key="FR0000130452",
    )

    loaded = cache.load(
        "EF3.DE",
        identity_key="FR0000130452",
        metadata_symbol="FGR.PA",
    )
    assert loaded["info"]["longName"] == "Eiffage"
    assert list(loaded["income"]["Revenue"]) == [10.0, 12.0]
