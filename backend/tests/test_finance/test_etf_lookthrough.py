"""Récup justETF incrémentale : sélection des ETF non-faits + fusion non destructive."""

import pandas as pd
import pytest

from app.services.finance.buffett.etf_lookthrough import (
    _done_pays_tickers,
    _etf_dates,
    countries_from_top_holdings,
    merge_pays,
    refresh_country_exposure,
    resolve_country_exposures,
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


def test_top_holdings_requires_high_known_coverage():
    holdings = pd.DataFrame(
        {"Holding Percent": [0.55, 0.25, 0.10]},
        index=["AAA", "BBB", "UNKNOWN"],
    )
    countries, coverage = countries_from_top_holdings(
        holdings,
        {"AAA": "France", "BBB": "Germany"},
        min_coverage=0.90,
    )
    assert countries == {}
    assert coverage == 0.80


def test_top_holdings_keeps_uncovered_remainder_unknown():
    holdings = pd.DataFrame(
        {"Holding Percent": [0.60, 0.35]},
        index=["AAA", "BBB"],
    )
    countries, coverage = countries_from_top_holdings(
        holdings,
        {"AAA": "France", "BBB": "Germany"},
    )
    assert coverage == 0.95
    assert countries == pytest.approx({
        "France": 0.60,
        "Germany": 0.35,
        "Inconnu": 0.05,
    })


def test_resolver_reuses_country_composition_across_same_isin():
    broker = pd.DataFrame([
        {
            "Ticker Yahoo Finance": "WORLD.PA",
            "Secteur 1": "ETF",
            "Secteur 2": "Actions",
            "Secteur 4": "Monde",
            "ISIN": "FR0000000001",
        },
        {
            "Ticker Yahoo Finance": "WORLD.DE",
            "Secteur 1": "ETF",
            "Secteur 2": "Actions",
            "Secteur 4": "Monde",
            "ISIN": "FR0000000001",
        },
    ])
    pays = pd.DataFrame([
        {
            "Ticker": "WORLD.PA",
            "Source": "issuer",
            "United States": 70.0,
            "Japan": 30.0,
        },
    ])
    resolved, diagnostics, updates = resolve_country_exposures(
        ["WORLD.DE"],
        etf_tickers={"WORLD.DE"},
        broker_table=broker,
        pays_table=pays,
        cached_compositions={},
        holdings_fetcher=lambda _ticker: None,
        max_live_fetches=0,
    )
    assert resolved["WORLD.DE"] == {"United States": 0.7, "Japan": 0.3}
    assert diagnostics["sources"] == {"same_isin": 1}
    assert updates[0]["ISIN"] == "FR0000000001"


def test_resolver_uses_index_region_and_excludes_unresolved_etf():
    broker = pd.DataFrame([
        {
            "Ticker Yahoo Finance": "GRE.PA",
            "Nom": "Greece ETF",
            "Secteur 1": "ETF",
            "Secteur 2": "Actions",
            "Secteur 4": "Grèce",
        },
        {
            "Ticker Yahoo Finance": "MYSTERY.PA",
            "Nom": "Mystery ETF",
            "Secteur 1": "ETF",
            "Secteur 2": "Actions",
            "Secteur 4": "Thématique inconnue",
        },
    ])
    resolved, diagnostics, _updates = resolve_country_exposures(
        ["GRE.PA", "MYSTERY.PA"],
        etf_tickers={"GRE.PA", "MYSTERY.PA"},
        broker_table=broker,
        pays_table=pd.DataFrame(),
        cached_compositions={},
        holdings_fetcher=lambda _ticker: None,
        max_live_fetches=0,
    )
    assert resolved["GRE.PA"] == {"Greece": 1.0}
    assert "MYSTERY.PA" not in resolved
    assert diagnostics["excluded_tickers"] == ["MYSTERY.PA"]


def test_sourced_cache_replaces_undated_legacy_country_row():
    broker = pd.DataFrame([{
        "Ticker Yahoo Finance": "GRE.PA",
        "Nom": "Greece ETF",
        "Secteur 1": "ETF",
        "Secteur 2": "Actions",
        "Secteur 4": "Grèce",
    }])
    legacy = pd.DataFrame([{"Ticker": "GRE.PA", "Greece": 100.0}])
    cached = {"GRE.PA": {
        "pays": {"Greece": 86.29, "United Kingdom": 13.71},
        "source": "issuer factsheet",
        "date_analyse": "2026-05-31",
        "isin": "FR0010405431",
    }}
    resolved, diagnostics, updates = resolve_country_exposures(
        ["GRE.PA"],
        etf_tickers={"GRE.PA"},
        broker_table=broker,
        pays_table=legacy,
        cached_compositions=cached,
        holdings_fetcher=lambda _ticker: None,
        max_live_fetches=0,
    )
    assert resolved["GRE.PA"] == pytest.approx({
        "Greece": 0.8629,
        "United Kingdom": 0.1371,
    })
    assert diagnostics["sources"] == {"issuer factsheet": 1}
    assert updates[0]["Date_analyse"] == "2026-05-31"


def test_resolver_marks_physical_commodity_as_non_geographic():
    broker = pd.DataFrame([{
        "Ticker Yahoo Finance": "GLDM",
        "Secteur 1": "ETF",
        "Secteur 2": "Matières premières",
        "Secteur 4": "Or",
    }])
    resolved, diagnostics, _updates = resolve_country_exposures(
        ["GLDM"],
        etf_tickers={"GLDM"},
        broker_table=broker,
        pays_table=pd.DataFrame(),
        cached_compositions={},
        holdings_fetcher=lambda _ticker: None,
        max_live_fetches=0,
    )
    assert resolved["GLDM"] == {"Sans pays": 1.0}
    assert diagnostics["excluded"] == 0


def test_merge_pays_preserves_source_isin_and_coverage():
    out = merge_pays(None, [{
        "Ticker": "A.L",
        "Nom": "A",
        "Source": "same_isin",
        "ISIN": "IE0000000001",
        "Couverture_pct": 95.0,
        "pays": {"France": 95.0, "Inconnu": 5.0},
    }], today="2026-08-04")
    row = out.iloc[0]
    assert row["Source"] == "same_isin"
    assert row["ISIN"] == "IE0000000001"
    assert row["Couverture_pct"] == 95.0


def test_load_lookthrough_ignores_legacy_etf_country_sheet(tmp_path):
    from app.services.finance.buffett.lookthrough import load_lookthrough

    path = tmp_path / "ToutBroker.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(columns=["Ticker Yahoo Finance"]).to_excel(
            writer, sheet_name="Sheet1", index=False,
        )
        pd.DataFrame([{
            "Ticker": "A.L",
            "Source": "issuer",
            "ISIN": "IE0000000001",
            "Indice": "MSCI Test",
            "Couverture_pct": 100.0,
            "France": 60.0,
            "Germany": 40.0,
        }]).to_excel(writer, sheet_name="ETF_Pays", index=False)
    _defensive, countries = load_lookthrough(str(path))
    assert "A.L" not in countries


def test_recent_sourced_etf_does_not_need_refresh():
    broker = pd.DataFrame([{
        "Ticker Yahoo Finance": "A.L",
        "Secteur 1": "ETF",
        "Secteur 2": "Actions",
    }])
    today = pd.Timestamp.today().date().isoformat()
    pays = pd.DataFrame([{
        "Ticker": "A.L",
        "Source": "yahoo_top_holdings",
        "Date_analyse": today,
        "France": 100.0,
    }])
    _resolved, diagnostics, _updates = resolve_country_exposures(
        ["A.L"],
        etf_tickers={"A.L"},
        broker_table=broker,
        pays_table=pays,
        cached_compositions={},
        max_live_fetches=0,
        include_unresolved=True,
    )
    assert diagnostics["refresh_tickers"] == []


def test_old_or_undated_etf_is_refreshed_only_if_selected_later():
    broker = pd.DataFrame([{
        "Ticker Yahoo Finance": "A.L",
        "Secteur 1": "ETF",
        "Secteur 2": "Actions",
    }])
    pays = pd.DataFrame([{
        "Ticker": "A.L",
        "Source": "issuer",
        "Date_analyse": "2020-01-01",
        "France": 100.0,
    }])
    resolved, diagnostics, _updates = resolve_country_exposures(
        ["A.L", "NEW.L"],
        etf_tickers={"A.L", "NEW.L"},
        broker_table=broker,
        pays_table=pays,
        cached_compositions={},
        max_live_fetches=0,
        include_unresolved=True,
    )
    assert resolved["NEW.L"] == {"Inconnu": 1.0}
    assert diagnostics["refresh_tickers"] == ["A.L", "NEW.L"]
    assert diagnostics["live_fetches"] == 0


def test_failed_complete_holdings_check_dates_a_usable_fallback():
    result = refresh_country_exposure(
        "WORLD.L",
        country_by_symbol={},
        holdings_fetcher=lambda _ticker: pd.DataFrame(),
        metadata={"Nom": "World ETF", "ISIN": "IE0000000001"},
        fallback_countries={"United States": 0.7, "Japan": 0.3},
    )
    assert result is not None
    assert result["Source"] == "fallback_verified_no_complete_yahoo_holdings"
    assert result["pays"] == {"United States": 70.0, "Japan": 30.0}


def test_unknown_fallback_is_not_marked_fresh_when_yahoo_fails():
    result = refresh_country_exposure(
        "UNKNOWN.L",
        country_by_symbol={},
        holdings_fetcher=lambda _ticker: pd.DataFrame(),
        fallback_countries={"Inconnu": 1.0},
    )
    assert result is None


def test_network_failure_never_dates_even_a_usable_fallback():
    result = refresh_country_exposure(
        "WORLD.L",
        country_by_symbol={},
        holdings_fetcher=lambda _ticker: None,
        fallback_countries={"United States": 0.7, "Japan": 0.3},
    )
    assert result is None


def test_synthetic_etf_country_resolution_never_reads_swap_collateral():
    broker = pd.DataFrame([{
        "Ticker Yahoo Finance": "SYNTH.PA",
        "Secteur 1": "ETF",
        "Secteur 2": "Actions",
        "Nom": "Amundi PEA Japon (TOPIX) UCITS ETF",
        "Indice": "TOPIX",
        "Réplication": "Synthétique",
        "Secteur 4": "Japon",
    }])

    def forbidden(_ticker):
        raise AssertionError("le collatéral Yahoo d'un ETF synthétique a été lu")

    resolved, diagnostics, _updates = resolve_country_exposures(
        ["SYNTH.PA"],
        etf_tickers={"SYNTH.PA"},
        broker_table=broker,
        pays_table=pd.DataFrame(),
        cached_compositions={},
        holdings_fetcher=forbidden,
        max_live_fetches=10,
    )

    assert resolved["SYNTH.PA"] == {"Japan": 1.0}
    assert diagnostics["live_fetches"] == 0
