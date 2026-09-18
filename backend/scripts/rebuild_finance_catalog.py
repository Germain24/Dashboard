"""CLI: reconstruire le catalogue Finance depuis des exports officiels."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.finance.catalog.apply import apply_catalog  # noqa: E402
from app.services.finance.catalog.builder import CatalogBuilder, write_catalog_csv  # noqa: E402


def parse_source(value: str) -> tuple[str, Path, str, str]:
    parts = value.split(":", 3)
    if len(parts) < 3:
        raise argparse.ArgumentTypeError("format attendu MIC:CHEMIN:SOURCE[:TYPE]")
    mic, path, source, *kind = parts
    return mic, Path(path), source, kind[0] if kind else "EQUITY"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--source", action="append", type=parse_source, required=True)
    parser.add_argument("--input-dir", type=Path, default=Path.cwd())
    parser.add_argument("--report-json", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=Path("data/finance_catalog.csv"))
    parser.add_argument("--tickers", type=Path, default=Path("data/imports/Finances/variables/tickers.csv"))
    parser.add_argument("--broker", type=Path, default=Path("data/imports/Finances/tableur/ToutBroker.xlsx"))
    parser.add_argument("--database", type=Path, default=Path("data/mission-control.db"))
    parser.add_argument("--validate-yahoo", action="store_true")
    args = parser.parse_args(argv)

    builder = CatalogBuilder()
    for mic, source_path, source, kind in args.source:
        path = source_path if source_path.is_absolute() else args.input_dir / source_path
        builder.add_file(path, mic=mic, source=source, default_type=kind)
    entries = builder.build()
    old = []
    if args.tickers.exists():
        old = [line.split(";", 1)[0] for line in args.tickers.read_text(encoding="utf-8-sig").splitlines()]
    report = builder.report(old)
    if args.validate_yahoo:
        from app.services.finance.catalog.validation import validate_yahoo_symbols
        validated = validate_yahoo_symbols(entry.yahoo_symbol for entry in entries)
        report["unresolved_yahoo_symbols"] = sorted(
            symbol for symbol, valid in validated.items() if not valid
        )
    args.report_json.parent.mkdir(parents=True, exist_ok=True)
    args.report_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.dry_run:
        preview = args.report_json.with_suffix(".catalog.csv")
        write_catalog_csv(preview, entries)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    apply_catalog(
        entries,
        catalog_path=args.catalog,
        tickers_path=args.tickers,
        broker_path=args.broker,
        database=args.database,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
