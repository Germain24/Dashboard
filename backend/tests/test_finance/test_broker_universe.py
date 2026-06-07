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
