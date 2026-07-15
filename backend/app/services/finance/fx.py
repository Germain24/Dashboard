"""Taux de change avec cache quotidien (conversion au taux du jour).

Comme pour les cours (prices.py), un taux est récupéré au plus une fois par jour
et par paire. La récupération réelle (yfinance ``EURUSD=X``…) est injectable
pour les tests. Conversion : ``convert(montant, base, quote)``.
"""

from __future__ import annotations

import datetime as dt
import threading
import time
from collections.abc import Callable

# (base, quote) -> (date, taux)  où 1 base = taux quote
_cache: dict[tuple[str, str], tuple[dt.date, float]] = {}
# Cache NEGATIF : paire -> epoch du dernier fetch en echec (meme logique que
# prices.py : ne pas re-frapper yfinance a chaque appel pour une paire cassee).
_failed: dict[tuple[str, str], float] = {}
NEG_RETRY_S = 3600.0
_lock = threading.Lock()


def _now() -> float:  # injectable dans les tests
    return time.time()


def _analysis_running() -> bool:
    """Vrai si une analyse Buffett tourne dans ce process (cf. prices.py :
    ne jamais faire la queue derrière le throttle saturé pour un taux live)."""
    try:
        from app.services.finance.scheduler_stub import is_analysis_running
        return is_analysis_running()
    except Exception:
        return False


def _default_fetch(base: str, quote: str) -> float | None:
    """Taux base->quote via yfinance (paire ``BASEQUOTE=X``)."""
    try:
        import yfinance as yf

        from app.services.finance.yf_session import fast_last_price, yf_session
        rate = fast_last_price(yf.Ticker(f"{base}{quote}=X", session=yf_session()))
        return rate if rate > 0 else None
    except Exception:
        return None


def get_rate(
    base: str,
    quote: str,
    *,
    fetcher: Callable[[str, str], float | None] | None = None,
    today: dt.date | None = None,
) -> float:
    """Taux du jour pour 1 ``base`` en ``quote`` (cache quotidien). 1.0 si base==quote."""
    base, quote = base.upper(), quote.upper()
    if base == quote:
        return 1.0
    today = today or dt.date.today()
    fetch = fetcher or _default_fetch
    key = (base, quote)

    now = _now()
    with _lock:
        entry = _cache.get(key)
        if entry and entry[0] == today:
            return entry[1]
        if _analysis_running() or now - _failed.get(key, float("-inf")) < NEG_RETRY_S:
            # Analyse en cours OU echec recent -> dernier taux connu sans
            # re-frapper yfinance
            return _cache[key][1] if key in _cache else 0.0

    rate = fetch(base, quote)
    if rate is None or rate <= 0:
        # Repli : inverse de la paire opposée si connue, sinon dernier taux connu, sinon 0.
        inv = fetch(quote, base)
        if inv and inv > 0:
            rate = 1.0 / inv
    with _lock:
        if rate and rate > 0:
            _cache[key] = (today, rate)
            _failed.pop(key, None)
            return rate
        _failed[key] = now
        if key in _cache:
            return _cache[key][1]
    return 0.0


def convert(amount: float, base: str, quote: str, **kwargs) -> float:
    """Convertit ``amount`` de ``base`` vers ``quote`` au taux du jour."""
    rate = get_rate(base, quote, **kwargs)
    return round(amount * rate, 2) if rate > 0 else 0.0


def clear_cache() -> None:
    with _lock:
        _cache.clear()
        _failed.clear()
