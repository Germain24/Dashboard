import datetime as dt
import json

import pandas as pd

from app.services.finance.buffett.etf_index_registry import (
    cached_fund_composition,
    cached_index_composition,
    cached_physical_index_proxy,
    canonical_constituent_set_id,
    canonical_index_id,
    cusip_to_isin,
    index_groups,
    infer_index_from_fund_name,
    infer_replication_from_fund_name,
    registry_workbook_frames,
    resolve_index_registry,
    save_registry,
    sync_registry_to_broker_workbook,
    valid_isin,
)


def test_constituent_identity_strips_share_and_replication_labels_only():
    base = canonical_constituent_set_id("S&P 500 Index")

    assert canonical_constituent_set_id("S&P 500 Swap (Acc)") == base
    assert canonical_constituent_set_id("Xtr.IEXtr. S&P 500 Swap II EUR Dist") == base
    assert canonical_constituent_set_id("S&P 500 EUR Hedged UCITS ETF") == base
    assert canonical_constituent_set_id("S&P 500 Equal Weight") != base
    assert canonical_constituent_set_id("S&P 500 ESG Screened") != base
    assert canonical_constituent_set_id("S&P 500 2x Inverse Daily") != base


def test_constituent_identity_strips_truncated_fund_and_return_markers():
    assert canonical_constituent_set_id("MONDE MSCI World UCI") == canonical_constituent_set_id(
        "MSCI World Index"
    )
    assert canonical_constituent_set_id("MDAX (Performance Index) NET") == canonical_constituent_set_id(
        "MDAX"
    )


def test_constituent_identity_reconciles_verified_stoxx_supersector_labels():
    assert canonical_constituent_set_id(
        "STOXX Europe 600 Technology (Capped) TR (EUR)"
    ) == canonical_constituent_set_id("STOXX Europe 600 Technology Index")
    assert canonical_constituent_set_id(
        "STOXX Europe 600 HealthCare (Capped) TR"
    ) == canonical_constituent_set_id("STOXX Europe 600 Health Care Index")


def test_large_compositions_are_externalized_and_loaded_transparently(tmp_path):
    path = tmp_path / "indices.json"
    holdings = [
        {"ticker": f"T{i}", "weight": 1 / 30}
        for i in range(30)
    ]
    registry = {
        "version": 2,
        "funds": {
            "ISIN:IE0000000001": {
                "composition": {
                    "source": "issuer_fund_holdings",
                    "updated_at": dt.date.today().isoformat(),
                    "holdings": holdings,
                },
            },
        },
        "indices": {
            "TEST-INDEX": {
                "name": "Test Index",
                "composition": {
                    "source": "official_index_constituents",
                    "updated_at": dt.date.today().isoformat(),
                    "holdings": holdings,
                },
            },
        },
    }

    save_registry(registry, path)

    stored = json.loads(path.read_text(encoding="utf-8"))
    assert "holdings" not in stored["indices"]["TEST-INDEX"]["composition"]
    assert stored["indices"]["TEST-INDEX"]["composition"]["holdings_count"] == 30
    fragments = list((tmp_path / "indices_compositions").glob("*.json.gz"))
    assert len(fragments) == 2
    assert len(cached_index_composition("TEST-INDEX", path=path)["holdings"]) == 30
    assert len(cached_fund_composition("ISIN:IE0000000001", path=path)["holdings"]) == 30


def test_index_mapping_is_cached_once_by_isin_and_shared_between_listings(tmp_path):
    path = tmp_path / "indices.json"
    broker = pd.DataFrame([
        {
            "Ticker Yahoo Finance": "WORLD.PA",
            "ISIN": "IE00B4L5Y983",
            "Nom": "Amundi MSCI World UCITS ETF Acc",
            "Indice": "MSCI World Net Total Return EUR",
            "Réplication": "Synthétique",
        },
        {
            "Ticker Yahoo Finance": "WORLD.DE",
            "ISIN": "IE00B4L5Y983",
            "Nom": "Amundi MSCI World UCITS ETF Acc",
            "Indice": "",
            "Réplication": "Synthétique",
        },
    ])

    first = resolve_index_registry(
        ["WORLD.PA"], broker_table=broker, path=path
    )
    second = resolve_index_registry(
        ["WORLD.DE"], broker_table=broker, path=path
    )

    assert first["WORLD.PA"]["index_id"] == second["WORLD.DE"]["index_id"]
    assert second["WORLD.DE"]["source"] == "catalog_explicit"
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert list(stored["funds"]) == ["ISIN:IE00B4L5Y983"]
    assert stored["funds"]["ISIN:IE00B4L5Y983"]["tickers"] == [
        "WORLD.DE", "WORLD.PA",
    ]


def test_manual_reference_repairs_wrong_catalog_isin_and_old_cache_alias(tmp_path):
    path = tmp_path / "indices.json"
    path.write_text(json.dumps({
        "version": 1,
        "funds": {
            "ISIN:FR0010315770": {
                "isin": "FR0010315770", "tickers": ["CW8.PA"],
                "name": "World", "index_id": "MSCI-WORLD-NETTOTAL-RETURN-INDEX",
                "index_name": "MSCI World NetTotal Return Index",
                "replication": "synthetic", "source": "issuer_factsheet",
                "confidence": "high", "verified_at": "2026-08-21",
            },
        },
        "indices": {},
    }), encoding="utf-8")
    broker = pd.DataFrame([{
        "Ticker Yahoo Finance": "CW8.PA", "ISIN": "FR0010315770",
        "Nom": "World", "Indice": "MSCI World", "Réplication": "Inconnue",
    }])

    result = resolve_index_registry(["CW8.PA"], broker_table=broker, path=path)

    assert result["CW8.PA"]["isin"] == "LU1681043599"
    assert result["CW8.PA"]["index_name"] == "MSCI World Index"
    assert result["CW8.PA"]["replication"] == "synthetic"
    assert result["CW8.PA"]["source"] == "manual_reference"
    assert result["CW8.PA"]["catalog_isin_conflict"] == "FR0010315770"
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["funds"]["ISIN:FR0010315770"]["tickers"] == []
    assert stored["funds"]["ISIN:LU1681043599"]["tickers"] == ["CW8.PA"]


def test_manual_reference_prevents_emb_ucits_identity_conflation(tmp_path):
    broker = pd.DataFrame([{
        "Ticker Yahoo Finance": "EMB",
        "ISIN": "IE00B2NPKV68",
        "Nom": "Wrong UCITS listing attached to EMB",
        "Indice": "",
        "Réplication": "",
    }])

    result = resolve_index_registry(
        ["EMB"], broker_table=broker, path=tmp_path / "indices.json",
    )["EMB"]

    assert result["isin"] == "US4642882819"
    assert result["asset_class"] == "fixed_income"
    assert result["index_name"] == "J.P. Morgan EMBI Global Core Index"
    assert result["catalog_isin_conflict"] == "IE00B2NPKV68"


def test_resolving_mapping_preserves_official_fund_composition(tmp_path):
    path = tmp_path / "indices.json"
    composition = {
        "source": "issuer_fund_holdings", "updated_at": "2026-08-21",
        "coverage": 0.995, "partial": False,
        "holdings": [{"ticker": "BBVA.MC", "weight": 0.995}],
    }
    path.write_text(json.dumps({
        "version": 1,
        "funds": {
            "ISIN:DE0006289309": {
                "isin": "DE0006289309", "tickers": ["EXX1.DE"],
                "name": "iShares EURO STOXX Banks ETF",
                "index_id": "EURO-STOXX-BANKS", "index_name": "EURO STOXX Banks",
                "replication": "physical", "source": "issuer_product_api",
                "confidence": "high", "verified_at": "2026-08-21",
                "composition": composition,
                "official_enrichment": {"status": "complete", "coverage": 0.995},
                "product_id": "251784",
            },
        },
        "indices": {},
    }), encoding="utf-8")
    broker = pd.DataFrame([{
        "Ticker Yahoo Finance": "EXX1.DE", "ISIN": "DE0006289309",
        "Nom": "iShares EURO STOXX Banks ETF",
        "Indice": "EURO STOXX Banks", "Réplication": "Physique",
    }])

    resolve_index_registry(["EXX1.DE"], broker_table=broker, path=path)
    stored = json.loads(path.read_text(encoding="utf-8"))["funds"]["ISIN:DE0006289309"]

    assert stored["composition"] == composition
    assert stored["official_enrichment"]["status"] == "complete"
    assert stored["product_id"] == "251784"


def test_name_inference_is_conservative_and_preserves_index_variants():
    assert infer_index_from_fund_name(
        "Xtrackers Euro Stoxx Quality Dividend UCITS ETF"
    ) == "Euro Stoxx Quality Dividend"
    assert infer_index_from_fund_name("Amundi PEA Japon (TOPIX) UCITS ETF EUR Acc") == "TOPIX"
    assert infer_index_from_fund_name(
        "Amundi Index Solutions - Amundi MSCI World Swap UCITS ETF EUR Acc"
    ) == "MSCI World"
    assert canonical_index_id(
        infer_index_from_fund_name("Amundi TOPIX UCITS ETF EUR Hedged Acc")
    ) != canonical_index_id(
        infer_index_from_fund_name("Amundi TOPIX UCITS ETF EUR Acc")
    )
    assert infer_index_from_fund_name("Generic Water UCITS ETF") == ""
    assert canonical_index_id("MSCI World ESG Screened") != canonical_index_id("MSCI World")


def test_topix_aliases_share_one_canonical_index_and_migrate_registry(tmp_path):
    assert canonical_index_id("TOPIX-INDEX") == "TOPIX"
    path = tmp_path / "indices.json"
    path.write_text(json.dumps({
        "version": 1,
        "funds": {"ISIN:JP0000000001": {"index_id": "TOPIX-INDEX"}},
        "indices": {
            "TOPIX": {"name": "TOPIX", "funds": ["A"]},
            "TOPIX-INDEX": {"name": "TOPIX-INDEX", "funds": ["B"]},
        },
    }), encoding="utf-8")

    from app.services.finance.buffett.etf_index_registry import load_registry

    registry = load_registry(path)

    assert list(registry["indices"]) == ["TOPIX"]
    assert registry["indices"]["TOPIX"]["funds"] == ["A", "B"]
    assert registry["funds"]["ISIN:JP0000000001"]["index_id"] == "TOPIX"


def test_replication_name_inference_uses_only_explicit_markers(tmp_path):
    assert infer_replication_from_fund_name("Amundi MSCI World Swap UCITS ETF") == "synthetic"
    assert infer_replication_from_fund_name("Example Physically Replicated ETF") == "physical"
    assert infer_replication_from_fund_name("Generic MSCI World UCITS ETF") == "unknown"

    broker = pd.DataFrame([{
        "Ticker Yahoo Finance": "SWAP.PA",
        "ISIN": "FR0000000001",
        "Nom": "Amundi S&P 500 Swap UCITS ETF",
        "Indice": "S&P 500",
        "Réplication": "",
    }])
    result = resolve_index_registry(
        ["SWAP.PA"], broker_table=broker, path=tmp_path / "indices.json",
    )
    assert result["SWAP.PA"]["replication"] == "synthetic"


def test_isin_checksum_rejects_well_formed_but_invalid_values():
    assert valid_isin("IE00B4L5Y983") == "IE00B4L5Y983"
    assert valid_isin("US0378331005") == "US0378331005"
    assert valid_isin("IE00B4L5Y984") == ""
    assert valid_isin("not-an-isin") == ""


def test_cusip_to_isin_derives_us_isin_with_luhn_check_digit():
    assert cusip_to_isin("78462F103") == "US78462F1030"  # SPY
    assert cusip_to_isin("922908769") == "US9229087690"  # VTI
    assert cusip_to_isin("464287200") == "US4642872000"  # IVV
    assert cusip_to_isin("46090E103") == "US46090E1038"  # QQQ
    assert cusip_to_isin("00214Q104") == "US00214Q1040"  # ARKK
    assert cusip_to_isin("037833100") == "US0378331005"  # AAPL
    # CUSIP malformé -> aucune reconstitution (jamais de valeur inventée)
    assert cusip_to_isin("78462F10") == ""
    assert cusip_to_isin("not-a-cusip") == ""


def test_missing_catalog_isin_is_recovered_from_trading212(tmp_path, monkeypatch):
    from app.services.finance.buffett.config import Config

    variables = tmp_path / "variables"
    variables.mkdir()
    tickers_csv = variables / "tickers.csv"
    tickers_csv.write_text("ETF.L;Example;LSE;ETF\n", encoding="utf-8")
    (variables / "trading212_instruments.json").write_text(json.dumps([{
        "ticker": "ETFl_EQ",
        "shortName": "ETF",
        "isin": "IE00B4L5Y983",
    }]), encoding="utf-8")
    monkeypatch.setattr(Config, "TICKERS_CSV", str(tickers_csv))
    broker = pd.DataFrame([{
        "Ticker Yahoo Finance": "ETF.L",
        "ISIN": "",
        "Nom": "Example ETF",
        "Tradding 212": 1,
        "Bourse Direct 2": 0,
    }])

    result = resolve_index_registry(
        ["ETF.L"], broker_table=broker, path=tmp_path / "indices.json",
    )["ETF.L"]

    assert result["isin"] == "IE00B4L5Y983"
    assert result["isin_source"] == "trading212_api"
    assert result["identity_key"] == "ISIN:IE00B4L5Y983"


def test_local_broker_isin_does_not_require_availability_flag(tmp_path, monkeypatch):
    from app.services.finance.buffett.config import Config

    variables = tmp_path / "variables"
    variables.mkdir()
    tickers_csv = variables / "tickers.csv"
    tickers_csv.write_text("WOSC.L;Example;LSE;ETF\n", encoding="utf-8")
    (variables / "trading212_instruments.json").write_text(json.dumps([{
        "type": "ETF", "shortName": "WOSC", "isin": "IE00BCBJG560",
    }]), encoding="utf-8")
    monkeypatch.setattr(Config, "TICKERS_CSV", str(tickers_csv))
    broker = pd.DataFrame([{
        "Ticker Yahoo Finance": "WOSC.L",
        "ISIN": "",
        "Nom": "SPDR MSCI World Small Cap UCITS ETF",
        "Tradding 212": 0,
    }])

    result = resolve_index_registry(
        ["WOSC.L"], broker_table=broker, path=tmp_path / "indices.json",
    )["WOSC.L"]

    assert result["isin"] == "IE00BCBJG560"
    assert result["isin_source"] == "trading212_api"


def test_invalid_catalog_isin_is_replaced_by_local_broker_source(tmp_path, monkeypatch):
    from app.services.finance.buffett.config import Config

    variables = tmp_path / "variables"
    variables.mkdir()
    tickers_csv = variables / "tickers.csv"
    tickers_csv.write_text("ETF.L;Example;LSE;ETF\n", encoding="utf-8")
    (variables / "trading212_instruments.json").write_text(json.dumps([{
        "shortName": "ETF", "isin": "IE00B4L5Y983",
    }]), encoding="utf-8")
    monkeypatch.setattr(Config, "TICKERS_CSV", str(tickers_csv))
    broker = pd.DataFrame([{
        "Ticker Yahoo Finance": "ETF.L",
        "ISIN": "IE00B4L5Y984",
        "Nom": "Example ETF",
        "Tradding 212": 1,
    }])

    result = resolve_index_registry(
        ["ETF.L"], broker_table=broker, path=tmp_path / "indices.json",
    )["ETF.L"]

    assert result["isin"] == "IE00B4L5Y983"
    assert result["invalid_catalog_isin"] == "IE00B4L5Y984"


def test_trading212_isin_resolves_with_exchange_suffix_present(tmp_path, monkeypatch):
    from app.services.finance.buffett.config import Config

    variables = tmp_path / "variables"
    variables.mkdir()
    tickers_csv = variables / "tickers.csv"
    tickers_csv.write_text("CSPX.L;Example;LSE;ETF\n", encoding="utf-8")
    # En production `trading212_exchanges.json` existe : `_local_broker_isins`
    # indexe alors la map par le symbole Yahoo COMPLET ("CSPX.L"), pas le court
    # nom. La résolution doit donc interroger le ticker complet, pas "CSPX".
    (variables / "trading212_exchanges.json").write_text(json.dumps([{
        "name": "London Stock Exchange",
        "workingSchedules": [{"id": 123}],
    }]), encoding="utf-8")
    (variables / "trading212_instruments.json").write_text(json.dumps([{
        "ticker": "CSPXl_EQ",
        "shortName": "CSPX",
        "isin": "IE00B5BMR087",
        "workingScheduleId": 123,
    }]), encoding="utf-8")
    monkeypatch.setattr(Config, "TICKERS_CSV", str(tickers_csv))
    broker = pd.DataFrame([{
        "Ticker Yahoo Finance": "CSPX.L",
        "ISIN": "",
        "Nom": "iShares Core S&P 500 UCITS ETF",
        "Tradding 212": 1,
    }])

    result = resolve_index_registry(
        ["CSPX.L"], broker_table=broker, path=tmp_path / "indices.json",
    )["CSPX.L"]

    assert result["isin"] == "IE00B5BMR087"
    assert result["isin_source"] == "trading212_api"


def test_index_composition_is_shared_only_with_same_official_provider_id(tmp_path):
    path = tmp_path / "indices.json"
    path.write_text(json.dumps({
        "version": 1,
        "funds": {},
        "indices": {
                "CAC-40-NET-TR-IN-EUR-EUR": {
                    "name": "CAC 40 Net TR in EUR (EUR)",
                    "provider": "euronext",
                    "provider_index_id": "CAC40-BASKET",
                "funds": [],
                "composition": {
                    "source": "official_index_constituents",
                    "updated_at": dt.date.today().isoformat(),
                    "holdings": [{"ticker": "AIR.PA", "weight": 1.0}],
                },
            },
                "CAC-40": {
                    "name": "CAC 40", "funds": [],
                    "provider": "euronext",
                    "provider_index_id": "CAC40-BASKET",
                },
                "CAC-40-ESG": {
                    "name": "CAC 40 ESG", "funds": [],
                    "provider": "euronext",
                    "provider_index_id": "CAC40-ESG-BASKET",
                },
        },
    }), encoding="utf-8")

    assert cached_index_composition("CAC-40", path=path)["holdings"][0]["ticker"] == "AIR.PA"
    assert cached_index_composition("CAC-40-ESG", path=path) is None


def test_index_groups_merge_return_labels_but_not_esg_or_hedged_variants():
    groups = index_groups({
        "CW8.PA": {
            "index_id": "MSCI-WORLD-NETTOTAL-RETURN-INDEX",
            "index_name": "MSCI World NetTotal Return Index",
            "confidence": "high",
        },
        "EUNL.DE": {
            "index_id": "MSCI-WORLD-INDEX-NET",
            "index_name": "MSCI World Index (Net",
            "confidence": "high",
        },
        "ESG.DE": {
            "index_id": "MSCI-WORLD-ESG",
            "index_name": "MSCI World ESG Screened",
            "confidence": "high",
        },
        "HEDGED.PA": {
            "index_id": "MSCI-WORLD-EUR-HEDGED",
            "index_name": "MSCI World EUR Hedged",
            "confidence": "high",
        },
    })

    assert groups["MSCI-WORLD"] == ["CW8.PA", "EUNL.DE"]
    assert groups["MSCI-WORLD-ESG-SCREENED"] == ["ESG.DE"]
    assert groups["MSCI-WORLD-EUR-HEDGED"] == ["HEDGED.PA"]


def test_physical_proxy_matches_only_the_same_canonical_index_basket(tmp_path):
    path = tmp_path / "indices.json"
    path.write_text(json.dumps({
        "version": 1,
        "funds": {
            "ISIN:IE0000000001": {
                "isin": "IE0000000001", "tickers": ["PHYS.DE"],
                "index_id": "MSCI-WORLD-NET", "index_name": "MSCI World Index (Net",
                "replication": "physical",
                "composition": {
                    "source": "issuer_fund_holdings", "updated_at": "2026-08-21",
                    "coverage": 0.97,
                    "holdings": [{"ticker": "NVDA", "weight": 0.97}],
                },
            },
            "ISIN:IE0000000002": {
                "isin": "IE0000000002", "tickers": ["ESG.DE"],
                "index_id": "MSCI-WORLD-ESG", "index_name": "MSCI World ESG",
                "replication": "physical",
                "composition": {
                    "source": "issuer_fund_holdings", "updated_at": "2026-08-21",
                    "coverage": 1.0,
                    "holdings": [{"ticker": "OTHER", "weight": 1.0}],
                },
            },
        },
        "indices": {
            "MSCI-WORLD": {"name": "MSCI World", "funds": []},
            "MSCI-WORLD-NET": {"name": "MSCI World Index (Net", "funds": []},
            "MSCI-WORLD-ESG": {"name": "MSCI World ESG", "funds": []},
        },
    }), encoding="utf-8")

    result = cached_physical_index_proxy("MSCI-WORLD", path=path)

    assert result is not None
    assert result["source"] == "physical_tracker_proxy"
    assert result["proxy_ticker"] == "PHYS.DE"
    assert result["proxy_isin"] == "IE0000000001"
    assert result["holdings"] == [{"ticker": "NVDA", "weight": 0.97}]


def test_physical_proxy_accepts_unknown_replication_with_issuer_holdings(tmp_path):
    """Un tracker dont la réplication est encore ``unknown`` mais qui a publié
    des positions ``issuer_fund_holdings`` est physique par preuve et peut
    servir de jumeau pour un synthétique du même indice sous licence."""
    path = tmp_path / "indices.json"
    path.write_text(json.dumps({
        "version": 1,
        "funds": {
            "ISIN:IE0000000001": {
                "isin": "IE0000000001", "tickers": ["UNKN.DE"],
                "index_id": "MSCI-WORLD-NET", "index_name": "MSCI World Index (Net",
                "replication": "unknown",
                "composition": {
                    "source": "issuer_fund_holdings",
                    "updated_at": dt.date.today().isoformat(),
                    "coverage": 0.97,
                    "holdings": [{"ticker": "NVDA", "weight": 0.97}],
                },
            },
        },
        "indices": {
            "MSCI-WORLD": {"name": "MSCI World", "funds": []},
            "MSCI-WORLD-NET": {"name": "MSCI World Index (Net", "funds": []},
        },
    }), encoding="utf-8")

    result = cached_physical_index_proxy("MSCI-WORLD", path=path)

    assert result is not None
    assert result["source"] == "physical_tracker_proxy"
    assert result["proxy_ticker"] == "UNKN.DE"
    assert result["proxy_isin"] == "IE0000000001"


def test_physical_proxy_rejects_declared_synthetic_even_with_holdings(tmp_path):
    """Un fonds déclaré synthétique ne sert jamais de jumeau, même si son
    panier était à tort libellé ``issuer_fund_holdings`` (collatéral)."""
    path = tmp_path / "indices.json"
    path.write_text(json.dumps({
        "version": 1,
        "funds": {
            "ISIN:IE0000000001": {
                "isin": "IE0000000001", "tickers": ["SYN.DE"],
                "index_id": "MSCI-WORLD-NET", "index_name": "MSCI World Index (Net",
                "replication": "synthetic",
                "composition": {
                    "source": "issuer_fund_holdings",
                    "updated_at": dt.date.today().isoformat(),
                    "coverage": 0.97,
                    "holdings": [{"ticker": "NVDA", "weight": 0.97}],
                },
            },
        },
        "indices": {
            "MSCI-WORLD": {"name": "MSCI World", "funds": []},
            "MSCI-WORLD-NET": {"name": "MSCI World Index (Net", "funds": []},
        },
    }), encoding="utf-8")

    result = cached_physical_index_proxy("MSCI-WORLD", path=path)

    assert result is None


def test_workbook_lists_proxy_and_unresolved_synthetic_indices(tmp_path):
    from app.services.finance.buffett.etf_index_registry import registry_workbook_frames

    registry = {
        "_storage_path": str(tmp_path / "indices.json"),
        "version": 2,
        "funds": {
            "SYN1": {
                "tickers": ["SYN1.PA"], "index_id": "MSCI-WORLD",
                "index_name": "MSCI World", "replication": "synthetic",
            },
            "SYN2": {
                "tickers": ["SYN2.PA"], "index_id": "MISSING-INDEX",
                "index_name": "Missing Index", "replication": "synthetic",
            },
            "PHYS": {
                "isin": "IE0000000001", "tickers": ["PHYS.DE"],
                "index_id": "MSCI-WORLD-NET", "index_name": "MSCI World Index (Net",
                "replication": "physical",
                "composition": {
                    "source": "issuer_fund_holdings", "updated_at": "2026-08-21",
                    "coverage": 0.97,
                    "source_url": "https://issuer.example/holdings",
                    "holdings": [{"ticker": "NVDA", "weight": 0.97}],
                },
            },
        },
        "indices": {
            "MSCI-WORLD": {"name": "MSCI World", "funds": ["SYN1"]},
            "MSCI-WORLD-NET": {"name": "MSCI World Index (Net", "funds": ["PHYS"]},
            "MISSING-INDEX": {
                "name": "Missing Index", "funds": ["SYN2"],
                "official_enrichment": {
                    "status": "licence_required", "error": "licence requise",
                },
            },
        },
    }

    funds, constituents = registry_workbook_frames(registry)
    proxy = constituents[constituents["Indice_ID"] == "MSCI-WORLD"].iloc[0]
    unresolved = constituents[constituents["Indice_ID"] == "MISSING-INDEX"].iloc[0]

    assert bool(funds.loc[funds["Ticker"] == "SYN1.PA", "Proxy_Physique"].iloc[0])
    assert proxy["Type_Composition"] == "PROXY_PHYSIQUE"
    assert proxy["Proxy_Ticker"] == "PHYS.DE"
    assert proxy["Ticker"] == "NVDA"
    assert unresolved["Type_Composition"] == "NON_RESOLU"
    assert unresolved["Statut_Composition"] == "licence_required"
    assert unresolved["Ticker"] == ""
    assert unresolved["Erreur"] == "licence requise"


def test_exact_index_dedup_chooses_lowest_fee_for_each_broker(tmp_path, monkeypatch):
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.dedup import deduplicate_same_index

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"X": 1000.0, "Y": 1000.0})
    returns = pd.DataFrame({
        "A.PA": [0.01, -0.01, 0.02],
        "B.DE": [0.03, 0.01, -0.02],  # corrélation sans importance ici
        "D.PA": [0.02, -0.02, 0.01],
        "C.L": [-0.02, 0.04, 0.01],
    })
    metadata = pd.DataFrame([
        {"Ticker Yahoo Finance": "A.PA", "Secteur 1": "ETF", "Nom": "A", "Indice": "MSCI World", "TER": "0.30%", "Volume": 10000, "X": True, "Y": True},
        {"Ticker Yahoo Finance": "B.DE", "Secteur 1": "ETF", "Nom": "B", "Indice": "MSCI World", "TER": "0.10%", "Volume": 10, "X": True, "Y": False},
        {"Ticker Yahoo Finance": "D.PA", "Secteur 1": "ETF", "Nom": "D", "Indice": "MSCI World", "TER": "0.20%", "Volume": 20, "X": False, "Y": True},
        {"Ticker Yahoo Finance": "C.L", "Secteur 1": "ETF", "Nom": "C", "Indice": "MSCI World ESG", "TER": "0.40%", "Volume": 999, "X": True, "Y": True},
    ])
    optimizer_rows = pd.DataFrame({
        "Ticker Yahoo Finance": ["A.PA", "B.DE", "D.PA", "C.L"],
        "Secteur": ["ETF", "ETF", "ETF", "ETF"],
        "Volume": [10000, 10, 20, 999],
        "X": [True, True, False, True],
        "Y": [True, False, True, True],
    })

    result = deduplicate_same_index(
        returns,
        optimizer_rows,
        broker_table=metadata,
        registry_path=tmp_path / "indices.json",
    )

    # Le très liquide A perd : B est le moins cher chez X, D chez Y. La variante
    # ESG est un autre indice économique et reste disponible.
    assert list(result.columns) == ["B.DE", "D.PA", "C.L"]


def test_same_low_cost_fund_can_win_both_broker_slots(tmp_path, monkeypatch):
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.dedup import deduplicate_same_index

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"X": 1.0, "Y": 1.0})
    returns = pd.DataFrame({"CHEAP": [0.01, 0.02], "EXPENSIVE": [0.01, 0.02]})
    metadata = pd.DataFrame([
        {"Ticker Yahoo Finance": "CHEAP", "Secteur 1": "ETF", "Nom": "Cheap MSCI World", "Indice": "MSCI World", "TER": "0.12%", "X": True, "Y": True},
        {"Ticker Yahoo Finance": "EXPENSIVE", "Secteur 1": "ETF", "Nom": "Expensive MSCI World", "Indice": "MSCI World", "TER": "0.30%", "X": True, "Y": True},
    ])
    optimizer_rows = metadata.rename(columns={"Secteur 1": "Secteur"}).copy()
    optimizer_rows["Volume"] = [1, 10000]

    result = deduplicate_same_index(
        returns, optimizer_rows, broker_table=metadata,
        registry_path=tmp_path / "indices.json",
    )

    assert list(result.columns) == ["CHEAP"]


def test_workbook_tables_store_mapping_and_index_constituents_without_etf_risk_fields():
    registry = {
        "funds": {
            "ISIN:IE0000000001": {
                "isin": "IE0000000001", "tickers": ["WORLD.PA"],
                "name": "World", "index_id": "MSCI-WORLD",
                "index_name": "MSCI World", "replication": "synthetic",
                "source": "issuer_factsheet", "confidence": "high",
                "verified_at": "2026-08-21",
            },
        },
        "indices": {
            "MSCI-WORLD": {
                "name": "MSCI World", "funds": ["IE0000000001"],
                "composition": {
                    "source": "official_index_constituents",
                    "updated_at": "2026-08-21",
                    "holdings": [{
                        "ticker": "NVDA", "name": "NVIDIA", "weight": 0.08,
                        "country": "United States", "sector": "Technology",
                    }],
                },
            },
        },
    }

    funds, constituents = registry_workbook_frames(registry)

    assert funds.loc[0, "Indice"] == "MSCI World"
    assert funds.loc[0, "Statut_Composition"] == "complete_shared_index"
    assert funds.loc[0, "Couverture_pct"] == 8.0
    assert "Pays" not in funds.columns
    assert "Defensif_pct" not in funds.columns
    assert constituents.loc[0, "Ticker"] == "NVDA"
    assert constituents.loc[0, "Poids_pct"] == 8.0
    assert constituents.loc[0, "Pays"] == "United States"


def test_workbook_mapping_prefers_resolved_isin_over_stale_ticker_identity():
    registry = {
        "funds": {
            "TICKER:CU2.PA": {
                "tickers": ["CU2.PA"], "name": "Old unresolved record",
                "index_id": "MSCI-USA-ESG-SELECTION", "replication": "unknown",
            },
            "ISIN:LU1681042864": {
                "isin": "LU1681042864", "tickers": ["CU2.PA"],
                "name": "Amundi PEA MSCI USA ESG Selection",
                "index_id": "MSCI-USA-ESG-SELECTION-P-SERIES-5-ISSUER-CAPPED-INDEX",
                "index_name": "MSCI USA ESG Selection P-Series 5% Issuer Capped Index",
                "replication": "synthetic",
            },
        },
        "indices": {},
    }

    funds, _ = registry_workbook_frames(registry)

    assert funds["Ticker"].tolist() == ["CU2.PA"]
    assert funds.loc[0, "ISIN"] == "LU1681042864"
    assert funds.loc[0, "Identite"] == "ISIN:LU1681042864"


def test_registry_is_published_as_two_dedicated_workbook_sheets(tmp_path):
    workbook = tmp_path / "ToutBroker.xlsx"
    registry_path = tmp_path / "indices.json"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame([{"Ticker Yahoo Finance": "WORLD.PA"}]).to_excel(
            writer, index=False,
        )
        pd.DataFrame([{"Ticker": "WORLD.PA", "France": 100}]).to_excel(
            writer, sheet_name="ETF_Pays", index=False,
        )
        pd.DataFrame([{"Ticker": "WORLD.PA", "Defensif_pct": 100}]).to_excel(
            writer, sheet_name="ETF_Defensif", index=False,
        )
    registry_path.write_text(json.dumps({
        "version": 1,
        "funds": {
            "ISIN:IE0000000001": {
                "isin": "IE0000000001", "tickers": ["WORLD.PA"],
                "name": "World", "index_id": "MSCI-WORLD",
                "index_name": "MSCI World", "source": "issuer_factsheet",
            },
        },
        "indices": {
            "MSCI-WORLD": {
                "name": "MSCI World", "funds": ["IE0000000001"],
                "composition": {
                    "source": "official_index_constituents",
                    "updated_at": "2026-08-21",
                    "holdings": [{"ticker": "A", "weight": 1.0}],
                },
            },
        },
    }), encoding="utf-8")

    counts = sync_registry_to_broker_workbook(
        path=workbook, registry_path=registry_path,
    )

    assert counts == {
        "etf_indices": 1,
        "constituants": 1,
        "anciennes_feuilles_supprimees": 2,
    }
    sheets = set(pd.ExcelFile(workbook).sheet_names)
    assert sheets >= {
        "ETF_Indices", "Indices_Constituants",
    }
    assert not {"ETF_Pays", "ETF_Defensif"} & sheets


def test_registry_isins_fill_invalid_cells_and_preserve_unverified_conflicts(tmp_path):
    from app.services.finance.buffett.etf_index_registry import (
        sync_registry_isins_to_broker_workbook,
    )

    workbook = tmp_path / "ToutBroker.xlsx"
    registry_path = tmp_path / "indices.json"
    table = pd.DataFrame([
        {"Ticker Yahoo Finance": "FILL.L", "ISIN": "", "Secteur 1": "ETF"},
        {"Ticker Yahoo Finance": "BAD.L", "ISIN": "IE00B4L5Y984", "Secteur 1": "ETF"},
        {"Ticker Yahoo Finance": "KEEP.L", "ISIN": "US0378331005", "Secteur 1": "ETF"},
        {"Ticker Yahoo Finance": "ACTION", "ISIN": "", "Secteur 1": "Action"},
    ])
    table.to_excel(workbook, index=False)
    registry_path.write_text(json.dumps({
        "version": 2,
        "funds": {
            "ISIN:IE00B4L5Y983": {
                "isin": "IE00B4L5Y983", "tickers": ["FILL.L", "BAD.L"],
            },
            "ISIN:US5949181045": {
                "isin": "US5949181045", "tickers": ["KEEP.L"],
            },
        },
        "indices": {},
    }), encoding="utf-8")

    diagnostics = sync_registry_isins_to_broker_workbook(
        table, path=registry_path, workbook_path=workbook,
    )
    written = pd.read_excel(workbook, keep_default_na=False)

    assert written.loc[0, "ISIN"] == "IE00B4L5Y983"
    assert written.loc[1, "ISIN"] == "IE00B4L5Y983"
    assert written.loc[2, "ISIN"] == "US0378331005"
    assert diagnostics["filled"] == 1
    assert diagnostics["invalid"] == 1
    assert diagnostics["conflicts"][0]["ticker"] == "KEEP.L"


def test_ticker_embedded_isin_resolves_fund_without_catalog_isin(tmp_path, monkeypatch):
    from app.services.finance.buffett.config import Config

    variables = tmp_path / "variables"
    variables.mkdir()
    tickers_csv = variables / "tickers.csv"
    tickers_csv.write_text("IE00BN4Q1675.SG;Example;SGX;ETF\n", encoding="utf-8")
    monkeypatch.setattr(Config, "TICKERS_CSV", str(tickers_csv))
    broker = pd.DataFrame([{
        "Ticker Yahoo Finance": "IE00BN4Q1675.SG",
        "ISIN": "",
        "Nom": "iShares MSCI World ETF",
    }])

    result = resolve_index_registry(
        ["IE00BN4Q1675.SG"], broker_table=broker, path=tmp_path / "indices.json",
    )["IE00BN4Q1675.SG"]

    assert result["isin"] == "IE00BN4Q1675"
    assert result["isin_source"] == "ticker_embedded_isin"


def test_us_cusip_isin_overrides_wrong_catalog_isin_for_bare_us_ticker(tmp_path, monkeypatch):
    from app.services.finance.buffett.config import Config

    variables = tmp_path / "variables"
    variables.mkdir()
    tickers_csv = variables / "tickers.csv"
    tickers_csv.write_text("SPY;Example;NYSE;ETF\n", encoding="utf-8")
    # Source US importée : SPY -> ISIN dérivé de son CUSIP (78462F103).
    (variables / "us_etf_isins.json").write_text(json.dumps({
        "SPY": "US78462F1030",
    }), encoding="utf-8")
    monkeypatch.setattr(Config, "TICKERS_CSV", str(tickers_csv))
    broker = pd.DataFrame([{
        "Ticker Yahoo Finance": "SPY",
        # Collision cross-marché : le catalogue a associé SPY à un fonds UCITS.
        "ISIN": "IE00B6YX5C33",
        "Nom": "SPDR S&P 500 ETF Trust",
    }])

    result = resolve_index_registry(
        ["SPY"], broker_table=broker, path=tmp_path / "indices.json",
    )["SPY"]

    assert result["isin"] == "US78462F1030"
    assert result["isin_source"] == "us_cusip"
    assert result["isin_conflicts"]["catalog"] == "IE00B6YX5C33"


def test_us_cusip_isin_does_not_override_valid_us_catalog_isin(tmp_path, monkeypatch):
    from app.services.finance.buffett.config import Config

    variables = tmp_path / "variables"
    variables.mkdir()
    tickers_csv = variables / "tickers.csv"
    tickers_csv.write_text("SQQQ;Example;NASDAQ;ETF\n", encoding="utf-8")
    # La source bulk propose un ISIN US erroné pour SQQQ ; le catalogue en porte
    # un autre, correct (confirmé par yfinance : US74350P6759). L'ISIN US dérivé
    # de CUSIP ne doit donc PAS écraser un ISIN US déjà valide du catalogue.
    (variables / "us_etf_isins.json").write_text(json.dumps({
        "SQQQ": "US74347G1922",
    }), encoding="utf-8")
    monkeypatch.setattr(Config, "TICKERS_CSV", str(tickers_csv))
    broker = pd.DataFrame([{
        "Ticker Yahoo Finance": "SQQQ",
        "ISIN": "US74350P6759",
        "Nom": "ProShares UltraPro Short QQQ",
    }])

    result = resolve_index_registry(
        ["SQQQ"], broker_table=broker, path=tmp_path / "indices.json",
    )["SQQQ"]

    assert result["isin"] == "US74350P6759"
    assert result["isin_source"] == "broker_catalog"


def test_us_catalog_isin_purges_stale_non_us_record(tmp_path, monkeypatch):
    from app.services.finance.buffett.config import Config

    variables = tmp_path / "variables"
    variables.mkdir()
    tickers_csv = variables / "tickers.csv"
    tickers_csv.write_text("GDX;Example;NYSE;ETF\n", encoding="utf-8")
    (variables / "us_etf_isins.json").write_text(json.dumps({
        "GDX": "US92189F1066",
    }), encoding="utf-8")
    monkeypatch.setattr(Config, "TICKERS_CSV", str(tickers_csv))
    broker = pd.DataFrame([{
        "Ticker Yahoo Finance": "GDX",
        # Le catalogue a déjà été corrigé en ISIN US (idem IAU, SQQQ).
        "ISIN": "US92189F1066",
        "Nom": "VanEck Gold Miners ETF",
    }])
    # Un ancien enregistrement non-US erroné référence encore GDX.
    path = tmp_path / "indices.json"
    path.write_text(json.dumps({
        "version": 1,
        "funds": {
            "ISIN:IE00BQQP9F84": {
                "isin": "IE00BQQP9F84", "tickers": ["GDX"],
            },
        },
        "indices": {},
    }), encoding="utf-8")

    result = resolve_index_registry(["GDX"], broker_table=broker, path=path)["GDX"]

    assert result["isin"] == "US92189F1066"
    assert result["isin_source"] == "broker_catalog"
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["funds"]["ISIN:US92189F1066"]["tickers"] == ["GDX"]
    assert stored["funds"]["ISIN:IE00BQQP9F84"]["tickers"] == []


def test_us_cusip_isin_does_not_leak_to_european_homonym(tmp_path, monkeypatch):
    from app.services.finance.buffett.config import Config

    variables = tmp_path / "variables"
    variables.mkdir()
    tickers_csv = variables / "tickers.csv"
    tickers_csv.write_text("SPY.L;Example;LSE;ETF\n", encoding="utf-8")
    (variables / "us_etf_isins.json").write_text(json.dumps({
        "SPY": "US78462F1030",
    }), encoding="utf-8")
    monkeypatch.setattr(Config, "TICKERS_CSV", str(tickers_csv))
    broker = pd.DataFrame([{
        "Ticker Yahoo Finance": "SPY.L",
        "ISIN": "",
        "Nom": "SPDR S&P 500 UCITS ETF",
    }])

    result = resolve_index_registry(
        ["SPY.L"], broker_table=broker, path=tmp_path / "indices.json",
    )["SPY.L"]

    # Le court nom "SPY" existe dans la source US, mais "SPY.L" porte un suffixe
    # de place : il ne doit PAS hériter de l'ISIN US.
    assert result["isin"] == ""
    assert result["isin_source"] == ""
