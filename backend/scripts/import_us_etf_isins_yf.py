"""Repli yfinance pour les ISIN des ETF US absents de la source bulk.

La source bulk ``free-ticker-database`` (connecteur ``import_us_etf_isins``)
couvre ~90 % des ETF US ; les ~10 % restants (fonds récents/petits, crypto,
ETF structurés) en sont absents. Ce script interroge l'ISIN via yfinance
(``yf.Ticker(t).isin``, endpoint BusinessInsider) pour ces tickers, et ne
conserve que les valeurs valides (préfixe US + somme Luhn).

La sortie ``us_etf_isins_yf.json`` est lue par ``_us_etf_isins`` en repli, APRÈS
la source bulk (qui prime). Elle est donc sans risque de collision.

Usage :
    ..\\.venv\\Scripts\\python.exe scripts\\import_us_etf_isins_yf.py [--dry-run]
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.finance.buffett.etf_index_registry import (
    DEFAULT_REGISTRY_PATH,
    _norm_isin,
    _read_us_isins_file,
    load_registry,
)

_DELAY_S = 0.35


def collect_targets(registry: dict, bulk_isins: dict[str, str]) -> list[str]:
    """Tous les tickers US nus du registre absents de la source bulk.

    On ne filtre pas sur le statut d'enrichissement : un ticker déjà résolu dans
    le registre (enregistrement ``ISIN:US...``) doit rester éligible pour que le
    repli yfinance reste reproductible indépendamment de l'état du registre.
    """
    funds = registry.get("funds", {})
    targets: set[str] = set()
    for _identity, fund in funds.items():
        if not isinstance(fund, dict):
            continue
        for ticker in (fund.get("tickers") or []):
            ticker = str(ticker).strip().upper()
            if not ticker or "." in ticker or ticker in bulk_isins:
                continue
            targets.add(ticker)
    return sorted(targets)


def resolve_yf_isins(tickers: list[str], delay: float = _DELAY_S) -> dict[str, str]:
    import yfinance as yf

    result: dict[str, str] = {}
    for ticker in tickers:
        try:
            raw = yf.Ticker(ticker).isin
        except Exception:
            raw = ""
        isin = _norm_isin(raw)
        if isin.startswith("US"):
            result[ticker] = isin
        if delay:
            time.sleep(delay)
    return result


def synchronize(tickers: list[str], out: Path) -> dict:
    from app.services.finance.buffett.config import Config

    variables = Path(Config.TICKERS_CSV).parent
    out = out or variables / "us_etf_isins_yf.json"

    resolved = resolve_yf_isins(tickers)
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
        "source": "yfinance/BusinessInsider (repli des tickers absents de la source bulk)",
        "generated_at": datetime.date.today().isoformat(),
        "etf_count": len(existing),
        "etfs": existing,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"output": str(out), "requested": len(tickers), "resolved": len(resolved), "total": len(existing)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    registry = load_registry(DEFAULT_REGISTRY_PATH)
    # Cible = tickers absents de la SEULE source bulk (pas du repli yfinance, sinon
    # on exclurait à tort des tickers déjà résolus lors d'une précédente passe).
    bulk_isins = _read_us_isins_file("us_etf_isins.json")
    targets = collect_targets(registry, bulk_isins)
    if args.limit:
        targets = targets[: args.limit]
    print(f"tickers à résoudre via yfinance : {len(targets)}")

    for ticker in targets:
        print("  ", ticker)

    result = synchronize(targets, args.out)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
