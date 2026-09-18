"""Lecture du catalogue SQLite sous la forme de compatibilité attendue par Buffett."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

_BOURSE_DIRECT_MARKET_PATH = {
    "XPAR": "euronext-paris",
    "ALXP": "euronext-access-paris",
    "XMLI": "euronext-growth-paris",
    "XAMS": "euronext-amsterdam",
    "XBRU": "euronext-bruxelles",
    "XLIS": "euronext-lisbonne",
    "XETR": "xetra",
    "XFRA": "francfort",
    "XSWX": "six-swiss-exchange",
    "XLON": "londres",
    "XMAD": "madrid",
    "ETFP": "milan",
}

_TRADING212_PUBLIC_SUFFIX = {
    "Deutsche Börse Xetra": "DE",
    "Gettex": "DE",
    "London Stock Exchange": "GB",
    "London Stock Exchange AIM": "GB",
    "London Stock Exchange NON-ISA": "GB",
    "SIX Swiss Exchange": "CH",
    "Toronto Stock Exchange": "CA",
    "Borsa Italiana": "IT",
    "Euronext Amsterdam": "NL",
    "Euronext Brussels": "BE",
    "Euronext Paris": "FR",
    "Euronext Lisbon": "PT",
    "Bolsa de Madrid": "ES",
    "Wiener Börse": "AT",
    "NYSE": "US",
    "NASDAQ": "US",
}


def _broker_product_url(source: str, record: dict, exchange_name: str = "") -> str:
    """Construit le lien public auditable sans l'utiliser comme preuve d'indice."""
    if source == "boursedirect":
        slug = str(record.get("slug") or "").strip(" /")
        market = _BOURSE_DIRECT_MARKET_PATH.get(str(record.get("mic") or "").upper())
        if slug and market:
            return f"https://www.boursedirect.fr/fr/marche/{market}/{slug}/seance"
        return "https://www.boursedirect.fr/fr/marches/recherche?pea=true"
    short = str(record.get("shortName") or "").strip().upper()
    suffix = _TRADING212_PUBLIC_SUFFIX.get(exchange_name)
    if short and suffix:
        return f"https://www.trading212.com/trading-instruments/invest/{short}.{suffix}"
    return "https://www.trading212.com/trading-instruments/invest"


def sync_local_broker_catalog_metadata(
    *,
    boursedirect_path: str | Path | None = None,
    trading212_path: str | Path | None = None,
    trading212_exchanges_path: str | Path | None = None,
    registry_path: str | Path | None = None,
) -> dict:
    """Réconcilie les caches broker/indice avec le catalogue SQLite actif.

    Les collecteurs broker sont les sources d'identité et de négociabilité ; le
    registre ETF reste la source de l'indice et de sa preuve officielle. Cette
    opération est locale, idempotente et ne transforme jamais une URL produit
    broker en preuve de composition économique.
    """
    from sqlalchemy import bindparam, text

    from app.core.config import settings
    from app.core.db import engine
    from app.services.finance.buffett.etf_index_registry import (
        DEFAULT_REGISTRY_PATH,
        canonical_index_id,
        valid_isin,
    )

    variables = settings.imports_dir / "Finances" / "variables"
    bd_path = Path(boursedirect_path or variables / "boursedirect_pea_etfs.json")
    t212_path = Path(trading212_path or variables / "trading212_instruments.json")
    exchanges_path = Path(
        trading212_exchanges_path or variables / "trading212_exchanges.json"
    )
    reg_path = Path(registry_path or DEFAULT_REGISTRY_PATH)

    records: list[dict] = []
    bd_snapshot_loaded = False
    t212_snapshot_loaded = False
    if bd_path.exists():
        payload = json.loads(bd_path.read_text(encoding="utf-8"))
        bd_snapshot_loaded = isinstance(payload.get("instruments"), list)
        for item in payload.get("instruments", []):
            ticker = str(item.get("yahoo") or "").strip().upper()
            if ticker:
                records.append({
                    "ticker": ticker,
                    "broker": "BOURSE_DIRECT_PEA",
                    "source": "boursedirect_public_search",
                    "source_url": _broker_product_url("boursedirect", item),
                    "record_id": str(item.get("slug") or ""),
                    "isin": valid_isin(item.get("isin")),
                    "name": str(item.get("name") or "").strip(),
                    "kind": "ETF",
                })

    schedules: dict[int, str] = {}
    if exchanges_path.exists():
        for exchange in json.loads(exchanges_path.read_text(encoding="utf-8")):
            for schedule in exchange.get("workingSchedules") or []:
                schedules[int(schedule["id"])] = str(exchange.get("name") or "")
    if t212_path.exists() and schedules:
        from app.services.finance.trading212_api import yahoo_symbol

        t212_payload = json.loads(t212_path.read_text(encoding="utf-8"))
        t212_snapshot_loaded = isinstance(t212_payload, list)
        for item in t212_payload:
            ticker = yahoo_symbol(item, schedules)
            if not ticker:
                continue
            exchange_name = schedules.get(int(item.get("workingScheduleId") or 0), "")
            records.append({
                "ticker": ticker.upper(),
                "broker": "TRADING212",
                "source": "trading212_api_v0",
                "source_url": _broker_product_url("trading212", item, exchange_name),
                "record_id": str(item.get("ticker") or ""),
                "isin": valid_isin(item.get("isin")),
                "name": str(item.get("name") or "").strip(),
                "kind": str(item.get("type") or "").strip().upper(),
            })

    registry = (
        json.loads(reg_path.read_text(encoding="utf-8")) if reg_path.exists() else {}
    )
    registry_by_ticker: dict[str, dict] = {}

    def registry_quality(fund: dict) -> tuple[int, int, int, int]:
        enrichment = fund.get("official_enrichment") or {}
        return (
            int(bool(str(fund.get("index_id") or fund.get("index_name") or "").strip())),
            int(str(fund.get("replication") or "unknown") != "unknown"),
            int(bool(str(enrichment.get("source_url") or "").strip())),
            int(bool(valid_isin(fund.get("isin")))),
        )

    for fund in registry.get("funds", {}).values():
        if not isinstance(fund, dict):
            continue
        for ticker in fund.get("tickers") or []:
            normalized = str(ticker).strip().upper()
            current = registry_by_ticker.get(normalized)
            if current is None or registry_quality(fund) > registry_quality(current):
                registry_by_ticker[normalized] = fund

    symbols = sorted({item["ticker"] for item in records} | set(registry_by_ticker))
    if not symbols:
        return {"source_records": 0, "matched_listings": 0, "indices": 0}
    lookup = text("""
        SELECT l.id, l.instrument_id, COALESCE(l.yahoo_symbol, l.local_symbol)
        FROM finance_listing l
        WHERE l.yahoo_symbol IN :symbols
           OR (l.yahoo_symbol IS NULL AND l.local_symbol IN :symbols)
    """).bindparams(bindparam("symbols", expanding=True))
    listings: dict[str, list[tuple[int, int]]] = {}
    with engine.connect() as connection:
        for start in range(0, len(symbols), 400):
            for listing_id, instrument_id, ticker in connection.execute(
                lookup, {"symbols": symbols[start : start + 400]},
            ):
                listings.setdefault(str(ticker).upper(), []).append(
                    (int(listing_id), int(instrument_id))
                )

    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat()
    stats = {
        "source_records": len(records), "matched_listings": 0,
        "isin_filled": 0, "instrument_relinked": 0, "isin_conflicts": 0,
        "availability_reset": 0, "availability_upserted": 0,
        "registry_metadata": 0, "indices": 0,
    }
    with engine.begin() as connection:
        broker_rows = {
            str(row[1]): int(row[0])
            for row in connection.execute(text("SELECT id, code FROM finance_broker"))
        }
        instruments_by_isin = {
            str(isin): int(instrument_id)
            for instrument_id, isin in connection.execute(text(
                "SELECT id, isin FROM finance_instrument WHERE isin IS NOT NULL"
            ))
            if valid_isin(isin)
        }
        for item in records:
            matches = listings.get(item["ticker"], [])
            stats["matched_listings"] += len(matches)
            for listing_id, instrument_id in matches:
                if item["isin"]:
                    current = connection.execute(
                        text("SELECT isin FROM finance_instrument WHERE id=:id"),
                        {"id": instrument_id},
                    ).scalar()
                    if not valid_isin(current):
                        canonical_instrument_id = instruments_by_isin.get(item["isin"])
                        if (
                            canonical_instrument_id is not None
                            and canonical_instrument_id != instrument_id
                        ):
                            connection.execute(text("""
                                UPDATE finance_listing SET instrument_id=:instrument_id,
                                    updated_at=:now WHERE id=:listing_id
                            """), {
                                "instrument_id": canonical_instrument_id,
                                "now": now, "listing_id": listing_id,
                            })
                            instrument_id = canonical_instrument_id
                            stats["instrument_relinked"] += 1
                        else:
                            connection.execute(text("""
                                UPDATE finance_instrument
                                SET isin=:isin, identity_status='VERIFIED', updated_at=:now
                                WHERE id=:id
                            """), {
                                "isin": item["isin"], "now": now, "id": instrument_id,
                            })
                            instruments_by_isin[item["isin"]] = instrument_id
                            stats["isin_filled"] += 1
                    elif valid_isin(current) != item["isin"]:
                        canonical_instrument_id = instruments_by_isin.get(item["isin"])
                        if (
                            canonical_instrument_id is not None
                            and canonical_instrument_id != instrument_id
                        ):
                            connection.execute(text("""
                                UPDATE finance_listing SET instrument_id=:instrument_id,
                                    updated_at=:now WHERE id=:listing_id
                            """), {
                                "instrument_id": canonical_instrument_id,
                                "now": now, "listing_id": listing_id,
                            })
                            instrument_id = canonical_instrument_id
                            stats["instrument_relinked"] += 1
                        else:
                            # Sans instrument canonique déjà vérifié, ne jamais
                            # écraser silencieusement une identité contradictoire.
                            stats["isin_conflicts"] += 1
                if item["kind"] == "ETF":
                    connection.execute(text("""
                        UPDATE finance_instrument
                        SET instrument_type='ETF',
                            name=CASE WHEN :name != '' THEN :name ELSE name END,
                            updated_at=:now
                        WHERE id=:id
                    """), {"name": item["name"], "now": now, "id": instrument_id})
                broker_id = broker_rows.get(item["broker"])
                if broker_id is not None:
                    connection.execute(text("""
                        INSERT INTO finance_broker_availability
                            (listing_id, broker_id, state, checked_at, source,
                             source_url, source_record_id)
                        VALUES (:listing_id, :broker_id, 'TRUE', :now, :source,
                                :source_url, :record_id)
                        ON CONFLICT(listing_id, broker_id) DO UPDATE SET
                            state='TRUE', checked_at=excluded.checked_at,
                            source=excluded.source, source_url=excluded.source_url,
                            source_record_id=excluded.source_record_id
                    """), {
                        "listing_id": listing_id, "broker_id": broker_id, "now": now,
                        "source": item["source"], "source_url": item["source_url"],
                        "record_id": item["record_id"],
                    })
                    stats["availability_upserted"] += 1

        # Les lignes vues portent toutes exactement le token ``now``. On ne
        # désactive ensuite que les anciennes disponibilités absentes du
        # snapshot, sans réécrire deux fois les milliers de lignes encore vraies.
        if t212_snapshot_loaded and broker_rows.get("TRADING212") is not None:
            reset = connection.execute(text("""
                UPDATE finance_broker_availability SET state='FALSE', checked_at=:now,
                    source='trading212_api_v0'
                WHERE broker_id=:broker_id AND state != 'FALSE'
                  AND (checked_at IS NULL OR checked_at != :now)
            """), {"now": now, "broker_id": broker_rows["TRADING212"]})
            stats["availability_reset"] += max(int(reset.rowcount or 0), 0)
        if bd_snapshot_loaded and broker_rows.get("BOURSE_DIRECT_PEA") is not None:
            reset = connection.execute(text("""
                UPDATE finance_broker_availability SET state='FALSE', checked_at=:now,
                    source='boursedirect_public_search'
                WHERE broker_id=:broker_id AND state != 'FALSE'
                  AND (checked_at IS NULL OR checked_at != :now)
                  AND listing_id IN (
                      SELECT l.id FROM finance_listing l
                      JOIN finance_instrument i ON i.id=l.instrument_id
                      WHERE i.instrument_type='ETF'
                  )
            """), {"now": now, "broker_id": broker_rows["BOURSE_DIRECT_PEA"]})
            stats["availability_reset"] += max(int(reset.rowcount or 0), 0)

        seen_indices: set[str] = set()
        for ticker, fund in registry_by_ticker.items():
            index_name = str(fund.get("index_name") or "").strip()
            index_id = str(fund.get("index_id") or canonical_index_id(index_name)).strip()
            replication = str(fund.get("replication") or "").strip()
            enrichment = fund.get("official_enrichment") or {}
            index_record = registry.get("indices", {}).get(index_id, {}) or {}
            index_enrichment = index_record.get("official_enrichment") or {}
            index_url = str(
                index_enrichment.get("source_url")
                or (index_record.get("composition") or {}).get("source_url") or ""
            ).strip()
            fund_url = str(enrichment.get("source_url") or "").strip()
            if index_id and index_name and index_id not in seen_indices:
                connection.execute(text("""
                    INSERT INTO finance_index (canonical_code, name, source, source_url)
                    VALUES (:code, :name, :source, :url)
                    ON CONFLICT(canonical_code) DO UPDATE SET
                        name=excluded.name,
                        source=CASE WHEN excluded.source != '' THEN excluded.source ELSE finance_index.source END,
                        source_url=CASE WHEN excluded.source_url != '' THEN excluded.source_url ELSE finance_index.source_url END
                """), {
                    "code": index_id, "name": index_name,
                    "source": str(index_enrichment.get("provider") or fund.get("source") or ""),
                    "url": index_url,
                })
                seen_indices.add(index_id)
            for listing_id, _instrument_id in listings.get(ticker, []):
                if index_name:
                    connection.execute(text("""
                        UPDATE finance_listing SET metadata_json=json_set(
                            CASE
                                WHEN metadata_json IS NULL OR json_type(metadata_json)='null'
                                THEN '{}'
                                ELSE metadata_json
                            END,
                            '$.Indice', :index_name,
                            '$.Indice_ID', :index_id, '$.Réplication', :replication,
                            '$.ETF_Source_URL', :fund_url, '$.Indice_Source_URL', :index_url
                        ), updated_at=:now WHERE id=:id
                    """), {
                        "index_name": index_name, "index_id": index_id,
                        "replication": replication, "fund_url": fund_url,
                        "index_url": index_url, "now": now, "id": listing_id,
                    })
                    stats["registry_metadata"] += 1
        stats["indices"] = len(seen_indices)
    return stats


def catalog_dataframe():
    """Retourne le catalogue normalisé, ou ``None`` tant qu'il n'est pas migré."""
    import pandas as pd
    from sqlalchemy import text

    from app.core.db import engine

    try:
        query = text("""
            SELECT
                COALESCE(l.yahoo_symbol, l.local_symbol) AS "Ticker Yahoo Finance",
                i.name AS "Nom", i.instrument_type AS "Type",
                i.isin AS "ISIN", i.domicile_country AS "Pays",
                l.mic AS "Primary MIC", l.primary_market AS "Primary Market",
                l.fundamentals_symbol AS "Fundamentals Symbol",
                json_extract(l.metadata_json, '$.Secteur') AS "Secteur",
                COALESCE(json_extract(l.metadata_json, '$.Secteur 1'),
                    CASE WHEN i.instrument_type = 'ETF' THEN 'ETF' END) AS "Secteur 1",
                json_extract(l.metadata_json, '$.Secteur 2') AS "Secteur 2",
                json_extract(l.metadata_json, '$.Secteur 3') AS "Secteur 3",
                json_extract(l.metadata_json, '$.Secteur 4') AS "Secteur 4",
                json_extract(l.metadata_json, '$.Secteur 5') AS "Secteur 5",
                COALESCE(json_extract(l.metadata_json, '$.Indice'),
                    json_extract(l.metadata_json, '$.Index'),
                    json_extract(l.metadata_json, '$.Benchmark')) AS "Indice",
                json_extract(l.metadata_json, '$.TER') AS "TER",
                COALESCE(json_extract(l.metadata_json, '$.Réplication'),
                    json_extract(l.metadata_json, '$.Replication')) AS "Réplication",
                json_extract(l.metadata_json, '$.ETF_Source_URL') AS "ETF Source URL",
                json_extract(l.metadata_json, '$.Indice_Source_URL') AS "Index Source URL",
                json_extract(l.metadata_json, '$.TTF') AS "TTF",
                json_extract(l.metadata_json, '$.Poids') AS "Poids",
                CASE WHEN i.instrument_type='ETF' THEN NULL
                    ELSE json_extract(l.metadata_json, '$.Chance MOAT') END AS "Chance MOAT",
                mo.price AS "Prix", COALESCE(mo.price_currency, l.currency) AS "Prix devise",
                mo.observed_at AS "Prix date", mo.average_volume_shares,
                mo.average_turnover_value AS "Volume", mo.turnover_currency AS "VolumeDevise",
                COALESCE(MAX(CASE WHEN b.code='TRADING212' THEN ba.state END), 'UNKNOWN') AS "Trading212",
                MAX(CASE WHEN b.code='TRADING212' THEN ba.source_url END) AS "Trading212 URL",
                COALESCE(MAX(CASE WHEN b.code='BOURSE_DIRECT_PEA' THEN ba.state END), 'UNKNOWN') AS "BoursDirect2",
                MAX(CASE WHEN b.code='BOURSE_DIRECT_PEA' THEN ba.source_url END) AS "Bourse Direct URL",
                COALESCE(MAX(CASE WHEN b.code='IBKR' THEN ba.state END), 'UNKNOWN') AS "IBKR"
            FROM finance_listing l
            JOIN finance_instrument i ON i.id = l.instrument_id
            LEFT JOIN finance_broker_availability ba ON ba.listing_id = l.id
            LEFT JOIN finance_broker b ON b.id = ba.broker_id
            LEFT JOIN finance_market_observation mo ON mo.id = (
                SELECT MAX(mo2.id) FROM finance_market_observation mo2
                WHERE mo2.listing_id = l.id
            )
            GROUP BY l.id
        """)
        with engine.connect() as connection:
            frame = pd.read_sql_query(query, connection)
    except Exception:
        # Base pas encore migrée : le classeur reste un bootstrap en lecture.
        return None
    return frame if not frame.empty else None


def normalized_catalog_is_active() -> bool:
    from sqlalchemy import text

    from app.core.db import engine

    try:
        with engine.connect() as connection:
            return bool(connection.execute(text("SELECT 1 FROM finance_listing LIMIT 1")).first())
    except Exception:
        return False


def append_analysis_results(rows) -> int:
    """Ajoute des observations datées et actualise les métadonnées de listing."""
    from sqlalchemy import bindparam, text

    from app.core.db import engine

    payload = []
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat()
    for row in rows:
        ticker = str(getattr(row, "ticker", "") or "").strip().upper()
        if not ticker:
            continue
        sector = getattr(row, "secteur", None)
        is_etf = str(sector or "").strip().upper() == "ETF"
        metadata = {
            "Secteur": sector,
            "Chance MOAT": None if is_etf else getattr(row, "chance_moat", None),
        }
        payload.append(
            {
                "ticker": ticker,
                "metadata": json.dumps(metadata, ensure_ascii=False, default=str),
                "now": now,
                "price": getattr(row, "prix", None),
                "turnover": getattr(row, "volume", None),
                "eps": getattr(row, "eps", None),
                "per": getattr(row, "per", None),
                "growth": getattr(row, "croissance", None),
                "peg": getattr(row, "peg", None),
                "sector": sector,
                "country": getattr(row, "pays", None),
            }
        )
    if not payload:
        return 0
    # Résoudre les IDs avec les index natifs des symboles. L'ancienne forme
    # ``UPPER(COALESCE(...))=:ticker`` rescannait les 258 000 listings pour
    # chacune des ~20 000 lignes et conservait le verrou d'écriture assez
    # longtemps pour faire échouer d'autres jobs SQLite.
    listings_by_ticker: dict[str, list[tuple[int, int]]] = {}
    symbols = sorted({item["ticker"] for item in payload})
    lookup = text("""
        SELECT id, instrument_id,
               COALESCE(yahoo_symbol, local_symbol) AS ticker
        FROM finance_listing
        WHERE yahoo_symbol IN :symbols
           OR (yahoo_symbol IS NULL AND local_symbol IN :symbols)
    """).bindparams(bindparam("symbols", expanding=True))
    with engine.connect() as connection:
        for start in range(0, len(symbols), 400):
            block = symbols[start : start + 400]
            for listing_id, instrument_id, ticker in connection.execute(
                lookup,
                {"symbols": block},
            ):
                listings_by_ticker.setdefault(str(ticker).upper(), []).append(
                    (int(listing_id), int(instrument_id))
                )

    expanded = [
        item | {"listing_id": listing_id, "instrument_id": instrument_id}
        for item in payload
        for listing_id, instrument_id in listings_by_ticker.get(item["ticker"], [])
    ]
    if not expanded:
        return 0

    update_listing = text("""
        UPDATE finance_listing
        SET metadata_json=json_patch(COALESCE(metadata_json, '{}'), json(:metadata)),
            updated_at=:now
        WHERE id=:listing_id
    """)
    insert_market = text("""
        INSERT INTO finance_market_observation
            (listing_id, observed_at, imported_at, price,
             average_turnover_value, turnover_currency, source)
        SELECT :listing_id, :now, :now, :price, :turnover, 'EUR', 'buffett_run'
        WHERE :price IS NOT NULL OR :turnover IS NOT NULL
    """)
    insert_fundamental = text("""
        INSERT INTO finance_fundamental_observation
            (instrument_id, observed_at, imported_at, eps, per, growth, peg,
             sector, country, source)
        SELECT :instrument_id, :now, :now, :eps, :per, :growth, :peg,
               :sector, :country, 'buffett_run'
        WHERE :eps IS NOT NULL OR :per IS NOT NULL OR :growth IS NOT NULL
           OR :peg IS NOT NULL OR :sector IS NOT NULL
    """)
    # Petites transactions : elles relâchent régulièrement le writer lock et
    # laissent les jobs Agenda/notifications écrire entre deux lots.
    for start in range(0, len(expanded), 250):
        block = expanded[start : start + 250]
        with engine.begin() as connection:
            connection.execute(update_listing, block)
            connection.execute(insert_market, block)
            connection.execute(insert_fundamental, block)
    return sum(1 for item in payload if item["ticker"] in listings_by_ticker)


def update_target_weights(weights: dict[str, float]) -> int:
    """Persiste la dernière cible dans SQLite; les listings absents repassent à zéro."""
    from sqlalchemy import text

    from app.core.db import engine

    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat()
    with engine.begin() as connection:
        connection.execute(
            text("""
            UPDATE finance_listing
            SET metadata_json=json_set(COALESCE(metadata_json, '{}'), '$.Poids', 0),
                updated_at=:now
        """),
            {"now": now},
        )
        if not weights:
            return 0
        payload = [
            {"ticker": ticker.upper(), "weight": float(weight), "now": now}
            for ticker, weight in weights.items()
        ]
        result = connection.execute(
            text("""
            UPDATE finance_listing
            SET metadata_json=json_set(COALESCE(metadata_json, '{}'), '$.Poids', :weight),
                updated_at=:now
            WHERE UPPER(COALESCE(yahoo_symbol, local_symbol))=:ticker
        """),
            payload,
        )
    return int(result.rowcount or len(payload))
