"""Contrôle réel des connecteurs officiels ETF sur un échantillon du catalogue."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.finance.buffett.broker_availability import (
    _find_ticker_col,
    load_broker_table,
    load_etf_tickers,
)
from app.services.finance.buffett.official_etf_enrichment import enrich_official_etfs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--tickers", default="", help="Tickers séparés par des virgules")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=8.0)
    args = parser.parse_args()

    table = load_broker_table()
    ticker_column = _find_ticker_col(table.columns, "Ticker Yahoo Finance")
    etfs = load_etf_tickers(table)
    columns = {str(column).strip().casefold(): column for column in table.columns}
    name_column = next(columns[key] for key in ("nom", "name") if key in columns)
    isin_column = columns.get("isin")
    rows = table[
        table[ticker_column].astype(str).str.strip().str.upper().isin(etfs)
    ].copy()
    # Le catalogue historique contient aussi des ETC/ETN et certificats dans ses
    # anciennes listes ETF. Pour ce contrôle, « ETF » signifie un fonds qui se
    # déclare explicitement ETF dans son nom officiel.
    rows = rows[
        rows[name_column].astype(str).str.contains(r"\bETF\b", case=False, regex=True)
    ]
    rows["__ticker"] = rows[ticker_column].astype(str).str.strip().str.upper()
    selected = {value.strip().upper() for value in args.tickers.split(",") if value.strip()}
    if selected:
        rows = rows[rows["__ticker"].isin(selected)]
    dedup_column = isin_column or "__ticker"
    rows = rows.drop_duplicates(dedup_column).head(args.limit)

    temporary_root = Path(tempfile.mkdtemp(prefix="etf-official-check-"))

    def check(position_row):
        position, row = position_row
        ticker = row["__ticker"]
        one = rows.loc[[position]].drop(columns=["__ticker"])
        registry_path = temporary_root / f"{position}.json"
        with httpx.Client(
            timeout=args.timeout,
            follow_redirects=True,
            headers={"User-Agent": "MissionControl/1.0 ETF metadata check"},
        ) as client:
            status = enrich_official_etfs(
                {ticker}, broker_table=one, path=registry_path,
                force=True, client=client,
            ).get(ticker, {})
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        fund = next(iter(registry.get("funds", {}).values()), {})
        return {
            "ticker": ticker,
            "isin": fund.get("isin", ""),
            "name": fund.get("name", ""),
            "index": fund.get("index_name", ""),
            "replication": fund.get("replication", "unknown"),
            "status": status.get("status", "missing"),
            "coverage": status.get("coverage", 0.0),
            "management_fee_pct": (
                float(fund["management_fee_rate"]) * 100.0
                if fund.get("management_fee_rate") is not None
                else None
            ),
            "management_fee_source": fund.get("management_fee_source", ""),
            "url": status.get("source_url", ""),
            "error": status.get("error", ""),
        }

    results = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {executor.submit(check, item): item[1]["__ticker"] for item in rows.iterrows()}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:  # diagnostic : conserver les 50 résultats
                results.append({"ticker": ticker, "status": "exception", "error": str(exc)})

    results.sort(key=lambda item: item["ticker"])
    print(json.dumps({
        "count": len(results),
        "statuses": dict(Counter(item["status"] for item in results)),
        "results": results,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
