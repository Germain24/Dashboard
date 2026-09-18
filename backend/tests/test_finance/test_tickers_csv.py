"""load_tickers/remove_stale_tickers : tickers.csv est un CSV headerless, séparé
par `;` -- certains libellés Bourse contiennent une virgule (ex. "Euronext
Amsterdam, Brussels"), ce qui casse un `pd.read_csv` sans séparateur explicite
(défaut `,`) dès la première ligne concernée -> ParserError -> liste vide
silencieuse (`load_tickers`) ou aucune suppression (`remove_stale_tickers`)."""

from __future__ import annotations

import pandas as pd
import pytest

from app.services.finance.buffett.runner import load_tickers, remove_stale_tickers
from app.services.finance.buffett.ticker_universe import TickerCatalogError


def _write(tmp_path, rows: list[str]):
    p = tmp_path / "tickers.csv"
    p.write_text("\r\n".join(rows) + "\r\n", encoding="utf-8")
    return str(p)


def test_load_tickers_survives_comma_in_exchange_field(tmp_path):
    path = _write(tmp_path, [
        "48TRA;TRATON;EuroTLX;Action",
        "AD.AS;AHOLD DEL;Euronext Amsterdam, Brussels;Action",   # virgule dans "Bourse"
        "WHA.AS;WERELDHAVE;Euronext Amsterdam;Action",
    ])
    tickers = load_tickers(path)
    assert tickers == ["48TRA", "AD.AS", "WHA.AS"]


def test_load_tickers_missing_file_is_explicit():
    with pytest.raises(TickerCatalogError, match="introuvable"):
        load_tickers("no/such/file.csv")


def test_load_tickers_dedupes(tmp_path):
    path = _write(tmp_path, [
        "AAA;Foo;NYSE;Action",
        "AAA;Foo;NYSE;Action",
        "BBB;Bar;NASDAQ;Action",
    ])
    assert load_tickers(path) == ["AAA", "BBB"]


def test_load_tickers_survives_invalid_utf8_in_name(tmp_path):
    path = tmp_path / "tickers.csv"
    path.write_bytes(b"AAA;Soci\xe3\xa9t\xe9;NYSE;Action\n")
    assert load_tickers(str(path)) == ["AAA"]


def test_remove_stale_tickers_never_mutates_catalog(tmp_path, monkeypatch):
    path = _write(tmp_path, [
        "48TRA;TRATON;EuroTLX;Action",
        "AD.AS;AHOLD DEL;Euronext Amsterdam, Brussels;Action",
        "WHA.AS;WERELDHAVE;Euronext Amsterdam;Action",
    ])
    from app.services.finance.buffett.config import Config
    monkeypatch.setattr(Config, "DATA_DIR", str(tmp_path))
    remove_stale_tickers(path, {"WHA.AS"})
    remaining = pd.read_csv(path, sep=";", header=None)[0].tolist()
    assert remaining == ["48TRA", "AD.AS", "WHA.AS"]
    assert (tmp_path / "finance_cache.db").exists()


def test_remove_stale_tickers_noop_when_empty_set(tmp_path):
    path = _write(tmp_path, ["AAA;Foo;NYSE;Action"])
    remove_stale_tickers(path, set())
    assert pd.read_csv(path, sep=";", header=None)[0].tolist() == ["AAA"]
