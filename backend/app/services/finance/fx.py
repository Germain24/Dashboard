"""Taux de change avec cache quotidien (conversion au taux du jour).

Comme pour les cours (prices.py), un taux est récupéré au plus une fois par jour
et par paire. La récupération réelle (yfinance ``EURUSD=X``…) est injectable
pour les tests. Conversion : ``convert(montant, base, quote)``.
"""

from __future__ import annotations

import datetime as dt
import json
import threading
import time
from collections.abc import Callable
from pathlib import Path

# (base, quote) -> (date, taux)  où 1 base = taux quote
_cache: dict[tuple[str, str], tuple[dt.date, float]] = {}

# Cache DISQUE : survit au redémarrage du backend (un restart en cours de
# journée perdait les taux du warm-up -> tous les volumes non-EUR à 0 pendant
# l'analyse suivante). Seuls les fetchs réseau par défaut sont persistés;
# les fetchers injectés dans les tests ne peuvent donc pas polluer ce fichier.
_DISK_CACHE_FILE = Path(__file__).resolve().parents[4] / "data" / "cache" / "fx_rates.json"
# Cache NEGATIF : paire -> epoch du dernier fetch en echec (meme logique que
# prices.py : ne pas re-frapper yfinance a chaque appel pour une paire cassee).
_failed: dict[tuple[str, str], float] = {}
NEG_RETRY_S = 3600.0
_lock = threading.Lock()
_refreshing: set[tuple[str, str]] = set()
_disk_loaded = False


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


def _fetch_with_inverse(
    base: str, quote: str, fetch: Callable[[str, str], float | None]
) -> float | None:
    rate = fetch(base, quote)
    if rate is not None and rate > 0:
        return rate
    inverse = fetch(quote, base)
    return 1.0 / inverse if inverse is not None and inverse > 0 else None


def _refresh_rate(base: str, quote: str, today: dt.date) -> None:
    key = (base, quote)
    try:
        rate = _fetch_with_inverse(base, quote, _default_fetch)
        with _lock:
            if rate is not None and rate > 0:
                _cache[key] = (today, rate)
                _failed.pop(key, None)
            else:
                _failed[key] = _now()
        if rate is not None and rate > 0:
            save_disk_cache()
    finally:
        with _lock:
            _refreshing.discard(key)


def _schedule_refresh(base: str, quote: str, today: dt.date) -> None:
    key = (base, quote)
    with _lock:
        if key in _refreshing:
            return
        _refreshing.add(key)
    threading.Thread(
        target=_refresh_rate,
        args=(base, quote, today),
        name=f"finance-fx-refresh-{base}-{quote}",
        daemon=True,
    ).start()


def get_rate(
    base: str,
    quote: str,
    *,
    fetcher: Callable[[str, str], float | None] | None = None,
    today: dt.date | None = None,
    force: bool = False,
    stale_ok: bool = False,
) -> float:
    """Taux du jour pour 1 ``base`` en ``quote`` (cache quotidien). 1.0 si
    base==quote. ``force=True`` (warm-up au démarrage d'un run Buffett) passe
    outre le garde _analysis_running et le cache négatif -- pas le cache du
    jour."""
    base, quote = base.upper(), quote.upper()
    if base == quote:
        return 1.0
    today = today or dt.date.today()
    use_default_fetcher = fetcher is None
    if use_default_fetcher:
        load_disk_cache()
    fetch = fetcher or _default_fetch
    key = (base, quote)

    now = _now()
    schedule_refresh = False
    stale_value = 0.0
    with _lock:
        entry = _cache.get(key)
        if entry and entry[0] == today:
            return entry[1]
        if not force and (
            _analysis_running() or now - _failed.get(key, float("-inf")) < NEG_RETRY_S
        ):
            # Analyse en cours OU echec recent -> dernier taux connu sans
            # re-frapper yfinance
            return _cache[key][1] if key in _cache else 0.0
        if stale_ok and use_default_fetcher and not force:
            schedule_refresh = True
            stale_value = _cache[key][1] if key in _cache else 0.0

    if schedule_refresh:
        _schedule_refresh(base, quote, today)
        return stale_value

    rate = _fetch_with_inverse(base, quote, fetch)
    with _lock:
        if rate and rate > 0:
            _cache[key] = (today, rate)
            _failed.pop(key, None)
            result = rate
        else:
            _failed[key] = now
            result = _cache[key][1] if key in _cache else 0.0
    if rate and rate > 0 and use_default_fetcher:
        save_disk_cache()
    return result


def convert(amount: float, base: str, quote: str, **kwargs) -> float:
    """Convertit ``amount`` de ``base`` vers ``quote`` au taux du jour."""
    rate = get_rate(base, quote, **kwargs)
    return round(amount * rate, 2) if rate > 0 else 0.0


def clear_cache() -> None:
    global _disk_loaded
    with _lock:
        _cache.clear()
        _failed.clear()
        _disk_loaded = False


def load_disk_cache() -> None:
    """Recharge les taux persistés (sans écraser un taux déjà en mémoire).
    Best-effort : fichier absent/corrompu -> no-op."""
    global _disk_loaded
    with _lock:
        if _disk_loaded:
            return
        _disk_loaded = True
    try:
        raw = json.loads(_DISK_CACHE_FILE.read_text(encoding="utf-8"))
        with _lock:
            for pair, (day, rate) in raw.items():
                base, quote = pair.split("/", 1)
                _cache.setdefault(
                    (base, quote), (dt.date.fromisoformat(day), float(rate))
                )
    except Exception:
        pass


def save_disk_cache() -> None:
    """Persiste le cache mémoire sur disque (appelé par warm_fx_cache après
    les fetchs réels -- les taux y sont donc toujours issus du réseau)."""
    try:
        with _lock:
            data = {f"{b}/{q}": (d.isoformat(), r) for (b, q), (d, r) in _cache.items()}
        _DISK_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _DISK_CACHE_FILE.write_text(json.dumps(data, indent=1), encoding="utf-8")
    except Exception:
        pass
