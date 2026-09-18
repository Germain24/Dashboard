"""Référentiel ETF auditable, autoritaire sur les caches d'enrichissement.

Une ligne décrit un fonds par ISIN. Les tickers ne servent que de clés de
cotation : ils ne sont jamais autorisés à fusionner deux ISIN différents.
La composition reste stockée dans ``etf_index_registry`` par indice exact afin
d'être téléchargée une seule fois pour tous les fonds qui le suivent.
"""

from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import Config

DEFAULT_REFERENCE_PATH = Path(__file__).with_name("etf_reference.csv")


def _text(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.casefold() in {"", "nan", "none", "-"} else text


def _isin(value: Any) -> str:
    value = _text(value).upper().replace(" ", "")
    return value if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", value) else ""


@lru_cache(maxsize=8)
def load_etf_reference(path: str | Path | None = None) -> dict[str, dict[str, dict]]:
    """Retourne deux index indépendants ``by_isin`` et ``by_ticker``."""
    configured = Path(path or Config.ETF_REFERENCE_FILE)
    target = configured if configured.exists() else DEFAULT_REFERENCE_PATH
    by_isin: dict[str, dict] = {}
    by_ticker: dict[str, dict] = {}
    try:
        with target.open(encoding="utf-8-sig", newline="") as stream:
            rows = csv.DictReader(stream)
            for raw in rows:
                record = {str(key).strip(): _text(value) for key, value in raw.items()}
                isin = _isin(record.get("isin"))
                if not isin or record.get("verification_status") != "manual_verified":
                    continue
                record["isin"] = isin
                ticker = record.get("ticker", "").upper()
                record["ticker"] = ticker
                by_isin[isin] = record
                if ticker:
                    existing = by_ticker.get(ticker)
                    # Un ticker ambigu ne doit jamais choisir arbitrairement un ISIN.
                    by_ticker[ticker] = record if existing is None else {}
    except OSError:
        pass
    return {"by_isin": by_isin, "by_ticker": by_ticker}


def reference_for(*, isin: str = "", ticker: str = "", path=None) -> dict:
    reference = load_etf_reference(path)
    normalized_isin = _isin(isin)
    if normalized_isin and normalized_isin in reference["by_isin"]:
        return dict(reference["by_isin"][normalized_isin])
    return dict(reference["by_ticker"].get(_text(ticker).upper()) or {})


def clear_reference_cache() -> None:
    load_etf_reference.cache_clear()
