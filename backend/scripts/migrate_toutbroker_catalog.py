"""Migre ToutBroker.xlsx vers le catalogue SQLite normalisé.

Par défaut, effectue uniquement un audit. Utiliser ``--apply`` après la migration
Alembic. Le script refuse d'écraser un catalogue déjà rempli.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import func
from sqlmodel import Session, select

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.core.db import engine  # noqa: E402
from app.models.finance_catalog import (  # noqa: E402
    FinanceBroker,
    FinanceBrokerAvailability,
    FinanceFundamentalObservation,
    FinanceInstrument,
    FinanceListing,
    FinanceMarketObservation,
)
from app.services.finance.buffett.config import Config  # noqa: E402
from app.services.finance.buffett.etf_index_registry import valid_isin  # noqa: E402

ISIN_CORRECTIONS = {
    "VIG": "US9219088443",
    "VOE": "US9229085124",
    "LIT": "US37954Y8553",
    "PDN": "US46138E7351",
    "MMK": "US85749T2859",
}
BROKERS = (
    (1, "TRADING212", "Trading 212", "CTO"),
    (2, "BOURSE_DIRECT_PEA", "Bourse Direct PEA", "PEA"),
    (3, "IBKR", "Interactive Brokers", "CTO"),
)


def fix_text(value):
    if not isinstance(value, str) or not any(marker in value for marker in ("Ã", "Â", "â€")):
        return value
    try:
        return value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


def clean_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    # Le classeur dépasse 250k lignes : ne jamais dupliquer toute la matrice ni
    # matérialiser un masque booléen de toutes ses cellules.
    for column in (
        "Nom",
        "Pays",
        "Secteur",
        "Secteur 1",
        "Secteur 2",
        "Secteur 3",
        "Secteur 4",
        "Secteur 5",
        "Type",
        "Primary MIC",
        "Fundamentals Symbol",
    ):
        if column not in frame.columns:
            continue
        frame[column] = frame[column].map(fix_text)
    ticker_col = "Ticker Yahoo Finance"
    frame[ticker_col] = frame[ticker_col].fillna("").astype(str).str.strip().str.upper()
    frame = frame[frame[ticker_col].ne("")].copy()
    corrected = 0
    if "ISIN" not in frame:
        frame["ISIN"] = None
    for ticker, isin in ISIN_CORRECTIONS.items():
        mask = frame[ticker_col].eq(ticker)
        corrected += int(mask.sum())
        frame.loc[mask, "ISIN"] = isin
    frame["ISIN"] = frame["ISIN"].map(lambda value: valid_isin(value) or None)
    # Un listing est unique. Pour IPN.PA et les autres snapshots superposés,
    # conserver la ligne la plus complète au lieu d'un choix dépendant de l'ordre.
    duplicate_mask = frame.duplicated(ticker_col, keep=False)
    duplicates = int(frame.duplicated(ticker_col, keep="first").sum())
    if duplicates:
        unique_rows = frame[~duplicate_mask]
        candidates = frame[duplicate_mask].copy()
        candidates["_completeness"] = candidates.notna().sum(axis=1)
        selected = (
            candidates.sort_values("_completeness", ascending=False)
            .drop_duplicates(ticker_col, keep="first")
            .drop(columns="_completeness")
        )
        frame = pd.concat([unique_rows, selected], ignore_index=True)
    sector_etf = (
        frame.get("Secteur 1", pd.Series(index=frame.index, dtype=object))
        .astype(str)
        .str.upper()
        .eq("ETF")
    )
    type_etf = (
        frame.get("Type", pd.Series(index=frame.index, dtype=object))
        .astype(str)
        .str.upper()
        .str.contains(r"\bETF\b", regex=True)
    )
    moat_values = pd.to_numeric(frame.get("Chance MOAT"), errors="coerce")
    # Le 200 n'est accepté qu'en entrée de migration comme marqueur legacy;
    # il est immédiatement converti en type ETF + MOAT vide.
    etf_mask = sector_etf | type_etf | moat_values.ge(200)
    moat_200 = int((moat_values.ge(200) & etf_mask).sum())
    if "Secteur 1" not in frame:
        frame["Secteur 1"] = None
    frame.loc[etf_mask, "Secteur 1"] = "ETF"
    if "Chance MOAT" in frame:
        frame.loc[etf_mask, "Chance MOAT"] = None
    return frame, {
        "rows": len(frame),
        "duplicate_listings_removed": duplicates,
        "known_isin_rows_corrected": corrected,
        "etf_moat_200_cleared": moat_200,
        "valid_isin": int(frame["ISIN"].notna().sum()),
    }


def state(value) -> str:
    if pd.isna(value) or str(value).strip() == "":
        return "UNKNOWN"
    normalized = str(value).strip().casefold()
    if normalized in {"1", "1.0", "true", "vrai", "oui"}:
        return "TRUE"
    if normalized in {"0", "0.0", "false", "faux", "non"}:
        return "FALSE"
    return "UNKNOWN"


def chunks(items: list[dict], size: int = 5000):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def migrate(frame: pd.DataFrame, *, replace: bool = False) -> dict:
    with Session(engine) as session:
        if session.exec(select(func.count(FinanceListing.id))).one() and not replace:
            raise RuntimeError("Le catalogue SQLite contient déjà des listings; migration annulée")

    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    buffers: dict[str, list[dict]] = {
        "instruments": [],
        "listings": [],
        "market": [],
        "fundamental": [],
        "availability": [],
    }
    totals = {name: 0 for name in buffers}
    identity_ids: dict[str, int] = {}
    next_instrument = 1
    next_listing = 1

    def value(row, name):
        raw = row.get(name)
        if pd.isna(raw) or str(raw).strip() == "":
            return None
        item = getattr(raw, "item", None)
        return item() if callable(item) else raw

    broker_sources = {
        1: next(
            (column for column in ("Trading212", "Tradding 212") if column in frame.columns), None
        ),
        2: next(
            (column for column in ("Bourse Direct 2", "BoursDirect2") if column in frame.columns),
            None,
        ),
    }
    tables = {
        "instruments": FinanceInstrument.__table__,
        "listings": FinanceListing.__table__,
        "market": FinanceMarketObservation.__table__,
        "fundamental": FinanceFundamentalObservation.__table__,
        "availability": FinanceBrokerAvailability.__table__,
    }

    def flush(conn) -> None:
        # L'ordre respecte les FK; chaque buffer est borné à environ 5k lignes.
        for name in ("instruments", "listings", "market", "fundamental", "availability"):
            rows = buffers[name]
            if rows:
                conn.execute(tables[name].insert(), rows)
                totals[name] += len(rows)
                rows.clear()

    with engine.begin() as conn:
        if replace:
            from sqlalchemy import delete

            from app.models.finance_catalog import FinanceIndex, FinanceIndexConstituent

            for table in (
                FinanceIndexConstituent,
                FinanceFundamentalObservation,
                FinanceMarketObservation,
                FinanceBrokerAvailability,
                FinanceListing,
                FinanceInstrument,
                FinanceIndex,
                FinanceBroker,
            ):
                conn.execute(delete(table))
        conn.execute(
            FinanceBroker.__table__.insert(),
            [
                {"id": broker_id, "code": code, "label": label, "account_type": account}
                for broker_id, code, label, account in BROKERS
            ],
        )
        for _, row in frame.iterrows():
            ticker = str(row["Ticker Yahoo Finance"])
            isin = value(row, "ISIN")
            mic = str(value(row, "Primary MIC") or value(row, "MIC") or "UNKNOWN").upper()
            identity = f"ISIN:{isin}" if isin else f"LISTING:{mic}:{ticker}"
            instrument_id = identity_ids.get(identity)
            is_etf = str(value(row, "Secteur 1") or "").upper() == "ETF"
            if instrument_id is None:
                instrument_id = next_instrument
                next_instrument += 1
                identity_ids[identity] = instrument_id
                country = str(value(row, "Pays") or "").upper()
                buffers["instruments"].append(
                    {
                        "id": instrument_id,
                        "isin": isin,
                        "name": str(value(row, "Nom") or ticker),
                        "instrument_type": "ETF"
                        if is_etf
                        else str(value(row, "Type") or "STOCK").upper(),
                        "domicile_country": country if len(country) == 2 else None,
                        "identity_status": "VERIFIED" if isin else "UNVERIFIED",
                        "source": "ToutBroker.xlsx",
                        "created_at": now,
                        "updated_at": now,
                    }
                )
            listing_id = next_listing
            next_listing += 1
            buffers["listings"].append(
                {
                    "id": listing_id,
                    "instrument_id": instrument_id,
                    "mic": mic,
                    "local_symbol": ticker,
                    "yahoo_symbol": ticker,
                    "currency": value(row, "Devise") or value(row, "Prix devise"),
                    "primary_market": state(value(row, "Primary Market")) == "TRUE",
                    "fundamentals_symbol": value(row, "Fundamentals Symbol"),
                    "metadata_json": {
                        key: value(row, key)
                        for key in (
                            "Secteur",
                            "Secteur 1",
                            "Secteur 2",
                            "Secteur 3",
                            "Secteur 4",
                            "Secteur 5",
                            "Indice",
                            "Index",
                            "Benchmark",
                            "TER",
                            "Réplication",
                            "Replication",
                            "TTF",
                            "Poids",
                            "Chance MOAT",
                        )
                        if value(row, key) is not None
                    },
                    "created_at": now,
                    "updated_at": now,
                }
            )
            price = pd.to_numeric(value(row, "Prix"), errors="coerce")
            turnover = pd.to_numeric(value(row, "Volume"), errors="coerce")
            if pd.notna(price) or pd.notna(turnover):
                buffers["market"].append(
                    {
                        "listing_id": listing_id,
                        "imported_at": now,
                        "price": float(price) if pd.notna(price) else None,
                        "price_currency": value(row, "Prix devise") or value(row, "Devise"),
                        "average_turnover_value": float(turnover) if pd.notna(turnover) else None,
                        "turnover_currency": value(row, "VolumeDevise") or "EUR",
                        "source": "ToutBroker.xlsx",
                    }
                )
            fvals = {
                name: pd.to_numeric(value(row, column), errors="coerce")
                for name, column in (
                    ("eps", "EPS"),
                    ("per", "PER"),
                    ("growth", "Croissance"),
                    ("peg", "PEG"),
                )
            }
            if any(pd.notna(item) for item in fvals.values()) or value(row, "Secteur"):
                buffers["fundamental"].append(
                    {
                        "instrument_id": instrument_id,
                        "imported_at": now,
                        **{
                            key: float(item) if pd.notna(item) else None
                            for key, item in fvals.items()
                        },
                        "sector": value(row, "Secteur"),
                        "country": value(row, "Pays"),
                        "source": "ToutBroker.xlsx",
                    }
                )
            for broker_id, column in broker_sources.items():
                if column is not None:
                    buffers["availability"].append(
                        {
                            "listing_id": listing_id,
                            "broker_id": broker_id,
                            "state": state(value(row, column)),
                            "source": "broker_catalog_import",
                            "checked_at": now,
                        }
                    )
            # IBKR reste volontairement absent donc UNKNOWN jusqu'à authentification.
            if len(buffers["listings"]) >= 5000:
                flush(conn)
        flush(conn)
    return {
        "instruments": totals["instruments"],
        "listings": totals["listings"],
        "market_observations": totals["market"],
        "fundamental_observations": totals["fundamental"],
        "broker_availability": totals["availability"],
    }


def repair_existing_etf_types(frame: pd.DataFrame) -> dict:
    """Convertit les anciens marqueurs 200 déjà importés en type ETF explicite."""
    from sqlalchemy import update

    tickers = (
        frame.loc[
            frame["Secteur 1"].astype(str).str.upper().eq("ETF"),
            "Ticker Yahoo Finance",
        ]
        .astype(str)
        .tolist()
    )
    changed = 0
    with engine.begin() as connection:
        for batch in chunks(tickers, 500):
            instrument_ids = select(FinanceListing.instrument_id).where(
                FinanceListing.yahoo_symbol.in_(batch)  # type: ignore[attr-defined]
            )
            result = connection.execute(
                update(FinanceInstrument)
                .where(FinanceInstrument.id.in_(instrument_ids))  # type: ignore[attr-defined]
                .values(instrument_type="ETF", updated_at=dt.datetime.now())
            )
            changed += int(result.rowcount or 0)
    return {"etf_types_repaired": changed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path(Config.BROKER_FILE))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--repair-existing", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    audit_columns = {
        "Ticker Yahoo Finance",
        "Nom",
        "ISIN",
        "Secteur 1",
        "Chance MOAT",
    }
    frame = pd.read_excel(
        args.input,
        engine="calamine",
        keep_default_na=False,
        na_values=[""],
        usecols=None if args.apply else lambda column: column in audit_columns,
    )
    cleaned, report = clean_frame(frame)
    report["mode"] = (
        "repair-existing" if args.repair_existing else "apply" if args.apply else "dry-run"
    )
    if args.apply:
        report.update(migrate(cleaned, replace=args.replace))
    elif args.repair_existing:
        report.update(repair_existing_etf_types(cleaned))
    target = args.report or args.input.with_suffix(".migration-report.json")
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
