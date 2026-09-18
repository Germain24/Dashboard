"""Importe les ISIN des ETF non-US (Europe + Asie) depuis la source bulk.

Le fichier ``core_listings.csv`` du dépôt ``adanos-software/free-ticker-database``
répertorie ~61 700 titres mondiaux avec leur ISIN. Le connecteur ``import_us_etf_isins``
en extrait déjà les ETF US (``country_code == "US"``) ; celui-ci couvre le
complément : les ETF domiciliés hors US (IE/LU/DE/FR/GB/JP/CN/…), cotés sur les
places européennes et asiatiques.

Résolution volontairement CONSERVATRICE : seul le couple ``(exchange, ticker)``
exact de la source est retenu (jamais de correspondance par nom, trop sujette aux
collisions cross-marché — ex. « Global X Semiconductor ETF » existe en Australie,
au Canada et au Japon avec des ISIN distincts). Un couple qui porterait plusieurs
ISIN dans la source est écarté (aucune valeur inventée).

La sortie ``nonus_etf_isins.json`` est lue par ``_nonus_etf_isins`` dans
``etf_index_registry``, qui résout ainsi l'ISIN des ETF non-US à ticker suffixé
(``.T``, ``.SZ``, ``.L``, ``.PA``, …).

Usage :
    ..\\.venv\\Scripts\\python.exe scripts\\import_nonus_etf_isins.py [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import datetime
import io
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.finance.buffett.config import Config
from app.services.finance.buffett.etf_index_registry import (
    DEFAULT_REGISTRY_PATH,
    _norm_isin,
    load_registry,
)

# Suffixe de place Yahoo -> exchange de la source bulk (``core_listings.csv``).
# Un seul suffixe par place, sauf les places multi-listings qui partagent un
# exchange unique dans la source (Euronext regroupe Paris/Milan/Bruxelles/Lisbonne,
# FSX regroupe Francfort/Düsseldorf). La base du ticker lève l'ambiguïté : on ne
# résout jamais un suffixe vers plusieurs exchange à la fois, mais plusieurs
# suffixex vers un même exchange.
SUFFIX_TO_EXCHANGE = {
    # Europe
    "L": "LSE",
    "PA": "EURONEXT",
    "MI": "EURONEXT",
    "BR": "EURONEXT",
    "LS": "EURONEXT",
    "IR": "EURONEXT",
    "AS": "AMS",
    "SW": "SIX",
    "DE": "XETRA",
    "F": "FSX",
    "DU": "FSX",
    "MC": "BME",
    "OL": "OSL",
    "CO": "CPH",
    "HE": "HEL",
    "ST": "STO",
    # Asie / Océanie
    "SZ": "SZSE",
    "T": "TSE",
    "NS": "NSE_IN",
    "TO": "TSX",
    "SG": "SGX",
    "KS": "KRX",
    "HK": "HKEX",
    "TW": "TWSE",
    "TWO": "TPEX",
}


def _source_rows(cache: Path) -> list[dict]:
    """Lit le cache ``core_listings.csv`` (déjà téléchargé par le connecteur US)."""
    text = cache.read_text(encoding="utf-8", errors="replace")
    return list(csv.DictReader(io.StringIO(text)))


def _build_exchange_ticker(rows: list[dict]) -> dict[tuple[str, str], str]:
    """(exchange, ticker) -> ISIN unique, pour les ETF non-US à ISIN valide."""
    by_key: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in rows:
        if str(row.get("asset_type") or "").strip().upper() != "ETF":
            continue
        if str(row.get("country_code") or "").strip().upper() == "US":
            continue
        isin = _norm_isin(row.get("isin"))
        exchange = str(row.get("exchange") or "").strip().upper()
        ticker = str(row.get("ticker") or "").strip().upper()
        if isin and exchange and ticker:
            by_key[(exchange, ticker)].add(isin)
    return {
        key: next(iter(values))
        for key, values in by_key.items()
        if len(values) == 1
    }


def collect_targets(registry: dict) -> dict[str, str]:
    """Ticker Yahoo (complet, suffixé) -> nom, pour les fonds non-US à ISIN vide.

    On ne filtre pas sur le statut d'enrichissement : un ticker déjà résolu dans le
    registre n'est simplement pas à ISIN vide, donc exclu par construction. Le
    connecteur reste ainsi reproductible indépendamment de l'état du registre.
    """
    funds = registry.get("funds", {})
    targets: dict[str, str] = {}
    for _identity, fund in funds.items():
        if not isinstance(fund, dict):
            continue
        if _norm_isin(fund.get("isin")):
            continue
        for ticker in (fund.get("tickers") or []):
            ticker = str(ticker).strip().upper()
            if not ticker or "." not in ticker:
                continue
            suffix = ticker.rsplit(".", 1)[1]
            if suffix in SUFFIX_TO_EXCHANGE:
                targets[ticker] = str(fund.get("name") or "")
    return targets


def resolve(targets: dict[str, str], exchange_ticker: dict[tuple[str, str], str]) -> dict[str, str]:
    """Résout l'ISIN de chaque ticker cible, uniquement par couple (exchange, ticker)."""
    resolved: dict[str, str] = {}
    for ticker in sorted(targets):
        base = ticker.rsplit(".", 1)[0]
        suffix = ticker.rsplit(".", 1)[1]
        # L'ISIN lisible dans le ticker lui-même (ex. "IE00BN4Q1675.SG") est la
        # source la plus fiable ; il est déjà géré par ``resolve_index_registry``
        # (``ticker_embedded_isin``), mais on le publie aussi ici pour que le
        # fichier soit exhaustif.
        embedded = _norm_isin(base)
        if embedded:
            resolved[ticker] = embedded
            continue
        exchange = SUFFIX_TO_EXCHANGE.get(suffix)
        if not exchange:
            continue
        isin = exchange_ticker.get((exchange, base))
        if isin:
            resolved[ticker] = isin
    return resolved


def synchronize(resolved: dict[str, str], out: Path) -> dict:
    variables = Path(Config.TICKERS_CSV).parent
    out = out or variables / "nonus_etf_isins.json"

    # Fusion : les ISIN résolus lors d'une passe précédente sont conservés, même
    # si leur ticker n'est plus une cible (déjà résolu au registre). Sans quoi une
    # passe partielle écraserait le mapping complet.
    existing: dict[str, str] = {}
    if out.exists():
        try:
            payload = json.loads(out.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("etfs"), dict):
                existing = {k: v for k, v in payload["etfs"].items()}
        except (OSError, ValueError, TypeError):
            existing = {}
    existing.update(resolved)
    payload = {
        "source": "free-ticker-database core_listings.csv (ETF non-US)",
        "generated_at": datetime.date.today().isoformat(),
        "etf_count": len(existing),
        "etfs": existing,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"output": str(out), "resolved": len(resolved), "total": len(existing)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--cache", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    variables = Path(Config.TICKERS_CSV).parent
    cache = args.cache or variables / "us_etf_core_listings.csv"
    registry = load_registry(DEFAULT_REGISTRY_PATH)

    rows = _source_rows(cache)
    exchange_ticker = _build_exchange_ticker(rows)
    targets = collect_targets(registry)
    resolved = resolve(targets, exchange_ticker)

    print(f"fonds non-US à ISIN vide : {len(targets)}")
    print(f"résolus par (exchange, ticker) : {len(resolved)}")

    if args.dry_run:
        for ticker in sorted(resolved):
            print(f"  {ticker} -> {resolved[ticker]}")
        return

    print(json.dumps(synchronize(resolved, args.out), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
