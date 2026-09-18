"""Filtre Buffett : exclure les titres dont TOUS les brokers sont Faux (vide ≠ Faux)."""

from __future__ import annotations

import pandas as pd

from app.services.finance.buffett import broker_availability as ba


def _patch_table(monkeypatch, df):
    monkeypatch.setattr(ba, "load_broker_table", lambda: df)


def test_excludes_only_all_false_rows(monkeypatch):
    # Colonnes nommées comme les clés Config.BUDGET_BROKERS (match exact).
    df = pd.DataFrame([
        {"Ticker Yahoo Finance": "ALLFALSE", "Trading212": False, "BoursDirect": False, "BoursDirect2": False},
        {"Ticker Yahoo Finance": "ONETRUE", "Trading212": True, "BoursDirect": False, "BoursDirect2": False},
        {"Ticker Yahoo Finance": "ONEEMPTY", "Trading212": None, "BoursDirect": False, "BoursDirect2": False},
        {"Ticker Yahoo Finance": "ALLEMPTY", "Trading212": None, "BoursDirect": None, "BoursDirect2": None},
    ])
    _patch_table(monkeypatch, df)
    excluded = ba.broker_excluded_tickers()
    assert excluded == {"ALLFALSE"}  # vide ne compte pas comme Faux


def test_handles_numeric_and_string_flags(monkeypatch):
    df = pd.DataFrame([
        {"Ticker Yahoo Finance": "NUM", "Trading212": 0, "BoursDirect": 0, "BoursDirect2": 0},
        {"Ticker Yahoo Finance": "STR", "Trading212": "Faux", "BoursDirect": "faux", "BoursDirect2": "0"},
        {"Ticker Yahoo Finance": "KEEP", "Trading212": 1, "BoursDirect": 0, "BoursDirect2": 0},
    ])
    _patch_table(monkeypatch, df)
    assert ba.broker_excluded_tickers() == {"NUM", "STR"}


def test_no_file_returns_empty(monkeypatch):
    monkeypatch.setattr(ba, "load_broker_table", lambda: None)
    assert ba.broker_excluded_tickers() == set()


def test_cell_state_parsing():
    assert ba._cell_state(True) is True
    assert ba._cell_state(1) is True
    assert ba._cell_state("Vrai") is True
    assert ba._cell_state(False) is False
    assert ba._cell_state(0) is False
    assert ba._cell_state("faux") is False
    assert ba._cell_state(None) is None
    assert ba._cell_state("") is None
    assert ba._cell_state(float("nan")) is None


def test_investable_universe_uses_only_explicit_true_on_funded_brokers():
    df = pd.DataFrame([
        {"Ticker Yahoo Finance": "T212", "Trading212": True, "BoursDirect2": False},
        {"Ticker Yahoo Finance": "BD", "Trading212": False, "BoursDirect2": True},
        {"Ticker Yahoo Finance": "UNKNOWN", "Trading212": None, "BoursDirect2": None},
        {"Ticker Yahoo Finance": "NO", "Trading212": False, "BoursDirect2": False},
    ])

    assert ba.broker_investable_tickers(["Trading212"], df=df) == {"T212"}
    assert ba.broker_investable_tickers(["BoursDirect2"], df=df) == {"BD"}
    assert ba.broker_investable_tickers(
        ["Trading212", "BoursDirect2"], df=df
    ) == {"T212", "BD"}


def test_investable_universe_is_empty_without_matching_funded_broker_column():
    df = pd.DataFrame([
        {"Ticker Yahoo Finance": "A", "Trading212": True},
    ])

    assert ba.broker_investable_tickers(["UnknownBroker"], df=df) == set()


def test_normalized_broker_table_is_cached_and_returned_as_copy(monkeypatch):
    import app.services.finance.catalog.repository as repository

    calls = 0

    def load_catalog():
        nonlocal calls
        calls += 1
        return pd.DataFrame([{"Ticker Yahoo Finance": "CACHE"}])

    monkeypatch.setattr(repository, "catalog_dataframe", load_catalog)
    ba.reset_etf_cache()
    first = ba.load_broker_table()
    first.loc[0, "Ticker Yahoo Finance"] = "MUTATED"
    second = ba.load_broker_table()

    assert calls == 1
    assert second.loc[0, "Ticker Yahoo Finance"] == "CACHE"

    ba.reset_etf_cache()
    ba.load_broker_table()
    assert calls == 2


def test_split_action_and_etf_workbooks_are_combined_on_legacy_fallback(
    tmp_path, monkeypatch,
):
    import app.services.finance.catalog.repository as repository

    actions = tmp_path / "ToutBroker_Actions.xlsx"
    etfs = tmp_path / "ToutBroker_ETF.xlsx"
    pd.DataFrame([
        {"Ticker Yahoo Finance": "AAPL", "Secteur 1": "Action"},
    ]).to_excel(actions, index=False)
    pd.DataFrame([
        {"Ticker Yahoo Finance": "CW8.PA", "Secteur 1": "ETF"},
    ]).to_excel(etfs, index=False)
    monkeypatch.setattr(repository, "catalog_dataframe", lambda: None)
    monkeypatch.setattr(ba.Config, "BROKER_ACTIONS_FILE", str(actions))
    monkeypatch.setattr(ba.Config, "BROKER_ETF_FILE", str(etfs))
    ba.reset_etf_cache()

    table = ba.load_broker_table()

    assert set(table["Ticker Yahoo Finance"]) == {"AAPL", "CW8.PA"}
    assert ba.find_broker_file() == str(etfs)


def test_primary_asset_unions_broker_quotes_and_routes_primary_then_liquidity(
    monkeypatch,
):
    table = pd.DataFrame([
        {
            "Ticker Yahoo Finance": "FGR.PA",
            "Fundamentals Symbol": "FGR.PA",
            "Primary Market": True,
            "Volume": 1000,
            "Trading212": False,
            "BoursDirect2": True,
        },
        {
            "Ticker Yahoo Finance": "EF3.DE",
            "Fundamentals Symbol": "FGR.PA",
            "Primary Market": False,
            "Volume": 5000,
            "Trading212": True,
            "BoursDirect2": True,
        },
    ])
    _patch_table(monkeypatch, table)
    monkeypatch.setattr(
        ba.Config,
        "BUDGET_BROKERS",
        {"Trading212": 1000.0, "BoursDirect2": 1000.0},
    )
    merged = ba.merge_broker_columns(pd.DataFrame([
        {"Ticker Yahoo Finance": "FGR.PA"},
    ]))
    row = merged.iloc[0]
    assert bool(row["Trading212"]) is True
    assert bool(row["BoursDirect2"]) is True
    assert row["Execution Routes"] == {
        "Trading212": "EF3.DE",
        "BoursDirect2": "FGR.PA",
    }
