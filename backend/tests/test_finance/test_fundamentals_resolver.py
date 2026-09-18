from __future__ import annotations

import pandas as pd

from app.services.finance.buffett.fundamentals_resolver import (
    build_fundamentals_links,
    build_instrument_groups,
)


def test_explicit_fundamentals_symbol_keeps_quote_symbol_for_execution():
    table = pd.DataFrame([
        {
            "Ticker Yahoo Finance": "FGR.PA",
            "ISIN": "FR0000130452",
            "Primary Market": True,
            "Fundamentals Symbol": "FGR.PA",
        },
        {
            "Ticker Yahoo Finance": "EF3.DE",
            "ISIN": "FR0000130452",
            "Primary Market": False,
            "Fundamentals Symbol": "FGR.PA",
        },
    ])

    link = build_fundamentals_links(table)["EF3.DE"]
    assert link.quote_symbol == "EF3.DE"
    assert link.fundamentals_symbol == "FGR.PA"
    assert link.identity_key == "FR0000130452"


def test_legacy_table_uses_unique_primary_row_in_isin_group():
    table = pd.DataFrame([
        {
            "Ticker Yahoo Finance": "FGR.PA",
            "ISIN": "FR0000130452",
            "Primary Market": True,
        },
        {
            "Ticker Yahoo Finance": "EF3.DE",
            "ISIN": "FR0000130452",
            "Primary Market": False,
        },
    ])
    assert (
        build_fundamentals_links(table)["EF3.DE"].fundamentals_symbol
        == "FGR.PA"
    )


def test_instrument_groups_schedule_only_primary_and_keep_broker_quotes():
    links = build_fundamentals_links(pd.DataFrame([
        {
            "Ticker Yahoo Finance": "FGR.PA",
            "ISIN": "FR0000130452",
            "Primary Market": True,
            "Fundamentals Symbol": "FGR.PA",
        },
        {
            "Ticker Yahoo Finance": "EF3.DE",
            "ISIN": "FR0000130452",
            "Primary Market": False,
            "Fundamentals Symbol": "FGR.PA",
        },
    ]))
    groups = build_instrument_groups(["EF3.DE", "FGR.PA", "AAPL"], links)
    assert [group.primary_symbol for group in groups] == ["FGR.PA", "AAPL"]
    assert groups[0].identity_key == "FR0000130452"
    assert groups[0].quote_symbols == ("EF3.DE", "FGR.PA")
