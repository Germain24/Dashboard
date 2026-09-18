"""Audit local des indices sous licence récupérables via un tracker physique."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.finance.buffett.etf_index_registry import (
    _composition_with_holdings,
    _registry_target,
    canonical_constituent_set_id,
    load_registry,
)


def main() -> None:
    database = Path(__file__).resolve().parents[2] / "data" / "mission-control.db"
    with sqlite3.connect(database) as connection:
        raw = connection.execute(
            "SELECT params_json FROM buffett_run WHERE id = 62"
        ).fetchone()
    params = json.loads(raw[0]) if raw else {}
    unresolved = (
        (((params.get("optimization") or {}).get("economic_composition_filter") or {})
         .get("index_resolution") or {}).get("unresolved") or []
    )
    licensed = {
        str(value.get("index_id") or "")
        for value in unresolved
        if value.get("status") == "licence_required" and value.get("index_id")
    }

    registry = load_registry()
    target = _registry_target(registry.get("_storage_path"))
    exact: dict[str, list[dict]] = {}
    canonical: dict[str, list[dict]] = {}
    for identity, fund in registry.get("funds", {}).items():
        composition = _composition_with_holdings(fund.get("composition"), target)
        if not (
            fund.get("replication") == "physical"
            and composition.get("holdings")
            and composition.get("source") == "issuer_fund_holdings"
            and float(composition.get("coverage") or 0.0) >= 0.90
        ):
            continue
        candidate = {
            "identity": identity,
            "ticker": str((fund.get("tickers") or [""])[0]),
            "holdings": len(composition.get("holdings") or []),
            "coverage": float(composition.get("coverage") or 0.0),
            "source_url": str(composition.get("source_url") or ""),
        }
        index_id = str(fund.get("index_id") or "")
        exact.setdefault(index_id, []).append(candidate)
        canonical.setdefault(
            canonical_constituent_set_id(fund.get("index_name") or ""), []
        ).append(candidate)

    matches: dict[str, list[dict]] = {}
    for index_id in licensed:
        index_name = str(
            (registry.get("indices", {}).get(index_id, {}) or {}).get("name")
            or index_id
        )
        candidates = exact.get(index_id) or canonical.get(
            canonical_constituent_set_id(index_name), []
        )
        if candidates:
            matches[index_id] = candidates

    print(json.dumps({
        "licensed_unique_indices": len(licensed),
        "matched_with_physical_tracker": len(matches),
        "candidate_trackers": sum(len(value) for value in matches.values()),
        "matches": matches,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
