"""Remplace les codes Tokyo générés par la liste officielle JPX.

Le CSV legacy reste sans en-tête et séparé par ``;`` :
Ticker;Nom;Bourse;Type. Une application crée toujours une sauvegarde datée.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import tempfile
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services.backup_storage import backup_file  # noqa: E402


def _instrument_type(section: str) -> str:
    value = str(section).upper()
    return "Tracker/ETF" if "ETF" in value or "ETN" in value else "Action"


def load_jpx_rows(path: Path) -> list[tuple[str, str, str, str]]:
    import pandas as pd

    frame = pd.read_excel(path, engine="calamine")
    required = {"Local Code", "Name (English)", "Section/Products"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"colonnes JPX absentes: {sorted(missing)}")
    rows: list[tuple[str, str, str, str]] = []
    seen: set[str] = set()
    for _, raw in frame.iterrows():
        code = str(raw.get("Local Code") or "").strip().upper()
        if not code or code.casefold() == "nan":
            continue
        ticker = f"{code}.T"
        if ticker in seen:
            continue
        seen.add(ticker)
        name = str(raw.get("Name (English)") or "").strip()
        section = str(raw.get("Section/Products") or "").strip()
        rows.append((
            ticker,
            "" if name.casefold() == "nan" else name,
            f"Tokyo Stock Exchange ({section})",
            _instrument_type(section),
        ))
    return sorted(rows, key=lambda row: row[0])


def merge_jpx_catalog(
    current_payload: bytes,
    official_rows: list[tuple[str, str, str, str]],
) -> tuple[bytes, dict]:
    text = current_payload.decode("utf-8-sig", errors="strict")
    retained: OrderedDict[str, tuple[str, str, str, str]] = OrderedDict()
    old_tokyo: set[str] = set()
    duplicate_non_tokyo: set[str] = set()
    for raw in csv.reader(io.StringIO(text), delimiter=";"):
        if not raw or not any(str(cell).strip() for cell in raw):
            continue
        values = [str(cell).strip() for cell in raw]
        values.extend([""] * (4 - len(values)))
        ticker = values[0].upper()
        if ticker.endswith(".T"):
            old_tokyo.add(ticker)
            continue
        candidate = (ticker, values[1], values[2], values[3])
        previous = retained.get(ticker)
        if previous is None:
            retained[ticker] = candidate
        else:
            duplicate_non_tokyo.add(ticker)
            if sum(map(len, candidate[1:])) > sum(map(len, previous[1:])):
                retained[ticker] = candidate

    official = OrderedDict((row[0], row) for row in official_rows)
    merged = [*retained.values(), *official.values()]
    output = io.StringIO(newline="")
    csv.writer(output, delimiter=";", lineterminator="\n").writerows(merged)
    report = {
        "rows_before": len([line for line in text.splitlines() if line.strip()]),
        "rows_after": len(merged),
        "tokyo_generated_before": len(old_tokyo),
        "tokyo_official_after": len(official),
        "tokyo_removed_not_listed": len(old_tokyo - set(official)),
        "tokyo_added_official": len(set(official) - old_tokyo),
        "duplicate_non_tokyo_removed": sorted(duplicate_non_tokyo),
        "etf_etn": sum(row[3] == "Tracker/ETF" for row in official.values()),
        "actions_and_other": sum(row[3] == "Action" for row in official.values()),
    }
    return output.getvalue().encode("utf-8"), report


def apply_import(tickers: Path, official: Path, report_path: Path) -> tuple[Path, dict]:
    payload, report = merge_jpx_catalog(tickers.read_bytes(), load_jpx_rows(official))
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backup_file(
        tickers,
        category="maintenance/import_jpx_tickers",
        filename=f"{tickers.name}.bak-jpx-{timestamp}",
    )
    fd, temp_name = tempfile.mkstemp(prefix=".tickers-jpx-", dir=tickers.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, tickers)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    report = {
        **report,
        "source": str(official.resolve()),
        "target": str(tickers.resolve()),
        "backup": str(backup.resolve()),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return backup, report


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--tickers", type=Path, required=True)
    parser.add_argument("--official", type=Path, required=True)
    parser.add_argument("--report-json", type=Path, required=True)
    args = parser.parse_args()
    if args.dry_run:
        _, report = merge_jpx_catalog(
            args.tickers.read_bytes(), load_jpx_rows(args.official)
        )
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    else:
        _, report = apply_import(args.tickers, args.official, args.report_json)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
