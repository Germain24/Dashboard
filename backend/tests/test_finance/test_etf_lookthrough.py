"""Récup justETF incrémentale : sélection des ETF non-faits + fusion non destructive."""

import pandas as pd

from app.services.finance.buffett.etf_lookthrough import (
    _done_pays_tickers,
    _etf_dates,
    merge_pays,
)


def test_done_tickers_only_those_with_country_data():
    pays = pd.DataFrame([
        {"Ticker": "A.L", "Nom": "A", "France": 50.0, "Italy": 50.0},
        {"Ticker": "B.L", "Nom": "B", "France": 0.0, "Italy": 0.0},  # ligne vide -> à refaire
    ])
    assert _done_pays_tickers(pays) == {"A.L"}


def test_done_tickers_empty_when_no_sheet():
    assert _done_pays_tickers(None) == set()
    assert _done_pays_tickers(pd.DataFrame()) == set()


def test_merge_pays_preserves_existing_and_adds_new():
    existing = pd.DataFrame([{"Ticker": "A.L", "Nom": "A", "France": 60.0, "Spain": 40.0}])
    results = [{"Ticker": "B.L", "Nom": "B", "pays": {"Japan": 100.0}}]
    out = merge_pays(existing, results)
    tickers = set(out["Ticker"])
    assert tickers == {"A.L", "B.L"}
    # union des colonnes pays, fillna 0
    a = out[out["Ticker"] == "A.L"].iloc[0]
    b = out[out["Ticker"] == "B.L"].iloc[0]
    assert a["France"] == 60.0 and a["Japan"] == 0
    assert b["Japan"] == 100.0 and b["France"] == 0


def test_merge_pays_upserts_same_ticker():
    existing = pd.DataFrame([{"Ticker": "A.L", "Nom": "A", "France": 60.0}])
    results = [{"Ticker": "A.L", "Nom": "A", "pays": {"Germany": 100.0}}]
    out = merge_pays(existing, results, today="2026-06-23")
    assert len(out) == 1
    row = out.iloc[0]
    assert row["Germany"] == 100.0          # compo remplacée
    assert "France" not in out.columns       # plus aucune ligne n'a France
    assert row["Date_analyse"] == "2026-06-23"


def test_merge_pays_stamps_date_only_on_fetched():
    existing = pd.DataFrame([
        {"Ticker": "A.L", "Nom": "A", "Date_analyse": "2026-01-01", "France": 100.0},
    ])
    results = [{"Ticker": "B.L", "Nom": "B", "pays": {"Japan": 100.0}}]
    out = merge_pays(existing, results, today="2026-06-23")
    a = out[out["Ticker"] == "A.L"].iloc[0]
    b = out[out["Ticker"] == "B.L"].iloc[0]
    assert a["Date_analyse"] == "2026-01-01"   # inchangé (pas refetché)
    assert b["Date_analyse"] == "2026-06-23"   # estampillé aujourd'hui


def test_etf_dates_reads_column():
    pays = pd.DataFrame([
        {"Ticker": "A.L", "Nom": "A", "Date_analyse": "2026-01-01", "France": 100.0},
        {"Ticker": "B.L", "Nom": "B", "Date_analyse": None, "France": 50.0},
    ])
    assert _etf_dates(pays) == {"A.L": "2026-01-01"}
    assert _etf_dates(pd.DataFrame([{"Ticker": "A.L", "France": 100.0}])) == {}


