"""Audit reproductible des ETF, ISIN et méthodes de réplication par broker."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.finance.buffett.broker_availability import (
    _cell_state,
    _find_ticker_col,
    load_broker_table,
    load_etf_tickers,
)
from app.services.finance.buffett.etf_index_registry import (
    load_registry,
    valid_isin,
)


def main() -> None:
    table = load_broker_table()
    ticker_col = _find_ticker_col(table.columns, "Ticker Yahoo Finance")
    etfs = load_etf_tickers(table)
    rows = table[
        table[ticker_col].astype(str).str.strip().str.upper().isin(etfs)
    ].copy()
    rows["__valid_isin"] = rows["ISIN"].map(valid_isin) if "ISIN" in rows else ""

    broker_columns = {
        "Trading212": ("Tradding 212", "Trading 212", "Trading212"),
        "BourseDirect": ("Bourse Direct 2", "BoursDirect2"),
    }
    brokers: dict[str, dict] = {}
    for broker, candidates in broker_columns.items():
        column = next((name for name in candidates if name in rows.columns), None)
        selected = (
            rows[rows[column].map(lambda value: _cell_state(value) is True)]
            if column
            else rows.iloc[0:0]
        )
        brokers[broker] = {
            "quotes": int(len(selected)),
            "funds_by_isin": int(selected["__valid_isin"].replace("", None).nunique()),
            "valid_isin": int(selected["__valid_isin"].astype(bool).sum()),
            "missing_or_invalid_isin": int((~selected["__valid_isin"].astype(bool)).sum()),
            "missing_or_invalid_tickers": sorted(
                selected.loc[
                    ~selected["__valid_isin"].astype(bool), ticker_col
                ].astype(str).str.strip().tolist()
            ),
        }

    registry = load_registry()
    funds = [record for record in registry.get("funds", {}).values() if isinstance(record, dict)]
    replications = Counter(str(record.get("replication") or "unknown") for record in funds)
    unknown_statuses = Counter()
    unknown_issuers = Counter()
    for record in funds:
        if str(record.get("replication") or "unknown") != "unknown":
            continue
        enrichment = record.get("official_enrichment") or {}
        unknown_statuses[str(enrichment.get("status") or "never_checked")] += 1
        unknown_issuers[str(record.get("issuer") or "unknown")] += 1

    print(json.dumps({
        "workbook": {
            "rows": int(len(table)),
            "etf_quotes": int(len(rows)),
            "valid_isin": int(rows["__valid_isin"].astype(bool).sum()),
            "missing_or_invalid_isin": int((~rows["__valid_isin"].astype(bool)).sum()),
        },
        "brokers": brokers,
        "registry": {
            "fund_records": len(funds),
            "replications": dict(replications),
            "unknown_statuses": dict(unknown_statuses.most_common()),
            "unknown_issuers_top20": dict(unknown_issuers.most_common(20)),
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
