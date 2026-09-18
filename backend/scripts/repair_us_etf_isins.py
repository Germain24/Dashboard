"""Répare les ISIN des ETF US à ticker nu dont le registre porte un ISIN erroné.

Le registre conserve encore, pour certains ETF US cotés sans suffixe de place
(ex. ``SPY``, ``GDX``), un ISIN non-US hérité d'une collision cross-marché
(SPY -> IE00B6YX5C33) ou un simple enregistrement sans ISIN (``TICKER:AAAU``).
La source bulk ``us_etf_isins.json`` (connecteur ``import_us_etf_isins``) fournit
l'ISIN US correct, dérivé du CUSIP.

Ce script ré-exécute ``resolve_index_registry`` sur les seuls tickers concernés :
la logique de résolution n'écrase jamais un ISIN US déjà valide du catalogue
broker (cas SQQQ/IAU), et purge le ticker de l'ancien enregistrement non-US.

Usage :
    ..\\.venv\\Scripts\\python.exe scripts\\repair_us_etf_isins.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.finance.buffett.etf_index_registry import (
    DEFAULT_REGISTRY_PATH,
    _norm_isin,
    _us_etf_isins,
    load_registry,
    resolve_index_registry,
    save_registry,
)


def prune_orphans(registry: dict) -> int:
    """Supprime les enregistrements devenus inertes (aucun ticker, aucune position).

    ``resolve_index_registry`` purge le ticker d'un ancien enregistrement quand un
    ISIN US autoritaire l'emporte, mais laisse derrière lui une coquille vide
    (ex. ``TICKER:AAA`` au statut ``missing_catalog_isin``, ou ``ISIN:IE00...``
    sans ticker). Ces coquilles faussent le décompte des ISIN manquants. On ne
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


def collect_targets(registry: dict, us_isins: dict[str, str]) -> list[str]:
    """Tickers US nus dont l'ISIN du registre est absent ou non-US."""
    funds = registry.get("funds", {})
    targets: set[str] = set()
    for _identity, fund in funds.items():
        if not isinstance(fund, dict):
            continue
        isin = _norm_isin(fund.get("isin"))
        for ticker in (fund.get("tickers") or []):
            ticker = str(ticker).strip().upper()
            if not ticker or "." in ticker:
                continue
            if ticker not in us_isins:
                continue
            if not isin or not isin.startswith("US"):
                targets.add(ticker)
    return sorted(targets)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    registry = load_registry(DEFAULT_REGISTRY_PATH)
    us_isins = _us_etf_isins()
    targets = collect_targets(registry, us_isins)
    print(f"tickers US à ISIN erroné/absent : {len(targets)}")

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
    if removed:
        save_registry(registry, DEFAULT_REGISTRY_PATH)
    print(f"enregistrements orphelins supprimés : {removed}")


if __name__ == "__main__":
    main()
