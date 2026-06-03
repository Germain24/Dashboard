"""Source de cours avec cache quotidien.

Évite de refrapper yfinance à chaque chargement de portefeuille : un cours est
récupéré au plus une fois par jour et par ticker, en un appel groupé. Si la
récupération échoue, on conserve le dernier cours connu (utile hors-ligne).
"""

from __future__ import annotations

import datetime as dt
import threading
from typing import Callable, Iterable

# ticker -> (date du cours, prix)
_cache: dict[str, tuple[dt.date, float]] = {}
_lock = threading.Lock()


def _default_fetch(tickers: list[str]) -> dict[str, float]:
    """Derniers cours via yfinance (appel groupé)."""
    out: dict[str, float] = {}
    if not tickers:
        return out
    try:
        import yfinance as yf
        data = yf.Tickers(" ".join(tickers))
        for t in tickers:
            try:
                out[t] = float(data.tickers[t].fast_info.get("last_price", 0) or 0)
            except Exception:
                out[t] = 0.0
    except Exception:
        pass
    return out


def get_prices(
    tickers: Iterable[str],
    *,
    fetcher: Callable[[list[str]], dict[str, float]] | None = None,
    today: dt.date | None = None,
) -> dict[str, float]:
    """Cours du jour pour ``tickers`` (cache quotidien, fetch groupé pour les manquants)."""
    today = today or dt.date.today()
    fetch = fetcher or _default_fetch
    ordered = [t for t in dict.fromkeys(tickers) if t]  # dédup en gardant l'ordre

    result: dict[str, float] = {}
    stale: list[str] = []
    with _lock:
        for t in ordered:
            entry = _cache.get(t)
            if entry and entry[0] == today:
                result[t] = entry[1]
            else:
                stale.append(t)

    if stale:
        fetched = fetch(stale) or {}
        with _lock:
            for t in stale:
                price = float(fetched.get(t, 0) or 0)
                if price > 0:
                    _cache[t] = (today, price)
                    result[t] = price
                elif t in _cache:
                    result[t] = _cache[t][1]  # fetch échoué -> dernier cours connu
                else:
                    result[t] = 0.0
    return result


def get_price(ticker: str, **kwargs) -> float:
    """Cours du jour pour un seul ticker."""
    return get_prices([ticker], **kwargs).get(ticker, 0.0)


def clear_cache() -> None:
    """Vide le cache (tests / rafraîchissement forcé)."""
    with _lock:
        _cache.clear()
