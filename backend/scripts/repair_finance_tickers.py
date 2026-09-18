"""Normalise le CSV ticker legacy avec sauvegarde et rapport JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.finance.catalog.repair import apply_repair, repair_legacy_tickers  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--tickers", type=Path, required=True)
    parser.add_argument("--broker", type=Path)
    parser.add_argument("--report-json", type=Path, required=True)
    args = parser.parse_args()
    if args.dry_run:
        _, report = repair_legacy_tickers(args.tickers, broker_path=args.broker)
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    else:
        _, report = apply_repair(
            args.tickers,
            broker_path=args.broker,
            report_path=args.report_json,
        )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
