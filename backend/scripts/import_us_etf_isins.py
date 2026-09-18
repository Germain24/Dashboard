"""Importe les ISIN des ETF cotés aux États-Unis depuis une source libre.

Le fichier ``core_listings.csv`` du dépôt ``adanos-software/free-ticker-database``
répertorie ~61 700 titres mondiaux avec leur ISIN. On ne retient ici que les ETF
US (``asset_type == "ETF"`` et ``country_code == "US"``), dont l'ISIN est
revalidé par ``valid_isin`` avant publication. Un ticker qui porterait plusieurs
ISIN distincts dans la source est volontairement écarté (aucune valeur inventée).

La sortie ``us_etf_isins.json`` est lue par ``_us_etf_isins`` dans
``etf_index_registry``, qui résout ainsi l'ISIN des ETF US sans suffixe de place
et corrige les collisions cross-marché du catalogue broker (ex. SPY associé à un
fonds UCITS homonyme).
"""

from __future__ import annotations

import argparse
import csv
import datetime
import io
import json
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

DEFAULT_URL = (
    "https://raw.githubusercontent.com/adanos-software/"
    "free-ticker-database/main/data/core_listings.csv"
)
USER_AGENT = "Mozilla/5.0 (import_us_etf_isins; mission-control)"


def _download(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def _build(rows: list[dict]) -> tuple[dict[str, str], dict[str, list[str]], int]:
    """Extrait les ETF US à ISIN valide et unique par ticker."""
    from app.services.finance.buffett.etf_index_registry import valid_isin

    by_ticker: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if str(row.get("asset_type") or "").strip().upper() != "ETF":
            continue
        if str(row.get("country_code") or "").strip().upper() != "US":
            continue
        isin = valid_isin(row.get("isin"))
        ticker = str(row.get("ticker") or "").strip().upper()
        if isin and ticker:
            by_ticker[ticker].add(isin)

    etfs: dict[str, str] = {}
    conflicts: dict[str, list[str]] = {}
    for ticker, values in by_ticker.items():
        if len(values) == 1:
            etfs[ticker] = next(iter(values))
        else:
            conflicts[ticker] = sorted(values)
    return etfs, conflicts, len(rows)


def synchronize(*, url: str, refresh: bool, out: Path, cache: Path) -> dict:
    from app.services.finance.buffett.config import Config

    variables = Path(Config.TICKERS_CSV).parent
    out = out or variables / "us_etf_isins.json"
    cache = cache or variables / "us_etf_core_listings.csv"

    if refresh or not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        text = _download(url)
        cache.write_text(text, encoding="utf-8")
    else:
        text = cache.read_text(encoding="utf-8")

    rows = list(csv.DictReader(io.StringIO(text)))
    etfs, conflicts, total_rows = _build(rows)

    payload = {
        "source": url,
        "generated_at": datetime.date.today().isoformat(),
        "source_rows": total_rows,
        "us_etf_count": len(etfs),
        "etfs": etfs,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "output": str(out),
        "cache": str(cache),
        "source_rows": total_rows,
        "us_etf_count": len(etfs),
        "ambiguous_tickers": conflicts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--refresh", action="store_true", help="Force le re-téléchargement")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--cache", type=Path, default=None)
    args = parser.parse_args()
    print(json.dumps(
        synchronize(url=args.url, refresh=args.refresh, out=args.out, cache=args.cache),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
