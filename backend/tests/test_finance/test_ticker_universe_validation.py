from __future__ import annotations

from pathlib import Path

import pytest

from app.services.finance.buffett.ticker_universe import (
    TickerCatalogError,
    read_ticker_catalog,
)
from app.services.finance.catalog.repair import repair_legacy_tickers


def test_canonical_preflight_rejects_encoding_duplicates_and_suffixes(tmp_path: Path):
    source = tmp_path / "tickers.csv"
    source.write_bytes(
        b"AAA.DE.DE;Bad\xe3\x98Name;Xetra;Action\n"
        b"AAA.DE.DE;Duplicate;Xetra;Action\n"
    )
    with pytest.raises(TickerCatalogError) as caught:
        read_ticker_catalog(source, require_canonical=True)
    diagnostics = caught.value.diagnostics
    assert diagnostics.encoding_errors > 0
    assert diagnostics.duplicate_symbols == ["AAA.DE.DE"]
    assert diagnostics.repeated_suffixes == ["AAA.DE.DE"]


def test_invalid_ticker_bytes_are_never_tolerated(tmp_path: Path):
    source = tmp_path / "tickers.csv"
    source.write_bytes(b"A\xe3\x98A;Name;NYSE;Action\n")
    with pytest.raises(TickerCatalogError, match="corrompu"):
        read_ticker_catalog(source)


def test_repair_is_utf8_deduplicated_and_suffix_idempotent(tmp_path: Path):
    source = tmp_path / "tickers.csv"
    source.write_bytes(
        b"AAA.DE.DE;Bad\xe3\x98Name;Xetra;Action\n"
        b"AAA.DE;Longer valid name;Xetra;Action\n"
        b"BBB;Beta;NYSE;Action\n"
    )
    payload, report = repair_legacy_tickers(source)
    repaired = tmp_path / "repaired.csv"
    repaired.write_bytes(payload)
    catalog = read_ticker_catalog(repaired, require_canonical=True)
    assert list(catalog.tickers) == ["AAA.DE", "BBB"]
    assert report["rows_after"] == 2
    assert report["suffix_fixes"] == [{"from": "AAA.DE.DE", "to": "AAA.DE"}]
