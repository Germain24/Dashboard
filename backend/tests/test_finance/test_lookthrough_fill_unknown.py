"""Un pays absent reste explicite et ne devient jamais une diversification fictive."""

import pandas as pd

from app.services.finance.buffett.lookthrough import fill_unknown_countries, load_lookthrough


def test_unknown_ticker_gets_explicit_unknown_bucket():
    pays = {
        "A": {"France": 0.6, "Germany": 0.4},
        "B": {"France": 0.2, "United States": 0.8},
    }
    out = fill_unknown_countries(pays, ["A", "B", "GOLD"])
    assert out["GOLD"] == {"Inconnu": 1.0}
    assert sum(out["GOLD"].values()) == 1.0


def test_known_tickers_unchanged():
    pays = {"A": {"France": 1.0}}
    out = fill_unknown_countries(pays, ["A", "GOLD"])
    assert out["A"] == {"France": 1.0}


def test_all_unknown_use_same_conservative_bucket():
    out = fill_unknown_countries({}, ["GOLD", "SILVER"])
    assert out == {
        "GOLD": {"Inconnu": 1.0},
        "SILVER": {"Inconnu": 1.0},
    }


def test_no_unknown_tickers_returns_unchanged():
    pays = {"A": {"France": 1.0}, "B": {"Germany": 1.0}}
    out = fill_unknown_countries(pays, ["A", "B"])
    assert out == {"A": {"France": 1.0}, "B": {"Germany": 1.0}}


def test_ticker_case_insensitive():
    pays = {"A.PA": {"France": 1.0}}
    out = fill_unknown_countries(pays, ["a.pa", "gold.l"])
    assert out["A.PA"] == {"France": 1.0}
    assert out["GOLD.L"] == {"Inconnu": 1.0}


def test_legacy_etf_country_and_defensive_sheets_are_ignored(tmp_path):
    path = tmp_path / "ToutBroker.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame([
            {
                "Ticker Yahoo Finance": "ETF.PA", "Secteur 1": "ETF",
                "Pays": "France", "Secteur": "Healthcare",
            },
            {
                "Ticker Yahoo Finance": "AIR.PA", "Secteur 1": "Action",
                "Pays": "France", "Secteur": "Industrials",
            },
        ]).to_excel(writer, index=False)
        pd.DataFrame([{"Ticker": "ETF.PA", "France": 100.0}]).to_excel(
            writer, sheet_name="ETF_Pays", index=False,
        )
        pd.DataFrame([{"Ticker": "ETF.PA", "Defensif_pct": 100.0}]).to_excel(
            writer, sheet_name="ETF_Defensif", index=False,
        )

    defensive, countries = load_lookthrough(str(path))

    assert "ETF.PA" not in defensive
    assert "ETF.PA" not in countries
    assert countries["AIR.PA"] == {"France": 1.0}
