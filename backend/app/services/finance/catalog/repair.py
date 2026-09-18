"""Réparation déterministe du CSV legacy avant reconstruction officielle."""

from __future__ import annotations

import csv
import io
import json
import os
import re
import tempfile
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from app.services.backup_storage import backup_file

_REPEATED_SUFFIX = re.compile(r"(\.[A-Z]{1,5})\1$", re.IGNORECASE)


def normalize_repeated_suffix(symbol: str) -> str:
    value = symbol.strip().upper()
    while _REPEATED_SUFFIX.search(value):
        value = _REPEATED_SUFFIX.sub(r"\1", value)
    return value


def repair_legacy_tickers(
    source: Path,
    *,
    broker_path: Path | None = None,
) -> tuple[bytes, dict]:
    payload = source.read_bytes()
    text = payload.decode("utf-8-sig", errors="replace")
    broker_names: dict[str, str] = {}
    if broker_path and broker_path.exists():
        import pandas as pd

        frame = pd.read_excel(
            broker_path,
            usecols=lambda c: str(c) in {"Ticker Yahoo Finance", "Ticker", "Nom"},
        )
        ticker_column = next(
            (c for c in frame.columns if str(c) in {"Ticker Yahoo Finance", "Ticker"}),
            None,
        )
        if ticker_column is not None and "Nom" in frame.columns:
            broker_names = {
                str(ticker).strip().upper(): str(name).strip()
                for ticker, name in zip(
                    frame[ticker_column], frame["Nom"], strict=True
                )
                if pd.notna(ticker) and pd.notna(name)
            }

    normalized: OrderedDict[str, list[str]] = OrderedDict()
    suffix_fixes: list[dict] = []
    duplicate_symbols: set[str] = set()
    restored_names: list[str] = []
    unresolved_names: list[str] = []
    invalid_rows: list[int] = []
    for line_number, row in enumerate(csv.reader(io.StringIO(text), delimiter=";"), 1):
        if not row or not any(cell.strip() for cell in row):
            continue
        if len(row) < 4:
            invalid_rows.append(line_number)
            continue
        original = row[0].strip().upper()
        ticker = normalize_repeated_suffix(original)
        if ticker != original:
            suffix_fixes.append({"from": original, "to": ticker})
        name = row[1].strip()
        if "\ufffd" in name or any("\x80" <= char <= "\x9f" for char in name):
            replacement = broker_names.get(ticker) or broker_names.get(original)
            if replacement:
                name = replacement
                restored_names.append(ticker)
            else:
                # Le nom n'intervient ni dans l'identité ni dans le scoring.
                # On garde une chaîne UTF-8 lisible et on expose le cas dans le
                # rapport pour correction ultérieure depuis la source officielle.
                name = "".join(
                    char for char in name
                    if char != "\ufffd" and not "\x80" <= char <= "\x9f"
                ).strip()
                unresolved_names.append(ticker)
        candidate = [ticker, name, row[2].strip(), row[3].strip()]
        if ticker in normalized:
            duplicate_symbols.add(ticker)
            current = normalized[ticker]
            # Conserver la description la plus informative sans changer
            # l'ordre stable de l'univers.
            if len(candidate[1]) > len(current[1]):
                normalized[ticker] = candidate
        else:
            normalized[ticker] = candidate

    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";", lineterminator="\n")
    writer.writerows(normalized.values())
    encoded = output.getvalue().encode("utf-8")
    report = {
        "source": str(source.resolve()),
        "rows_before": len(text.splitlines()),
        "rows_after": len(normalized),
        "encoding_replacements_before": text.count("\ufffd"),
        "suffix_fixes": suffix_fixes,
        "duplicate_symbols": sorted(duplicate_symbols),
        "restored_names": sorted(set(restored_names)),
        "unresolved_names": sorted(set(unresolved_names)),
        "invalid_rows": invalid_rows,
    }
    return encoded, report


def apply_repair(
    source: Path,
    *,
    broker_path: Path | None,
    report_path: Path,
) -> tuple[Path, dict]:
    payload, report = repair_legacy_tickers(source, broker_path=broker_path)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backup_file(
        source,
        category="runtime/finance-catalog",
        filename=f"{source.name}.bak-repair-{timestamp}",
    )
    fd, temp_name = tempfile.mkstemp(prefix=".tickers-repair-", dir=source.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, source)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    report = {**report, "backup": str(backup.resolve())}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return backup, report
