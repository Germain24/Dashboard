"""Synchronise le catalogue Trading 212 vers ToutBroker avec la place exacte.

Contrairement à un rapprochement par ``shortName`` seul, ``CBSM.PA`` et
``CBSM.DE`` ne sont pas confondus : ``workingScheduleId`` détermine le suffixe
Yahoo (.PA, .DE, .L…).
"""

from __future__ import annotations

import argparse
import datetime
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.backup_storage import backup_file  # noqa: E402

BROKER = ROOT / "data/imports/Finances/tableur/ToutBroker_ETF.xlsx"
COL = "Trading212"
TICKER_COL = "Ticker Yahoo Finance"


def synchronize(*, apply: bool, refresh: bool) -> dict:
    from app.services.finance.buffett.etf_index_registry import valid_isin
    from app.services.finance.trading212_api import (
        exchange_by_schedule,
        load_exchanges,
        load_instruments,
        yahoo_symbol,
    )

    if refresh:
        load_exchanges(max_age_days=0)
        instruments = load_instruments(max_age_days=0)
    else:
        instruments = load_instruments(max_age_days=7)
    schedules = exchange_by_schedule()
    by_symbol: dict[str, list[dict]] = defaultdict(list)
    unresolved = 0
    for instrument in instruments:
        symbol = yahoo_symbol(instrument, schedules)
        if not symbol:
            unresolved += 1
            continue
        by_symbol[symbol.upper()].append(instrument)

    table = pd.read_excel(BROKER, keep_default_na=False, na_values=[""])
    if TICKER_COL not in table or COL not in table:
        raise RuntimeError(f"colonnes absentes: {TICKER_COL!r} / {COL!r}")
    positions: dict[str, list[int]] = defaultdict(list)
    for index, value in table[TICKER_COL].items():
        symbol = str(value or "").strip().upper()
        if symbol:
            positions[symbol].append(index)

    old_available = table[COL].map(
        lambda value: str(value).strip().lower() in {"1", "1.0", "true", "vrai", "oui"}
    )
    old_etf_available = old_available & table["Secteur 1"].map(
        lambda value: str(value or "").strip().upper() == "ETF"
    )
    table[COL] = 0
    matched = 0
    metadata_updated = 0
    conflicts: dict[str, list[str]] = {}
    missing_rows: list[str] = []
    new_etf_rows: list[dict] = []
    for symbol, candidates in by_symbol.items():
        indexes = positions.get(symbol, [])
        if not indexes:
            missing_rows.append(symbol)
            identities = {
                (valid_isin(candidate.get("isin")), str(candidate.get("type") or "").upper())
                for candidate in candidates
            }
            identities.discard(("", ""))
            if len(identities) == 1:
                isin, kind = next(iter(identities))
                if isin and kind == "ETF":
                    candidate = candidates[0]
                    row = {column: "" for column in table.columns}
                    row.update({
                        TICKER_COL: symbol,
                        "Nom": str(candidate.get("name") or "").strip(),
                        "ISIN": isin,
                        "Secteur 1": "ETF",
                        "Secteur 2": "Actions",
                        COL: 1,
                    })
                    new_etf_rows.append(row)
            continue
        for index in indexes:
            table.at[index, COL] = 1
            matched += 1
        identities = {
            (valid_isin(candidate.get("isin")), str(candidate.get("type") or "").upper())
            for candidate in candidates
        }
        identities.discard(("", ""))
        if len(identities) != 1:
            conflicts[symbol] = sorted(
                f"{isin or '?'}:{kind or '?'}" for isin, kind in identities
            )
            continue
        isin, kind = next(iter(identities))
        candidate = candidates[0]
        for index in indexes:
            if isin:
                table.at[index, "ISIN"] = isin
            name = str(candidate.get("name") or "").strip()
            if name:
                table.at[index, "Nom"] = name
            if kind == "ETF":
                table.at[index, "Secteur 1"] = "ETF"
                if "Secteur 2" in table and not str(table.at[index, "Secteur 2"] or "").strip():
                    table.at[index, "Secteur 2"] = "Actions"
            elif kind == "STOCK" and str(table.at[index, "Secteur 1"] or "").strip().upper() == "ETF":
                table.at[index, "Secteur 1"] = ""
                if "Secteur 2" in table:
                    table.at[index, "Secteur 2"] = ""
            metadata_updated += 1

    if new_etf_rows:
        table = pd.concat([table, pd.DataFrame(new_etf_rows)], ignore_index=True)
    new_available = table[COL].astype(bool)
    new_etf_available = new_available & table["Secteur 1"].map(
        lambda value: str(value or "").strip().upper() == "ETF"
    )
    report = {
        "catalog_instruments": len(instruments),
        "resolved_symbols": len(by_symbol),
        "unresolved_instruments": unresolved,
        "matched_rows": matched,
        "available_before": int(old_available.sum()),
        "available_after": int(new_available.sum()),
        "removed_false_matches": int((old_available & ~new_available).sum()),
        "etf_available_before": int(old_etf_available.sum()),
        "etf_available_after": int(new_etf_available.sum()),
        "new_etf_rows": len(new_etf_rows),
        "metadata_updated": metadata_updated,
        "identity_conflicts": conflicts,
        "symbols_missing_from_workbook_count": len(missing_rows),
        "symbols_missing_from_workbook_sample": sorted(missing_rows)[:50],
    }
    if apply:
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = backup_file(
            BROKER,
            category="maintenance/import_trading212_catalog",
            filename=f"{BROKER.name}.bak-trading212-{stamp}",
        )
        from app.services.finance.buffett.broker_availability import _save_main_sheet

        _save_main_sheet(table, str(BROKER))
        from app.services.finance.catalog.repository import sync_local_broker_catalog_metadata

        report["sqlite"] = sync_local_broker_catalog_metadata()
        report["backup"] = str(backup)
    return report


def main() -> None:
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    print(json.dumps(synchronize(apply=args.apply, refresh=args.refresh), indent=2))


if __name__ == "__main__":
    main()
