"""Application atomique d'un catalogue, interdite pendant un run Buffett."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from app.services.backup_storage import backup_file
from .builder import CatalogEntry, write_catalog_csv, write_legacy_tickers


def assert_no_active_run(database: Path) -> None:
    if not database.exists():
        return
    con = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        row = con.execute(
            "select id from buffett_run where statut in ('en_cours', 'interrompu') "
            "order by id desc limit 1"
        ).fetchone()
    finally:
        con.close()
    if row:
        raise RuntimeError(
            f"application refusée: le run Buffett #{row[0]} doit être terminé et archivé"
        )


def apply_catalog(
    entries: list[CatalogEntry],
    *,
    catalog_path: Path,
    tickers_path: Path,
    broker_path: Path | None,
    database: Path,
) -> list[Path]:
    assert_no_active_run(database)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backups: list[Path] = []
    for target in (catalog_path, tickers_path, broker_path):
        if target and target.exists():
            backup = backup_file(
                target,
                category="runtime/finance-catalog",
                filename=f"{target.name}.bak-{timestamp}",
            )
            backups.append(backup)

    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=catalog_path.parent) as temp_dir:
        temp = Path(temp_dir)
        next_catalog = temp / catalog_path.name
        next_tickers = temp / tickers_path.name
        write_catalog_csv(next_catalog, entries)
        write_legacy_tickers(next_tickers, entries)
        os.replace(next_catalog, catalog_path)
        os.replace(next_tickers, tickers_path)

    if broker_path and broker_path.exists():
        import pandas as pd

        sheets = pd.read_excel(broker_path, sheet_name=None)
        main_name = next(iter(sheets))
        current = sheets[main_name]
        ticker_column = next(
            (
                c
                for c in current.columns
                if str(c).strip().casefold()
                in {
                    "ticker",
                    "symbole",
                    "ticker yahoo",
                    "ticker yahoo finance",
                    "yahoo symbol",
                }
            ),
            "Ticker Yahoo Finance",
        )
        base = pd.DataFrame({
            ticker_column: [entry.yahoo_symbol for entry in entries],
            "Nom": [entry.name for entry in entries],
            "MIC": [entry.mic for entry in entries],
            "ISIN": [entry.isin for entry in entries],
            "Type": [entry.instrument_type for entry in entries],
            "Primary Market": [entry.primary_market for entry in entries],
            "Primary MIC": [entry.primary_mic for entry in entries],
            "Fundamentals Symbol": [entry.fundamentals_symbol for entry in entries],
        })
        broker_columns = [c for c in current.columns if c not in base.columns]
        if ticker_column in current.columns:
            base = base.merge(current[[ticker_column, *broker_columns]], on=ticker_column, how="left")
        temp_xlsx = broker_path.with_name(f".{broker_path.name}.{timestamp}.tmp.xlsx")
        with pd.ExcelWriter(temp_xlsx, engine="openpyxl") as writer:
            base.to_excel(writer, sheet_name=main_name, index=False)
            for name, frame in list(sheets.items())[1:]:
                frame.to_excel(writer, sheet_name=name, index=False)
        os.replace(temp_xlsx, broker_path)
    return backups
