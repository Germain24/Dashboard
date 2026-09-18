from __future__ import annotations

from pathlib import Path

import pytest

from app.services.finance.catalog.apply import apply_catalog, assert_no_active_run
from app.services.finance.catalog.builder import (
    CatalogBuilder,
    CatalogEntry,
    CatalogError,
    build_yahoo_symbol,
)


@pytest.mark.parametrize(
    ("symbol", "mic", "expected"),
    [
        ("600000", "XSHG", "600000.SS"),
        ("600000.SS", "XSHG", "600000.SS"),
        ("1", "XSHE", "000001.SZ"),
        ("000001.SZ", "XSHE", "000001.SZ"),
        ("700", "XHKG", "0700.HK"),
        ("ASML", "XAMS", "ASML.AS"),
        ("ASML.AS", "XAMS", "ASML.AS"),
        ("BRK.B", "XNYS", "BRK-B"),
        ("RACE", "XMIL", "RACE.MI"),
        ("VOD.L", "XLON", "VOD.L"),
    ],
)
def test_yahoo_suffix_is_idempotent(symbol, mic, expected):
    assert build_yahoo_symbol(symbol, mic) == expected


@pytest.mark.parametrize(
    ("symbol", "mic"),
    [("ASML.AS.AS", "XAMS"), ("VOD.L.L", "XLON"), ("RACE.MI.MI", "XMIL")],
)
def test_repeated_terminal_suffix_is_rejected(symbol, mic):
    with pytest.raises(CatalogError, match="répété"):
        build_yahoo_symbol(symbol, mic)


def test_builder_deduplicates_market_symbol_but_keeps_cross_listings():
    builder = CatalogBuilder()
    builder.add_rows(
        [
            {"symbol": "ABC", "name": "Alpha", "isin": "US0000000001"},
            {"symbol": "ABC", "name": "Alpha duplicate", "isin": "US0000000001"},
        ],
        mic="XNYS", source="fixture", source_date="2026-01-01",
    )
    builder.add_rows(
        [{"symbol": "ABC", "name": "Alpha London", "isin": "US0000000001"}],
        mic="XLON", source="fixture", source_date="2026-01-01",
    )
    entries = builder.build()
    assert [(entry.mic, entry.yahoo_symbol) for entry in entries] == [
        ("XLON", "ABC.L"),
        ("XNYS", "ABC"),
    ]
    report = builder.report()
    assert report["cross_listed_isin"]["US0000000001"] == ["ABC.L", "ABC"]


def test_cross_listing_uses_declared_primary_market_for_fundamentals():
    builder = CatalogBuilder()
    builder.add_rows(
        [{"symbol": "FGR", "name": "Eiffage", "isin": "FR0000130452"}],
        mic="XPAR", source="Euronext",
    )
    builder.add_rows(
        [{
            "symbol": "EF3",
            "name": "Eiffage",
            "isin": "FR0000130452",
            "Primary Market MIC Code": "XPAR",
        }],
        mic="XETR", source="Deutsche Börse",
    )

    entries = {entry.yahoo_symbol: entry for entry in builder.build()}
    assert entries["FGR.PA"].fundamentals_symbol == "FGR.PA"
    assert entries["EF3.DE"].fundamentals_symbol == "FGR.PA"
    assert entries["EF3.DE"].primary_market is False


def test_deutsche_boerse_export_keeps_isin_and_primary_mic(tmp_path: Path):
    source = tmp_path / "xetra.csv"
    source.write_text(
        "Market:;Xetra\n"
        "Date:;2026-07-30\n"
        "Mnemonic;Instrument;ISIN;Primary Market MIC Code\n"
        "EF3;Eiffage;FR0000130452;XPAR\n",
        encoding="latin-1",
    )
    builder = CatalogBuilder()
    builder.add_file(source, mic="XETR", source="Deutsche Börse")
    entry = builder.build()[0]
    assert entry.yahoo_symbol == "EF3.DE"
    assert entry.isin == "FR0000130452"
    assert entry.primary_mic == "XPAR"
    assert entry.primary_market is False


def test_excluded_instruments_are_not_in_catalog():
    builder = CatalogBuilder()
    builder.add_rows(
        [
            {"symbol": "GOOD", "type": "Common stock"},
            {"symbol": "BAD", "type": "Warrant"},
            {"symbol": "FUND", "type": "Mutual fund"},
        ],
        mic="XNAS", source="fixture",
    )
    assert [entry.yahoo_symbol for entry in builder.build()] == ["GOOD"]


def test_euronext_adapter_resolves_market_to_mic(tmp_path: Path):
    import pandas as pd

    source = tmp_path / "euronext.xlsx"
    pd.DataFrame([
        {"Symbol": "AIR", "Name": "Airbus", "ISIN": "NL0000235190", "Market": "Euronext Paris"},
        {"Symbol": "AD", "Name": "Ahold", "ISIN": "NL0011794037", "Market": "Euronext Amsterdam"},
        {"Symbol": "IGNORED", "Name": "After hours", "Market": "Trading After Hours"},
    ]).to_excel(source, index=False)
    builder = CatalogBuilder()
    builder.add_file(source, mic="EURONEXT", source="Euronext")
    assert [(entry.mic, entry.yahoo_symbol) for entry in builder.build()] == [
        ("XAMS", "AD.AS"),
        ("XPAR", "AIR.PA"),
    ]


def test_apply_guard_refuses_an_active_run(tmp_path: Path):
    import sqlite3

    database = tmp_path / "app.db"
    with sqlite3.connect(database) as con:
        con.execute("create table buffett_run (id integer primary key, statut text)")
        con.execute("insert into buffett_run values (52, 'en_cours')")
    with pytest.raises(RuntimeError, match="#52"):
        assert_no_active_run(database)


def test_apply_catalog_enriches_broker_rows_without_changing_execution_ticker(
    tmp_path: Path,
):
    import pandas as pd

    broker = tmp_path / "ToutBroker.xlsx"
    pd.DataFrame([
        {
            "Ticker Yahoo Finance": "EF3.DE",
            "Nom": "Eiffage",
            "Trading212": True,
        },
    ]).to_excel(broker, index=False)
    entries = [
        CatalogEntry(
            mic="XETR",
            local_symbol="EF3",
            yahoo_symbol="EF3.DE",
            isin="FR0000130452",
            name="Eiffage",
            primary_market=False,
            primary_mic="XPAR",
            fundamentals_symbol="FGR.PA",
        ),
    ]

    apply_catalog(
        entries,
        catalog_path=tmp_path / "finance_catalog.csv",
        tickers_path=tmp_path / "tickers.csv",
        broker_path=broker,
        database=tmp_path / "missing.db",
    )
    row = pd.read_excel(broker).iloc[0]
    assert row["Ticker Yahoo Finance"] == "EF3.DE"
    assert row["Fundamentals Symbol"] == "FGR.PA"
    assert bool(row["Trading212"]) is True
    assert "Ticker" not in pd.read_excel(broker).columns
