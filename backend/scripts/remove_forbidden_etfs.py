"""Retire atomiquement de tickers.csv les ETF inverses ou à effet de levier."""

from __future__ import annotations

import csv
import os
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.finance.buffett.config import Config  # noqa: E402
from app.services.finance.buffett.leverage_filter import is_leveraged_product  # noqa: E402


def main() -> None:
    target = Path(Config.TICKERS_CSV).resolve()
    rows: list[list[str]] = []
    removed: list[str] = []
    with target.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.reader(stream, delimiter=";"):
            name = row[1] if len(row) > 1 else ""
            instrument_type = row[3] if len(row) > 3 else ""
            if instrument_type.strip().casefold() == "etf" and is_leveraged_product(name):
                if row:
                    removed.append(row[0].strip().upper())
                continue
            rows.append(row)

    handle, temporary_name = tempfile.mkstemp(
        prefix="tickers-filtered-", suffix=".csv", dir=target.parent,
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            csv.writer(stream, delimiter=";", lineterminator="\n").writerows(rows)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    print({"kept": len(rows), "removed": len(removed), "sample": removed[:20]})


if __name__ == "__main__":
    main()
