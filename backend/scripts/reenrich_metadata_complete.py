"""Re-enrichissement ciblé des fonds ``metadata_complete`` physiques actions.

Les connecteurs Amundi/Invesco/Vanguard remontent désormais les positions
complètes, mais le registre conserve des statuts ``metadata_complete`` datés
(attente du retry de 7 jours). Ce script force la re-résolution des fonds
ciblés pour récupérer immédiatement les positions.

Usage :
    ..\\.venv\\Scripts\\python.exe scripts\\reenrich_metadata_complete.py [--dry-run] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.finance.buffett import official_etf_enrichment as enrich
from app.services.finance.buffett.etf_index_registry import (
    DEFAULT_REGISTRY_PATH,
    load_registry,
)

_BOND_KW = (
    "bloomberg", "gilt", "treasury", "aggregate", "corporate", "govt",
    "government", "sovereign", "inflation", "high yield", "overnight",
    "cash", "gold", "silver", "platinum", "palladium", "bitcoin",
    "ethereum", "crypto", "multi-asset", "the index",
)


def collect_targets(registry: dict) -> list[str]:
    """Tickerrs Yahoo des fonds physiques actions au statut metadata_complete."""
    funds = registry.get("funds", {})
    tickers: list[str] = []
    for _identity, fund in funds.items():
        if str(fund.get("replication") or "") != "physical":
            continue
        idx = str(fund.get("index_name") or "")
        if any(marker in idx.casefold() for marker in _BOND_KW):
            continue
        if (fund.get("official_enrichment") or {}).get("status") != "metadata_complete":
            continue
        for ticker in fund.get("tickers") or []:
            if ticker:
                tickers.append(ticker)
    return sorted(set(tickers))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    registry = load_registry(DEFAULT_REGISTRY_PATH)
    targets = collect_targets(registry)
    if args.limit:
        targets = targets[: args.limit]
    print(f"cibles metadata_complete physiques actions : {len(targets)}")

    if args.dry_run:
        for ticker in targets:
            print("  ", ticker)
        return

    results = enrich.enrich_official_etfs(
        targets, path=DEFAULT_REGISTRY_PATH, force=True
    )
    by_status: dict[str, int] = {}
    for ticker in targets:
        status = str(results.get(ticker, {}).get("status") or "missing")
        by_status[status] = by_status.get(status, 0) + 1
    print("résultats :", dict(sorted(by_status.items())))


if __name__ == "__main__":
    main()
