"""Source de cours avec cache quotidien.

Évite de refrapper yfinance à chaque chargement de portefeuille : un cours est
récupéré au plus une fois par jour et par ticker, en un appel groupé. Si la
récupération échoue, on conserve le dernier cours connu (utile hors-ligne).
"""

from __future__ import annotations

import datetime as dt
import threading
import time
from collections.abc import Callable, Iterable

# ticker -> (date du cours, prix)
_cache: dict[str, tuple[dt.date, float]] = {}
# Cache NEGATIF : ticker -> epoch du dernier fetch en echec. Sans lui, un ticker
# invalide (delisted, symbole sans suffixe .PA...) etait re-telecharge a CHAQUE
# appel (fast_info + history 1y + history 5d, avec retries yfinance), derriere
# le throttle global Yahoo -- famine des endpoints interactifs (#ECONNRESET sur
# /finance/state pendant un run Buffett) et spam de logs "possibly delisted".
_failed: dict[str, float] = {}
NEG_RETRY_S = 3600.0  # re-tenter un ticker en echec au plus 1x/heure
_lock = threading.Lock()


def _now() -> float:  # injectable dans les tests
    return time.time()


def _analysis_running() -> bool:
    """Vrai si une analyse Buffett tourne dans ce process. Pendant un run, le
    throttle global Yahoo est saturé par les workers de scoring : un fetch live
    interactif ferait la queue plusieurs minutes -> proxy Next "socket hang up"
    (#ECONNRESET sur /finance/state). On sert alors le dernier cours connu."""
    try:
        from app.services.finance.scheduler_stub import is_analysis_running
        return is_analysis_running()
    except Exception:
        return False


def _default_fetch(tickers: list[str]) -> dict[str, float]:
    """Derniers cours via yfinance (appel groupé)."""
    out: dict[str, float] = {}
    if not tickers:
        return out
    try:
        import yfinance as yf

        from app.services.finance.yf_session import fast_last_price, yf_session
        data = yf.Tickers(" ".join(tickers), session=yf_session())
        for t in tickers:
            try:
                out[t] = fast_last_price(data.tickers[t])
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
    now = _now()
    analysis = _analysis_running()
    with _lock:
        for t in ordered:
            entry = _cache.get(t)
            if entry and entry[0] == today:
                result[t] = entry[1]
            elif analysis or now - _failed.get(t, float("-inf")) < NEG_RETRY_S:
                # Analyse en cours OU echec recent -> ne PAS re-frapper yfinance,
                # servir le dernier cours connu (meme d'un jour precedent)
                result[t] = _cache[t][1] if t in _cache else 0.0
            else:
                stale.append(t)

    if stale:
        fetched = fetch(stale) or {}
        with _lock:
            for t in stale:
                price = float(fetched.get(t, 0) or 0)
                if price > 0:
                    _cache[t] = (today, price)
                    _failed.pop(t, None)
                    result[t] = price
                else:
                    _failed[t] = now
                    result[t] = _cache[t][1] if t in _cache else 0.0
    return result


def get_price(ticker: str, **kwargs) -> float:
    """Cours du jour pour un seul ticker."""
    return get_prices([ticker], **kwargs).get(ticker, 0.0)


def clear_cache() -> None:
    """Vide le cache (tests / rafraîchissement forcé)."""
    with _lock:
        _cache.clear()
        _failed.clear()
