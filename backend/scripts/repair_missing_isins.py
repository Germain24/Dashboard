"""Répare les fonds dont le registre porte un ISIN absent.

Le registre conserve des fonds sans ISIN (``TICKER:…`` ou ``ISIN:`` vide) alors que
la résolution actuelle peut désormais les combler : catalogue broker, ISIN non-US
bulk (``nonus_etf_isins.json``), ISIN US dérivé de CUSIP, alias de registre, ou ISIN
lisible dans le ticker. Ce script ré-exécute ``resolve_index_registry`` sur les seuls
fonds concernés, sans toucher aux fonds déjà correctement résolus.

Usage :
    ..\\.venv\\Scripts\\python.exe scripts\\repair_missing_isins.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.finance.buffett.etf_index_registry import (
    DEFAULT_REGISTRY_PATH,
    _norm_isin,
    load_registry,
    resolve_index_registry,
    save_registry,
)


def prune_orphans(registry: dict) -> int:
    """Supprime les enregistrements devenus inertes (aucun ticker, aucune position).

    ``resolve_index_registry`` purge le ticker d'un ancien enregistrement quand un
    ISIN autoritaire l'emporte, mais laisse derrière lui une coquille vide. On ne
    supprime que les enregistrements sans ``tickers`` ET sans ``composition``.
    """
    funds = registry.get("funds", {})
    removed = 0
    for key in list(funds):
        record = funds.get(key)
        if not isinstance(record, dict):
            continue
        if record.get("tickers") or record.get("composition") or record.get("holdings"):
            continue
        del funds[key]
        removed += 1
    return removed


def prune_stale_ticker_records(registry: dict) -> int:
    """Supprime les anciens enregistrements ``TICKER:`` devenus doublons.

    ``resolve_index_registry`` purge le ticker d'un ancien enregistrement quand un
    ISIN autoritaire (référence manuelle ou ISIN US) l'emporte, mais pas quand
    l'ISIN est résolu par une source non-US (``broker_catalog``, ``nonus_bulk``,
    alias de registre). L'ancien enregistrement ``TICKER:`` à ISIN vide subsiste
    alors en doublon du nouvel enregistrement ``ISIN:``.

    On ne supprime que les enregistrements ``TICKER:`` sans ISIN, sans composition
    ni positions, et dont TOUS les tickers sont désormais résolus vers un
    enregistrement ``ISIN:``. Aucune perte : l'éventuel ``official_enrichment`` y
    est un échec ``missing_catalog_isin`` devenu obsolète (l'ISIN existe à présent)
    et l'``index_id`` est recalculé sur l'enregistrement ``ISIN:`` lors de la
    résolution.
    """
    funds = registry.get("funds", {})
    resolved_isin: dict[str, str] = {}
    for identity, fund in funds.items():
        if not isinstance(fund, dict) or not identity.startswith("ISIN:"):
            continue
        isin = _norm_isin(fund.get("isin"))
        if not isin:
            continue
        for ticker in (fund.get("tickers") or []):
            ticker = str(ticker).strip().upper()
            if ticker:
                resolved_isin[ticker] = isin

    removed = 0
    for identity in list(funds):
        if not identity.startswith("TICKER:"):
            continue
        fund = funds.get(identity)
        if not isinstance(fund, dict):
            continue
        if _norm_isin(fund.get("isin")):
            continue
        if fund.get("composition") or fund.get("holdings"):
            continue
        tickers = [str(t).strip().upper() for t in (fund.get("tickers") or []) if str(t).strip()]
        if not tickers:
            continue
        if all(t in resolved_isin for t in tickers):
            del funds[identity]
            removed += 1
    return removed


def collect_targets(registry: dict) -> list[str]:
    """Tous les tickers (nus ou suffixés) dont l'ISIN du registre est vide."""
    funds = registry.get("funds", {})
    targets: set[str] = set()
    for _identity, fund in funds.items():
        if not isinstance(fund, dict):
            continue
        if _norm_isin(fund.get("isin")):
            continue
        for ticker in (fund.get("tickers") or []):
            ticker = str(ticker).strip().upper()
            if ticker:
                targets.add(ticker)
    return sorted(targets)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    registry = load_registry(DEFAULT_REGISTRY_PATH)
    targets = collect_targets(registry)
    print(f"tickers à ISIN vide : {len(targets)}")

    if args.dry_run:
        for ticker in targets:
            print("  ", ticker)
        return

    results = resolve_index_registry(targets, path=DEFAULT_REGISTRY_PATH)
    by_source: dict[str, int] = {}
    for ticker in targets:
        source = str(results.get(ticker, {}).get("isin_source") or "missing")
        by_source[source] = by_source.get(source, 0) + 1
    print("résultats par source :", dict(sorted(by_source.items())))

    registry = load_registry(DEFAULT_REGISTRY_PATH)
    removed = prune_orphans(registry)
    removed_stale = prune_stale_ticker_records(registry)
    if removed or removed_stale:
        save_registry(registry, DEFAULT_REGISTRY_PATH)
    print(f"enregistrements orphelins supprimés : {removed}")
    print(f"enregistrements TICKER doublons supprimés : {removed_stale}")


if __name__ == "__main__":
    main()
