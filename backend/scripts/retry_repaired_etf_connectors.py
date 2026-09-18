"""Relance bornée des anciens échecs HSBC/Vanguard ; aucun ordre ni allocation.

Prévisualisation par défaut. --apply met uniquement à jour le cache officiel.
Les délais de reprise restent actifs pour les connecteurs déjà à jour.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.finance.buffett.etf_index_registry import load_registry
from app.services.finance.buffett.official_etf_enrichment import (
    _CONNECTOR_REVISIONS, _attempt_due, _issuer, enrich_official_etfs,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=24)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--retry-recent", action="store_true", help="Maintenance : retenter les échecs récents du lot borné")
    args = parser.parse_args()
    if not 1 <= args.limit <= 200:
        parser.error("--limit doit être compris entre 1 et 200")
    registry = load_registry()
    groups = {issuer: [] for issuer in _CONNECTOR_REVISIONS}
    for identity, fund in sorted(registry["funds"].items()):
        issuer = _issuer(fund.get("name", ""))
        status = fund.get("official_enrichment") or {}
        if issuer not in groups or not status or status.get("status") in {
            "complete", "complete_shared_index", "aggregate_complete", "non_equity",
        }:
            continue
        if not fund.get("isin") or not fund.get("tickers") or not _attempt_due(fund, args.retry_recent):
            continue
        groups[issuer].append({
            "identity": identity, "ticker": sorted(fund["tickers"])[0],
            "name": fund.get("name"), "isin": fund["isin"],
            "before": status.get("status"), "issuer": issuer,
        })
    selected = []
    for position in range(max((len(values) for values in groups.values()), default=0)):
        for values in groups.values():
            if position < len(values) and len(selected) < args.limit:
                selected.append(values[position])
    print(json.dumps({"apply": args.apply, "eligible": {k: len(v) for k, v in groups.items()}, "selected": selected}), flush=True)
    if not args.apply or not selected:
        return
    def progress(done, total, ticker):
        print(json.dumps({"done": done, "total": total, "ticker": ticker}), flush=True)
    results = enrich_official_etfs([row["ticker"] for row in selected], progress_cb=progress, force=args.retry_recent)
    for row in selected:
        print(json.dumps({**row, "after": results.get(row["ticker"], {})}), flush=True)
    print(json.dumps({"summary": dict(Counter(value.get("status", "unknown") for value in results.values()))}), flush=True)


if __name__ == "__main__":
    main()
