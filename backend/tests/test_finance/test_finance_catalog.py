from types import SimpleNamespace

import pandas as pd
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.models.finance_catalog import (
    FinanceBroker,
    FinanceBrokerAvailability,
    FinanceIndex,
    FinanceInstrument,
    FinanceListing,
)


def test_unknown_broker_state_is_not_buyable():
    from app.services.finance.buffett.optimizer import _is_true

    assert _is_true(None) is False
    assert _is_true("UNKNOWN") is False
    assert _is_true("TRUE") is True


def test_group_download_supplies_etf_turnover_without_info_call():
    from app.services.finance.buffett.allocation import average_turnover_eur_from_download

    columns = pd.MultiIndex.from_product([["ETF.PA"], ["Close", "Volume"]])
    raw = pd.DataFrame([[10.0, 100.0], [20.0, 200.0]], columns=columns)
    assert average_turnover_eur_from_download(raw, ["ETF.PA"]) == {"ETF.PA": 2500.0}


def test_catalog_repository_exposes_explicit_tristate(monkeypatch):
    import app.core.db
    from app.services.finance.catalog.repository import catalog_dataframe

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(app.core.db, "engine", engine)
    with Session(engine) as session:
        instrument = FinanceInstrument(isin="US9219088443", name="VIG", instrument_type="ETF")
        session.add(instrument)
        session.commit()
        session.refresh(instrument)
        listing = FinanceListing(
            instrument_id=instrument.id, mic="ARCX", local_symbol="VIG", yahoo_symbol="VIG"
        )
        broker = FinanceBroker(code="TRADING212", label="Trading 212")
        session.add(listing)
        session.add(broker)
        session.commit()
        session.refresh(listing)
        session.refresh(broker)
        session.add(
            FinanceBrokerAvailability(listing_id=listing.id, broker_id=broker.id, state="TRUE")
        )
        session.commit()

    frame = catalog_dataframe()
    row = frame.iloc[0]
    assert row["ISIN"] == "US9219088443"
    assert row["Trading212"] == "TRUE"
    assert pd.isna(row["Trading212 URL"])
    assert row["BoursDirect2"] == "UNKNOWN"
    assert row["IBKR"] == "UNKNOWN"


def test_local_broker_sync_repairs_isin_links_and_index_metadata(tmp_path, monkeypatch):
    import json

    import app.core.db
    from app.services.finance.catalog.repository import (
        sync_local_broker_catalog_metadata,
    )

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(app.core.db, "engine", engine)
    with Session(engine) as session:
        instrument = FinanceInstrument(name="Ancien nom", instrument_type="UNKNOWN")
        broker = FinanceBroker(
            id=2, code="BOURSE_DIRECT_PEA", label="Bourse Direct PEA"
        )
        session.add(instrument)
        session.add(broker)
        session.commit()
        session.refresh(instrument)
        session.add(FinanceListing(
            instrument_id=instrument.id, mic="XPAR", local_symbol="PANX",
            yahoo_symbol="PANX.PA",
        ))
        session.commit()
        stale = FinanceInstrument(
            isin="FR0010000003", name="Ancien ETF", instrument_type="ETF"
        )
        session.add(stale)
        session.commit()
        session.refresh(stale)
        stale_listing = FinanceListing(
            instrument_id=stale.id, mic="XPAR", local_symbol="OLD",
            yahoo_symbol="OLD.PA",
        )
        session.add(stale_listing)
        session.commit()
        session.refresh(stale_listing)
        session.add(FinanceBrokerAvailability(
            listing_id=stale_listing.id, broker_id=broker.id, state="TRUE"
        ))
        session.commit()
        stale_listing_id = stale_listing.id

    bd = tmp_path / "boursedirect.json"
    bd.write_text(json.dumps({"instruments": [{
        "isin": "FR0013412269", "yahoo": "PANX.PA", "mic": "XPAR",
        "name": "Amundi PEA US Tech Screened UC", "slug": (
            "amundi-pea-us-tech-screened-uc-FR0013412269-PANX-EUR-XPAR"
        ),
    }]}), encoding="utf-8")
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({
        "funds": {"ISIN:FR0013412269": {
            "isin": "FR0013412269", "tickers": ["PANX.PA"],
            "index_name": "Solactive ISS ESG US Tech 100 Index",
            "index_id": "SOLACTIVE-ISS-ESG-US-TECH-100-INDEX",
            "replication": "synthetic",
            "official_enrichment": {
                "source_url": "https://issuer.example/PANX",
            },
        }},
        "indices": {"SOLACTIVE-ISS-ESG-US-TECH-100-INDEX": {
            "name": "Solactive ISS ESG US Tech 100 Index",
            "official_enrichment": {
                "provider": "solactive", "source_url": "https://index.example/PANX",
            },
        }},
    }), encoding="utf-8")

    stats = sync_local_broker_catalog_metadata(
        boursedirect_path=bd,
        trading212_path=tmp_path / "missing-t212.json",
        trading212_exchanges_path=tmp_path / "missing-exchanges.json",
        registry_path=registry,
    )

    assert stats["isin_filled"] == 1
    assert stats["availability_reset"] == 1
    assert stats["availability_upserted"] == 1
    with Session(engine) as session:
        instrument = session.exec(
            select(FinanceInstrument).where(FinanceInstrument.isin == "FR0013412269")
        ).one()
        listing = session.exec(
            select(FinanceListing).where(FinanceListing.yahoo_symbol == "PANX.PA")
        ).one()
        availability = session.exec(
            select(FinanceBrokerAvailability).where(
                FinanceBrokerAvailability.listing_id == listing.id
            )
        ).one()
        stale_availability = session.exec(
                select(FinanceBrokerAvailability).where(
                FinanceBrokerAvailability.listing_id == stale_listing_id
            )
        ).one()
        index = session.exec(select(FinanceIndex)).one()
    assert instrument.isin == "FR0013412269"
    assert instrument.instrument_type == "ETF"
    assert listing.metadata_json["Indice"] == "Solactive ISS ESG US Tech 100 Index"
    assert listing.metadata_json["Indice_Source_URL"] == "https://index.example/PANX"
    assert availability.state == "TRUE"
    assert stale_availability.state == "FALSE"
    assert availability.source_record_id.endswith("PANX-EUR-XPAR")
    assert availability.source_url.endswith("/seance")
    assert index.canonical_code == "SOLACTIVE-ISS-ESG-US-TECH-100-INDEX"
    assert index.source_url == "https://index.example/PANX"


def test_workbook_cleanup_and_streaming_migration(monkeypatch):
    import scripts.migrate_toutbroker_catalog as migration

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(migration, "engine", engine)
    source = pd.DataFrame(
        [
            {
                "Ticker Yahoo Finance": "VIG",
                "Nom": "Vanguard",
                "ISIN": "AT0000908504",
                "Secteur 1": "ETF",
                "Chance MOAT": 200,
                "Trading212": 1,
                "Bourse Direct 2": "",
            },
            {
                "Ticker Yahoo Finance": "VIG",
                "Nom": "Vanguard snapshot incomplet",
                "ISIN": None,
                "Secteur 1": "ETF",
            },
        ]
    )
    cleaned, audit = migration.clean_frame(source)
    assert audit["duplicate_listings_removed"] == 1
    assert cleaned.iloc[0]["ISIN"] == "US9219088443"
    assert pd.isna(cleaned.iloc[0]["Chance MOAT"])

    result = migration.migrate(cleaned)
    assert result["instruments"] == 1
    assert result["listings"] == 1
    with Session(engine) as session:
        states = session.exec(select(FinanceBrokerAvailability)).all()
        assert {(item.broker_id, item.state) for item in states} == {(1, "TRUE"), (2, "UNKNOWN")}


def test_export_cleanup_canonicalizes_topix_and_real_estate():
    from scripts.export_toutbroker_catalog import clean_extra_sheet

    constituents = pd.DataFrame(
        [
            {
                "Indice_ID": "TOPIX",
                "Indice": "TOPIX",
                "Identifiant_Fournisseur": "TOPIX",
                "Ticker": "7203.T",
                "ISIN": "JP3633400001",
            },
            {
                "Indice_ID": "TOPIX-INDEX",
                "Indice": "TOPIX-INDEX",
                "Identifiant_Fournisseur": "TOPIX-INDEX",
                "Ticker": "7203.T",
                "ISIN": "JP3633400001",
            },
        ]
    )
    cleaned_constituents = clean_extra_sheet("Indices_Constituants", constituents)
    assert len(cleaned_constituents) == 1
    assert cleaned_constituents.iloc[0]["Indice_ID"] == "TOPIX"
    assert cleaned_constituents.iloc[0]["Indice"] == "TOPIX"
    assert cleaned_constituents.iloc[0]["Identifiant_Fournisseur"] == "TOPIX"

    sectors = pd.DataFrame(
        [{"Ticker": "MSOS", "Immobilier": 0.0, "realestate": 50.18, "Couverture_pct": 0}]
    )
    cleaned_sectors = clean_extra_sheet("ETF_Secteurs", sectors)
    assert "realestate" not in cleaned_sectors.columns
    assert cleaned_sectors.iloc[0]["Immobilier"] == 50.18
    assert pd.isna(cleaned_sectors.iloc[0]["Couverture_pct"])


def test_analysis_observations_and_weights_are_written_to_catalog(monkeypatch):
    import app.core.db
    from app.services.finance.catalog.repository import (
        append_analysis_results,
        catalog_dataframe,
        update_target_weights,
    )

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(app.core.db, "engine", engine)
    with Session(engine) as session:
        instrument = FinanceInstrument(name="ETF", instrument_type="ETF")
        session.add(instrument)
        session.commit()
        session.refresh(instrument)
        session.add(
            FinanceListing(
                instrument_id=instrument.id,
                mic="XPAR",
                local_symbol="ETF.PA",
                yahoo_symbol="ETF.PA",
            )
        )
        session.commit()

    assert (
        append_analysis_results(
            [
                SimpleNamespace(
                    ticker="ETF.PA",
                    secteur="ETF",
                    chance_moat=None,
                    prix=25.0,
                    volume=2_500_000.0,
                    eps=None,
                    per=None,
                    croissance=None,
                    peg=None,
                    pays="FR",
                )
            ]
        )
        == 1
    )
    assert update_target_weights({"ETF.PA": 12.5}) == 1
    row = catalog_dataframe().iloc[0]
    assert pd.isna(row["Chance MOAT"])
    assert row["Volume"] == 2_500_000.0
    assert row["Poids"] == 12.5
