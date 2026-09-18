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
_HISTORY_CACHE_FILE = (
    Path(__file__).resolve().parents[4] / "data" / "cache" / "fx_history_ecb.csv"
)
_ECB_HISTORY_URL = (
    "https://data-api.ecb.europa.eu/service/data/EXR/"
    "D.{currency}.EUR.SP00.A?startPeriod=2019-01-01&format=csvdata"
)
_ECB_DAILY_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
# Cache NEGATIF : paire -> epoch du dernier fetch en echec (meme logique que
# prices.py : ne pas re-frapper yfinance a chaque appel pour une paire cassee).
_failed: dict[tuple[str, str], float] = {}
NEG_RETRY_S = 3600.0
_lock = threading.Lock()
_refreshing: set[tuple[str, str]] = set()
_disk_loaded = False
_history_cache = None
_history_lock = threading.Lock()


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


def get_historical_rates(
    base: str,
    quote: str,
    *,
    refresh_after_days: int = 7,
):
    """Série quotidienne ``1 base = n quote`` issue des taux de référence ECB.

    Le CSV officiel exprime chaque devise en unités pour un euro. On convertit
    donc ``base -> quote`` par ``quote_par_eur / base_par_eur``. Le dernier CSV
    valide est conservé sur disque et reste utilisable hors ligne : une panne
    ponctuelle de Yahoo/ECB ne doit pas interrompre une optimisation entière.
    Renvoie une série pandas vide pour une devise non couverte par l'ECB.
    """
    import pandas as pd

    base, quote = base.upper(), quote.upper()
    if base == quote:
        return pd.Series(dtype=float)

    def normalize_frame(raw):
        if raw is None or "Date" not in raw.columns:
            return None
        normalized = raw.copy()
        normalized["Date"] = pd.to_datetime(normalized["Date"], errors="coerce")
        return normalized.dropna(subset=["Date"]).set_index("Date").sort_index()

    def download_currency(currency: str):
        if currency == "EUR":
            return pd.Series(dtype=float)
        try:
            import httpx

            response = httpx.get(
                _ECB_HISTORY_URL.format(currency=currency),
                timeout=20.0,
                follow_redirects=True,
                headers={"User-Agent": "mission-control/finance"},
            )
            response.raise_for_status()
            raw = pd.read_csv(io.StringIO(response.text))
            if not {"TIME_PERIOD", "OBS_VALUE"}.issubset(raw.columns):
                return pd.Series(dtype=float)
            dates = pd.to_datetime(raw["TIME_PERIOD"], errors="coerce")
            values = pd.to_numeric(raw["OBS_VALUE"], errors="coerce")
            series = pd.Series(values.to_numpy(), index=dates, name=currency)
            return series.dropna().sort_index()
        except Exception:
            return pd.Series(dtype=float)

    # Import local : évite de charger le parseur CSV à chaque conversion spot.
    import io

    global _history_cache
    with _history_lock:
        frame = _history_cache
        if frame is None:
            try:
                frame = normalize_frame(pd.read_csv(_HISTORY_CACHE_FILE))
            except Exception:
                frame = pd.DataFrame()
            _history_cache = frame

        today = pd.Timestamp(dt.date.today())
        changed = False
        for currency in {base, quote} - {"EUR"}:
            existing = frame[currency].dropna() if currency in frame.columns else pd.Series()
            last = existing.index.max() if not existing.empty else pd.NaT
            stale = pd.isna(last) or (today - last).days > max(0, refresh_after_days)
            if stale:
                downloaded = download_currency(currency)
                if not downloaded.empty:
                    frame = frame.drop(columns=[currency], errors="ignore").join(
                        downloaded, how="outer"
                    )
                    changed = True
        if changed:
            frame = frame.sort_index()
            _history_cache = frame
            try:
                _HISTORY_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                frame.rename_axis("Date").to_csv(_HISTORY_CACHE_FILE)
            except Exception:
                pass
        data = frame.copy()

    def per_eur(currency: str):
        if currency == "EUR":
            return pd.Series(1.0, index=data.index)
        if currency not in data.columns:
            return pd.Series(dtype=float)
        return pd.to_numeric(data[currency], errors="coerce")

    base_per_eur = per_eur(base)
    quote_per_eur = per_eur(quote)
    if base_per_eur.empty or quote_per_eur.empty:
        return pd.Series(dtype=float)
    result = (quote_per_eur / base_per_eur).replace([float("inf"), float("-inf")], pd.NA)
    return result.dropna().sort_index()


def refresh_rates_from_ecb(
    bases: list[str] | set[str] | tuple[str, ...],
    quote: str = "EUR",
    *,
    today: dt.date | None = None,
) -> set[str]:
    """Alimente en une requête les taux spot ECB demandés et renvoie les bases trouvées.

    Les taux ECB sont cotés ``1 EUR = n devise``. La conversion générique
    ``base -> quote`` vaut donc ``quote_par_eur / base_par_eur``.
    """
    import xml.etree.ElementTree as ET

    wanted = {str(base).upper() for base in bases}
    quote = quote.upper()
    today = today or dt.date.today()
    try:
        import httpx

        response = httpx.get(
            _ECB_DAILY_URL,
            timeout=12.0,
            follow_redirects=True,
            headers={"User-Agent": "mission-control/finance"},
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
        per_eur = {"EUR": 1.0}
        for node in root.iter():
            currency = str(node.attrib.get("currency") or "").upper()
            rate = node.attrib.get("rate")
            if currency and rate:
                per_eur[currency] = float(rate)
        quote_rate = per_eur.get(quote)
        if not quote_rate:
            return set()
        found = set()
        with _lock:
            for base in wanted:
                base_rate = per_eur.get(base)
                if base_rate and base_rate > 0:
                    _cache[(base, quote)] = (today, quote_rate / base_rate)
                    _failed.pop((base, quote), None)
                    found.add(base)
        if found:
            save_disk_cache()
        return found
    except Exception:
        return set()


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
