import datetime as dt
from types import SimpleNamespace

import pandas as pd
import pytest
from sqlmodel import select

from app.models.finance import BuffettRun, BuffettRunResult
from app.services.finance.buffett.equity_lookthrough import (
    _is_non_equity_etf,
    build_equity_lookthrough,
    economic_exposure_from_payload,
    etf_composition_quality,
    holdings_from_yahoo,
    index_risk_lookthrough,
)


def test_non_equity_detection_reads_real_catalog_series_case_insensitively():
    assert _is_non_equity_etf(
        pd.Series({"Nom": "21Shares Bitcoin Core ETP", "Secteur": "ETF"})
    )
    assert _is_non_equity_etf(
        pd.Series({"Nom": "Amundi Euro Government Bond", "Secteur": "ETF"})
    )
    assert not _is_non_equity_etf(
        pd.Series({"Nom": "iShares MSCI World ETF", "Secteur": "ETF"})
    )


def test_quality_uses_official_asset_class_over_bad_catalog_sector():
    quality = etf_composition_quality(
        {
            "holdings": [{
                "isin": "US912810TM09", "weight": 1.0,
                "security_type": "BOND",
            }],
            "source": "issuer_fund_holdings",
            "replication": "physical",
            "asset_class": "fixed_income",
        },
        pd.Series({"Nom": "Fund share class", "Secteur": "ETF", "Secteur 2": "Actions"}),
        minimum_coverage=0.90,
    )

    assert quality["eligible"] is True
    assert quality["reason"] == "adapted_non_equity"


def test_synthetic_etf_requires_the_exact_official_index_constituents():
    holdings = [
        {"ticker": "AAA", "weight": 0.5, "sector": "Technology", "country": "US"},
        {"ticker": "BBB", "weight": 0.5, "sector": "Financial Services", "country": "FR"},
    ]
    row = {"nom": "Synthetic World ETF", "secteur": "ETF"}
    rejected = etf_composition_quality(
        {
            "holdings": holdings,
            "source": "issuer_physical_index_proxy",
            "replication": "synthetic",
            "index_id": "MSCI-WORLD",
        },
        row,
        minimum_coverage=0.90,
    )
    accepted = etf_composition_quality(
        {
            "holdings": holdings,
            "source": "official_index_constituents",
            "replication": "synthetic",
        },
        row,
        minimum_coverage=0.90,
    )

    assert rejected["eligible"] is False
    assert rejected["reason"] == "synthetic_index_constituents_required"
    assert accepted["eligible"] is True


def test_synthetic_etf_accepts_an_explicit_same_index_physical_tracker_proxy():
    holdings = [
        {"ticker": "AAA", "weight": 0.55, "sector": "Technology", "country": "US"},
        {"ticker": "BBB", "weight": 0.45, "sector": "Industrials", "country": "FR"},
    ]
    quality = etf_composition_quality(
        {
            "holdings": holdings,
            "source": "physical_tracker_proxy",
            "replication": "synthetic",
            "index_id": "MSCI-WORLD",
            "proxy_ticker": "PHYS.DE",
            "proxy_isin": "IE0000000001",
            "proxy_source_url": "https://issuer.example/holdings",
            "proxy_warning": "proxy économique",
        },
        {"nom": "Synthetic World ETF", "secteur": "ETF"},
        minimum_coverage=0.90,
    )

    assert quality["eligible"] is True
    assert quality["reason"] == "physical_tracker_proxy"
    assert quality["proxy_ticker"] == "PHYS.DE"
    assert quality["proxy_isin"] == "IE0000000001"


def test_synthetic_etf_without_identified_index_has_explicit_reason_and_error():
    quality = etf_composition_quality(
        {
            "holdings": [],
            "source": "official_index_constituents_required",
            "replication": "synthetic",
            "index_status": "provider_unsupported",
            "index_error": "aucun connecteur officiel public disponible",
        },
        {"nom": "Synthetic Unknown ETF", "secteur": "ETF"},
        minimum_coverage=0.90,
    )

    assert quality["eligible"] is False
    assert quality["reason"] == "synthetic_index_unresolved"
    assert quality["index_status"] == "provider_unsupported"
    assert quality["index_error"] == "aucun connecteur officiel public disponible"


def test_gold_miners_etf_is_an_equity_fund_not_physical_gold():
    assert _is_non_equity_etf({"nom": "VanEck Gold Miners ETF", "secteur": "ETF"}) is False
    assert _is_non_equity_etf({"nom": "Physical Gold ETC", "secteur": "ETF"}) is True


def test_fixed_income_and_gilts_are_not_equity_funds():
    assert _is_non_equity_etf({"nom": "Core UK Gilts UCITS ETF", "secteur": "ETF"}) is True
    assert _is_non_equity_etf({"nom": "Global Fixed Income ETF", "secteur": "ETF"}) is True
    assert _is_non_equity_etf({"nom": "Physical Silver ETC", "secteur": "ETF"}) is True
    assert _is_non_equity_etf({"nom": "Silver Miners ETF", "secteur": "ETF"}) is False
    assert _is_non_equity_etf({
        "nom": "Generic UCITS ETF",
        "secteur": "ETF",
        "Secteur 2": "Fixed Income - Emerging Markets Bond",
    }) is True


def test_official_bond_holdings_use_bond_rules_not_equity_sector_country_rules():
    quality = etf_composition_quality(
        {
            "holdings": [
                {
                    "isin": "US0000000001",
                    "name": "Republic government bond 2030",
                    "security_type": "Bond",
                    "weight": 1.0,
                }
            ],
            "source": "issuer_fund_holdings",
            "replication": "physical",
            "asset_class": "fixed_income",
            "index_name": "J.P. Morgan EMBI Global Core Index",
        },
        {"nom": "iShares Emerging Markets Bond ETF", "Secteur 2": "Obligations"},
        minimum_coverage=0.90,
    )

    assert quality["eligible"] is True
    assert quality["reason"] == "adapted_non_equity"


def test_crypto_etp_is_explicitly_excluded_even_when_physically_backed():
    quality = etf_composition_quality(
        {
            "holdings": [{"ticker": "ETH", "name": "Ethereum", "weight": 1.0}],
            "source": "issuer_fund_holdings",
            "replication": "physical",
            "name": "21Shares Ethereum Staking ETP",
        },
        {"nom": "21Shares Ethereum Staking ETP", "Secteur 2": "Crypto ETP"},
        minimum_coverage=0.90,
    )

    assert quality["eligible"] is False
    assert quality["reason"] == "crypto_etp_excluded"


def test_official_margins_are_eligible_but_never_create_country_sector_bonus():
    payload = {
        "holdings": [],
        "source": "issuer_official_aggregate_exposure",
        "scope": "economic_exposure",
        "replication": "synthetic",
        "countries": {"United States": 0.7, "Japan": 0.3},
        "sectors": {"Technology": 0.6, "Industrials": 0.4},
        "country_coverage": 1.0,
        "sector_coverage": 1.0,
    }
    quality = etf_composition_quality(
        payload,
        {"nom": "Synthetic World ETF", "secteur": "ETF"},
        minimum_coverage=0.90,
    )
    countries, sectors, _ = index_risk_lookthrough({"SYN.PA": payload}, {})
    from app.services.finance.buffett.equity_lookthrough import (
        index_sector_country_lookthrough,
    )

    assert quality["eligible"] is True
    assert quality["reason"] == "official_aggregate_exposure"
    assert countries["SYN.PA"] == payload["countries"]
    assert sectors["SYN.PA"] == payload["sectors"]
    assert index_sector_country_lookthrough({"SYN.PA": payload}, {})["SYN.PA"] == {}


def _row(ticker, weight, *, etf=False, name=None):
    return SimpleNamespace(
        ticker=ticker,
        nom=name or ticker,
        allocation_pct=weight,
        secteur="ETF" if etf else "Technology",
        chance_moat=200.0 if etf else 90.0,
    )


def test_holdings_from_yahoo_accepts_fraction_and_percent_formats():
    fractions = pd.DataFrame(
        {"Name": ["NVIDIA", "Apple"], "Holding Percent": [0.20, 0.15]},
        index=["NVDA", "AAPL"],
    )
    percentages = pd.DataFrame(
        {"name": ["NVIDIA", "Apple"], "% Assets": [20.0, 15.0]},
        index=["NVDA", "AAPL"],
    )

    assert [item["weight"] for item in holdings_from_yahoo(fractions)] == [0.20, 0.15]
    assert [item["weight"] for item in holdings_from_yahoo(percentages)] == [0.20, 0.15]


def test_economic_composition_requires_an_official_index_source():
    physical = {
        "holdings": [
            {"ticker": "AAA", "weight": 0.50},
            {"ticker": "BBB", "weight": 0.25},
        ],
        "source": "yahoo_top_holdings",
        "replication": "physical",
    }
    exposure, coverage, _, usable = economic_exposure_from_payload(
        physical, minimum_coverage=0.75
    )
    assert exposure == {"AAA": 0.50, "BBB": 0.25}
    assert coverage == pytest.approx(0.75)
    assert usable is False

    physical["source"] = "official_index_constituents"
    assert economic_exposure_from_payload(
        physical, minimum_coverage=0.75
    )[3] is True

    physical["holdings"][1]["weight"] = 0.24
    assert economic_exposure_from_payload(
        physical, minimum_coverage=0.75
    )[3] is False

    physical["holdings"][1]["weight"] = 0.25
    physical["replication"] = "synthetic"
    assert economic_exposure_from_payload(
        physical, minimum_coverage=0.75
    )[3] is True
    physical["source"] = "catalog_etf_constituents"
    assert economic_exposure_from_payload(
        physical, minimum_coverage=0.75
    )[3] is False

    physical["source"] = "issuer_physical_index_proxy"
    assert economic_exposure_from_payload(
        physical, minimum_coverage=0.75
    )[3] is False

    physical["source"] = "physical_tracker_proxy"
    assert economic_exposure_from_payload(
        physical, minimum_coverage=0.75
    )[3] is True


def test_missing_index_is_enriched_before_synthetic_etf_is_rejected(monkeypatch):
    from app.services.finance.buffett import (
        broker_availability,
        equity_lookthrough,
        etf_index_registry,
        official_etf_enrichment,
        official_index_enrichment,
    )

    enriched = {"done": False}
    composition = {
        "holdings": [
            {
                "ticker": "7203.T",
                "name": "Toyota",
                "country": "Japan",
                "sector": "Consumer Cyclical",
                "weight": 1.0,
            }
        ],
        "coverage": 1.0,
        "source": "official_index_constituents",
    }
    index_metadata = {
        "SYN.PA": {
            "identity_key": "FR0000000001",
            "index_id": "TOPIX",
            "index_name": "TOPIX",
            "replication": "synthetic",
            "source": "issuer_product_page",
        }
    }

    monkeypatch.setattr(broker_availability, "load_broker_table", lambda: pd.DataFrame())
    monkeypatch.setattr(broker_availability, "load_etf_tickers", lambda _table: {"SYN.PA"})
    monkeypatch.setattr(official_etf_enrichment, "enrich_official_etfs", lambda *a, **k: {})
    monkeypatch.setattr(
        equity_lookthrough,
        "load_etf_replication_metadata",
        lambda _universe: {"SYN.PA": {"replication": "synthetic"}},
    )
    monkeypatch.setattr(
        etf_index_registry,
        "resolve_index_registry",
        lambda *a, **k: index_metadata,
    )
    monkeypatch.setattr(
        etf_index_registry,
        "cached_index_composition",
        lambda _index_id, **kwargs: composition if enriched["done"] else None,
    )
    monkeypatch.setattr(
        etf_index_registry,
        "load_registry",
        lambda: {
            "indices": {
                "TOPIX": {
                    "provider": "jpx",
                    "official_enrichment": {"status": "complete"},
                }
            }
        },
    )

    def enrich(index_ids, **kwargs):
        assert index_ids == {"TOPIX"}
        enriched["done"] = True
        return {"TOPIX": {"status": "complete"}}

    monkeypatch.setattr(official_index_enrichment, "enrich_official_indices", enrich)

    result = equity_lookthrough.fetch_etf_holdings(["SYN.PA"])

    assert enriched["done"] is True
    assert result["SYN.PA"]["source"] == "index_composition_cache"
    assert result["SYN.PA"]["holdings"][0]["ticker"] == "7203.T"

def test_etfs_are_replaced_duplicate_tickers_are_aggregated_and_residual_is_other():
    allocation = [
        _row("ETF1", 40.0, etf=True),
        _row("ETF2", 30.0, etf=True),
        _row("NVDA", 10.0),
        _row("C5H.IR", 20.0),
    ]
    compositions = {
        "ETF1": [
            {"ticker": "NVDA", "name": "NVIDIA", "weight": 0.20},
            {"ticker": "AAPL", "name": "Apple", "weight": 0.70},
        ],
        "ETF2": [
            {"ticker": "NVDA", "name": "NVIDIA", "weight": 0.10},
            {"ticker": "MSFT", "name": "Microsoft", "weight": 0.80},
        ],
    }

    result = build_equity_lookthrough(allocation, compositions)
    by_ticker = {row["ticker"]: row for row in result["rows"]}

    assert by_ticker["NVDA"]["weight_pct"] == pytest.approx(21.0)
    assert by_ticker["AAPL"]["weight_pct"] == pytest.approx(28.0)
    assert by_ticker["MSFT"]["weight_pct"] == pytest.approx(24.0)
    assert by_ticker["C5H.IR"]["weight_pct"] == pytest.approx(20.0)
    assert by_ticker["AUTRES_ACTIONS"]["weight_pct"] == pytest.approx(7.0)
    assert by_ticker["NVDA"]["sources"] == ["Action directe", "ETF1", "ETF2"]
    assert sum(row["weight_pct"] for row in result["rows"]) == pytest.approx(100.0)
    assert result["coverage_pct"] == pytest.approx(93.0)


def test_missing_etf_composition_goes_entirely_to_single_other_line():
    result = build_equity_lookthrough(
        [_row("UNKNOWN", 40.0, etf=True), _row("PRDO", 60.0)],
        {"UNKNOWN": []},
    )

    assert [(row["ticker"], row["weight_pct"]) for row in result["rows"]] == [
        ("PRDO", 60.0),
        ("COMPOSITION_INDISPONIBLE", 40.0),
    ]
    assert result["etfs"][0]["holdings_coverage_pct"] == 0.0


def test_rounding_above_one_is_normalized_without_creating_weight():
    result = build_equity_lookthrough(
        [_row("ETF", 100.0, etf=True)],
        {
            "ETF": [
                {"ticker": "AAA", "name": "AAA", "weight": 0.51},
                {"ticker": "BBB", "name": "BBB", "weight": 0.50},
            ]
        },
    )

    assert result["other_pct"] == 0.0
    assert sum(row["weight_pct"] for row in result["rows"]) == pytest.approx(100.0)


def test_completed_run_endpoint_persists_and_reuses_the_decomposition(mem_session, monkeypatch):
    from app.api.finance.buffett import buffett_run_equity_lookthrough
    from app.services.finance.buffett import equity_lookthrough

    run = BuffettRun(run_date=dt.date.today(), statut="termine")
    mem_session.add(run)
    mem_session.commit()
    mem_session.refresh(run)
    mem_session.add_all(
        [
            BuffettRunResult(
                run_id=run.id,
                ticker="ETF1",
                nom="ETF test",
                secteur="ETF",
                chance_moat=200.0,
                allocation_pct=40.0,
            ),
            BuffettRunResult(
                run_id=run.id,
                ticker="PRDO",
                nom="Perdoceo",
                secteur="Consumer Defensive",
                chance_moat=89.0,
                allocation_pct=60.0,
            ),
        ]
    )
    mem_session.commit()
    monkeypatch.setattr(
        equity_lookthrough,
        "fetch_etf_holdings",
        lambda _tickers: {
            "ETF1": [{"ticker": "NVDA", "name": "NVIDIA", "weight": 0.20}]
        },
    )

    first = buffett_run_equity_lookthrough(run.id, False, mem_session)
    assert first["run_id"] == run.id
    assert {row["ticker"]: row["weight_pct"] for row in first["rows"]} == {
        "PRDO": 60.0,
        "AUTRES_ACTIONS": 32.0,
        "NVDA": 8.0,
    }

    monkeypatch.setattr(
        equity_lookthrough,
        "fetch_etf_holdings",
        lambda _tickers: pytest.fail("le cache de la run devait être réutilisé"),
    )
    second = buffett_run_equity_lookthrough(run.id, False, mem_session)
    assert second == first


def test_non_equity_etf_is_not_reported_as_unknown_actions():
    result = build_equity_lookthrough(
        [_row("ICOM.L", 25.0, etf=True, name="iShares Diversified Commodity Swap")],
        {"ICOM.L": []},
    )

    assert result["non_equity_pct"] == pytest.approx(25.0)
    assert result["unknown_pct"] == 0.0
    assert result["rows"][0]["ticker"] == "NON_ACTIONS"


def test_bond_etf_is_grouped_by_country_and_maturity_in_portfolio_rows(monkeypatch):
    monkeypatch.setattr(
        "app.services.finance.buffett.equity_lookthrough.dt.date",
        type("FixedDate", (dt.date,), {"today": classmethod(lambda cls: cls(2026, 9, 1))}),
    )
    result = build_equity_lookthrough(
        [_row("EUN9.DE", 10.0, etf=True, name="iShares EUR Govt Bond 5-7yr")],
        {
            "EUN9.DE": {
                "name": "iShares EUR Govt Bond 5-7yr",
                "asset_class": "fixed_income",
                "source": "issuer_fund_holdings",
                "replication": "physical",
                "holdings": [
                    {
                        "name": "France government bond",
                        "country": "France",
                        "asset_class": "Fixed Income",
                        "maturity": "20321125",
                        "weight": 0.60,
                    },
                    {
                        "name": "Italy government bond",
                        "country": "Italy",
                        "asset_class": "Fixed Income",
                        "maturity": "20330525",
                        "weight": 0.35,
                    },
                    {
                        "name": "Cash",
                        "country": "Ireland",
                        "asset_class": "Cash",
                        "weight": 0.05,
                    },
                ],
            }
        },
    )

    by_name = {row["name"]: row for row in result["rows"]}
    assert by_name["Obligation — France — 5–7 ans"]["weight_pct"] == pytest.approx(6.0)
    assert by_name["Obligation — Italy — 5–7 ans"]["weight_pct"] == pytest.approx(3.5)
    assert by_name["Obligation — France — 5–7 ans"]["asset_type"] == "obligation"
    assert by_name["Autres expositions non-actions non détaillées"]["weight_pct"] == pytest.approx(0.5)
    assert result["known_bonds_pct"] == pytest.approx(9.5)
    assert result["other_non_equity_pct"] == pytest.approx(0.5)
    assert result["non_equity_pct"] == pytest.approx(10.0)
    assert result["unknown_pct"] == 0.0
    assert sum(row["weight_pct"] for row in result["rows"]) == pytest.approx(10.0)


def test_index_constituents_are_the_single_source_for_etf_country_and_defensive():
    countries, sectors, defensive = index_risk_lookthrough(
        {
            "ETF.PA": {
                "holdings": [
                    {"ticker": "A", "weight": 0.50},
                    {"ticker": "B", "weight": 0.30},
                ],
                "source": "index_composition_cache",
            },
        },
        {
            "A": {"country": "France", "sector": "Utilities"},
            "B": {"country": "United States", "sector": "Technology"},
            # Une éventuelle ligne de métadonnées ETF n'est jamais consultée.
            "ETF.PA": {"country": "Germany", "sector": "Healthcare"},
        },
    )

    assert countries["ETF.PA"] == {
        "France": pytest.approx(0.50),
        "United States": pytest.approx(0.30),
        "Inconnu": pytest.approx(0.20),
    }
    assert sectors["ETF.PA"] == {
        "Services aux collectivites": pytest.approx(0.50),
        "Technologie": pytest.approx(0.30),
    }
    assert defensive["ETF.PA"] == pytest.approx(0.50)


def test_bond_holdings_feed_country_risk_sector_and_duration_sensitive_defensive():
    countries, sectors, defensive = index_risk_lookthrough(
        {
            "BOND.DE": {
                "name": "Investment Grade Corporate Bond ETF",
                "index": "Corporate Bond Index",
                "asset_class": "fixed_income",
                "holdings": [
                    {
                        "isin": "FR0000000001", "name": "French issuer bond",
                        "weight": 0.60, "country": "France", "rating": "A",
                        "duration": "2.0", "asset_class": "Fixed Income",
                    },
                    {
                        "isin": "DE0000000002", "name": "German issuer bond",
                        "weight": 0.35, "country": "Germany", "rating": "BBB",
                        "duration": "12.0", "asset_class": "Fixed Income",
                    },
                ],
                "source": "issuer_fund_holdings",
            },
        },
        {},
    )

    assert countries["BOND.DE"] == {
        "France": pytest.approx(0.60),
        "Germany": pytest.approx(0.35),
        "Inconnu": pytest.approx(0.05),
    }
    assert sectors["BOND.DE"] == {"Obligations entreprises IG": 1.0}
    assert 0.25 < defensive["BOND.DE"] < 0.65


def test_money_market_index_has_no_fake_collateral_country_and_is_defensive():
    countries, sectors, defensive = index_risk_lookthrough(
        {
            "OBLI.PA": {
                "name": "Amundi PEA Euro Court Terme UCITS ETF",
                "index": "Solactive Euro Overnight Return Index",
                "asset_class": "fixed_income",
                "holdings": [],
                "source": "official_index_constituents_required",
            },
        },
        {},
    )

    assert countries["OBLI.PA"] == {"Sans pays": 1.0}
    assert sectors["OBLI.PA"] == {"Monetaire": 1.0}
    assert defensive["OBLI.PA"] == pytest.approx(0.95)


def test_credit_agricole_name_does_not_turn_a_bank_etf_into_fixed_income():
    countries, sectors, defensive = index_risk_lookthrough(
        {
            "BANK.DE": {
                "name": "EURO STOXX Banks ETF",
                "holdings": [
                    {
                        "ticker": "ACA.PA", "name": "Credit Agricole SA",
                        "weight": 0.55, "country": "France", "sector": "Financials",
                        "asset_class": "Equity",
                    },
                    {
                        "ticker": "BBVA.MC", "name": "Banco Bilbao Vizcaya",
                        "weight": 0.45, "country": "Spain", "sector": "Financials",
                        "asset_class": "Equity",
                    },
                ],
                "source": "issuer_fund_holdings",
            },
        },
        {},
    )

    assert countries["BANK.DE"] == {"France": 0.55, "Spain": 0.45}
    assert sectors["BANK.DE"] == {"Finance": 1.0}
    assert defensive["BANK.DE"] == 0.0


def test_selecting_world_scenario_changes_target_without_creating_transactions(mem_session):
    from app.api.finance.buffett import select_buffett_scenario
    from app.api.schemas_finance import BuffettScenarioSelectIn

    scenario_allocation = [{
        "Ticker": "WPEA.PA", "AnalysisTicker": "WPEA.PA", "Broker": "boursedirect",
        "eur": 1000.0, "prix": 10.0, "shares": 100, "type": "shares",
        "Poids total (%)": 55.0,
    }]
    run = BuffettRun(
        run_date=dt.date.today(),
        statut="termine",
        params_json={
            "equity_lookthrough_v2": {"stale": True},
            "optimization": {
                "world_scenarios": {
                    "active": "free",
                    "world_55": {"allocation": scenario_allocation},
                }
            },
        },
    )
    mem_session.add(run)
    mem_session.commit()
    mem_session.refresh(run)
    mem_session.add(BuffettRunResult(
        run_id=run.id, ticker="WPEA.PA", nom="World", secteur="ETF",
        chance_moat=200.0,
    ))
    mem_session.commit()

    response = select_buffett_scenario(
        run.id, BuffettScenarioSelectIn(scenario="world_55"), mem_session
    )
    mem_session.refresh(run)
    row = mem_session.exec(
        select(BuffettRunResult).where(BuffettRunResult.run_id == run.id)
    ).one()

    assert response["active_scenario"] == "world_55"
    assert row.allocation_pct == 55.0
    assert run.params_json["optimization"]["world_scenarios"]["active"] == "world_55"
    assert "equity_lookthrough_v2" not in run.params_json


def test_topix_jpx_33_sectors_are_fully_classified():
    sectors = [
        "Electric Appliances", "Banks", "Wholesale Trade", "Machinery",
        "Information & Communication", "Transportation Equipment", "Chemicals",
        "Retail Trade", "Services", "Insurance", "Pharmaceutical",
        "Nonferrous Metals", "Foods", "Construction", "Precision Instruments",
        "Other Products", "Land Transportation", "Real Estate",
        "Other Financing Business", "Electric Power & Gas",
        "Glass & Ceramics Products", "Securities & Commodity Futures",
        "Iron & Steel", "Rubber Products", "Metal Products",
        "Marine Transportation", "Oil & Coal Products", "Mining",
        "Textiles & Apparels", "Air Transportation",
        "Warehousing & Harbor Transportation Services", "Pulp & Paper",
        "Fishery,Agriculture & Forestry",
    ]
    weight = 1.0 / len(sectors)
    quality = etf_composition_quality(
        {
            "holdings": [
                {"ticker": f"{1000 + index}.T", "weight": weight,
                 "sector": sector, "country": "Japan"}
                for index, sector in enumerate(sectors)
            ],
            "source": "official_index_constituents",
            "replication": "synthetic", "index_id": "TOPIX",
        },
        {"Nom": "Amundi PEA Japon TOPIX", "Secteur": "ETF"},
        minimum_coverage=0.90,
    )

    assert quality["eligible"] is True
    assert quality["coverage"] == pytest.approx(1.0)
    assert quality["joint_coverage"] == pytest.approx(1.0)
