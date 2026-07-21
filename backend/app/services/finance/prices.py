"""Source de cours avec cache quotidien.

Évite de refrapper yfinance à chaque chargement de portefeuille : un cours est
récupéré au plus une fois par jour et par ticker, en un appel groupé. Si la
récupération échoue, on conserve le dernier cours connu (utile hors-ligne).
"""

from __future__ import annotations

import datetime as dt
import json
import threading
import time
from collections.abc import Callable, Iterable
from pathlib import Path

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
_refreshing: set[str] = set()
_disk_loaded = False
_PRICE_CACHE_FILE = Path(__file__).resolve().parents[4] / "data" / "cache" / "latest_prices.json"


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


def load_disk_cache() -> None:
    """Recharge les derniers cours connus une seule fois par process."""
    global _disk_loaded
    with _lock:
        if _disk_loaded:
            return
        _disk_loaded = True
    try:
        raw = json.loads(_PRICE_CACHE_FILE.read_text(encoding="utf-8"))
        loaded = {
            ticker: (dt.date.fromisoformat(day), float(price))
            for ticker, (day, price) in raw.items()
            if float(price) > 0
        }
        with _lock:
            for ticker, entry in loaded.items():
                _cache.setdefault(ticker, entry)
    except Exception:
        pass


def save_disk_cache() -> None:
    """Persiste les cours réels pour survivre aux redémarrages du backend."""
    try:
        with _lock:
            data = {
                ticker: (day.isoformat(), price)
                for ticker, (day, price) in _cache.items()
                if price > 0
            }
        _PRICE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _PRICE_CACHE_FILE.write_text(
            json.dumps(data, indent=1, sort_keys=True), encoding="utf-8"
        )
    except Exception:
        pass


def _store_fetched(
    tickers: list[str], fetched: dict[str, float], today: dt.date, *, persist: bool
) -> dict[str, float]:
    result: dict[str, float] = {}
    now = _now()
    changed = False
    with _lock:
        for ticker in tickers:
            price = float(fetched.get(ticker, 0) or 0)
            if price > 0:
                _cache[ticker] = (today, price)
                _failed.pop(ticker, None)
                result[ticker] = price
                changed = True
            else:
                _failed[ticker] = now
                result[ticker] = _cache[ticker][1] if ticker in _cache else 0.0
    if persist and changed:
        save_disk_cache()
    return result


def _refresh_prices(tickers: list[str], today: dt.date) -> None:
    try:
        refreshed = _store_fetched(
            tickers, _default_fetch(tickers) or {}, today, persist=True
        )
        if any(price > 0 for price in refreshed.values()):
            # L'état portefeuille peut avoir été calculé avec 0 ou un cours
            # périmé pendant ce fetch. Le polling UI doit voir le nouveau cours
            # immédiatement, sans attendre les cinq minutes de son propre TTL.
            from app.services.finance.portfolio_state import invalidate_state

            invalidate_state()
    finally:
        with _lock:
            _refreshing.difference_update(tickers)


def _schedule_refresh(tickers: list[str], today: dt.date) -> None:
    with _lock:
        pending = [ticker for ticker in tickers if ticker not in _refreshing]
        _refreshing.update(pending)
    if pending:
        threading.Thread(
            target=_refresh_prices,
            args=(pending, today),
            name="finance-price-refresh",
            daemon=True,
        ).start()


def get_prices(
    tickers: Iterable[str],
    *,
    fetcher: Callable[[list[str]], dict[str, float]] | None = None,
    today: dt.date | None = None,
    stale_ok: bool = False,
) -> dict[str, float]:
    """Cours du jour pour ``tickers``.

    ``stale_ok=True`` sert immédiatement le dernier cours persistant et lance
    l'actualisation réelle en arrière-plan. Ce mode est réservé aux vues
    interactives; les snapshots conservent le comportement synchrone précis.
    """
    today = today or dt.date.today()
    use_default_fetcher = fetcher is None
    if use_default_fetcher:
        load_disk_cache()
    fetch = fetcher or _default_fetch
    ordered = [t for t in dict.fromkeys(tickers) if t]  # dédup en gardant l'ordre

    result: dict[str, float] = {}
    stale: list[str] = []
    refresh: list[str] = []
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
            elif stale_ok and use_default_fetcher:
                result[t] = _cache[t][1] if t in _cache else 0.0
                refresh.append(t)
            else:
                stale.append(t)

    if refresh:
        _schedule_refresh(refresh, today)
    if stale:
        fetched = fetch(stale) or {}
        result.update(
            _store_fetched(stale, fetched, today, persist=use_default_fetcher)
        )
    return result


def get_price(ticker: str, **kwargs) -> float:
    """Cours du jour pour un seul ticker."""
    return get_prices([ticker], **kwargs).get(ticker, 0.0)


def clear_cache() -> None:
    """Vide le cache (tests / rafraîchissement forcé)."""
    global _disk_loaded
    with _lock:
        _cache.clear()
        _failed.clear()
        _disk_loaded = False
