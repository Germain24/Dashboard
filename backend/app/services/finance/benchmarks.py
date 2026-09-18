"""Performance des benchmarks (CW8, S&P 500, MSCI World) vs portefeuille."""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import logging
import threading
import time
from pathlib import Path

BENCHMARKS = {
    "CW8": "CW8.PA",          # Amundi MSCI World
    "SP500": "^GSPC",          # S&P 500
    "MSCI_WORLD": "URTH",     # iShares MSCI World
}
CACHE_TTL_H = 4  # heures
REFRESH_RETRY_S = 300.0

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[float, dict]] = {}  # ticker -> (timestamp, data)
_simulation_cache: dict[str, tuple[float, list[dict]]] = {}
_lock = threading.Lock()
_refreshing = False
_simulation_refreshing: set[str] = set()
_last_refresh_attempt = 0.0
_simulation_last_attempt: dict[str, float] = {}
_disk_loaded = False
_CACHE_FILE = Path(__file__).resolve().parents[4] / "data" / "cache" / "benchmarks.json"


def _analysis_running() -> bool:
    try:
        from app.services.finance.scheduler_stub import is_analysis_running

        return is_analysis_running()
    except Exception:
        return False


def _load_disk_cache() -> None:
    global _disk_loaded
    with _lock:
        if _disk_loaded:
            return
        _disk_loaded = True
    try:
        raw = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        metrics = {
            ticker: (float(entry[0]), entry[1])
            for ticker, entry in raw.get("metrics", {}).items()
        }
        simulations = {
            key: (float(entry[0]), entry[1])
            for key, entry in raw.get("simulations", {}).items()
        }
        with _lock:
            for ticker, entry in metrics.items():
                _cache.setdefault(ticker, entry)
            for key, entry in simulations.items():
                _simulation_cache.setdefault(key, entry)
    except Exception:
        pass


def _save_disk_cache() -> None:
    try:
        with _lock:
            payload = {
                "metrics": copy.deepcopy(_cache),
                "simulations": copy.deepcopy(_simulation_cache),
            }
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    except Exception:
        logger.debug("Cache benchmark disque indisponible", exc_info=True)


def _fetch_perf(ticker: str, period: str = "1y") -> dict | None:
    """Télécharge la performance d'un indice via yfinance."""
    try:
        import yfinance as yf

        from app.services.finance.yf_session import yf_session
        h = yf.Ticker(ticker, session=yf_session()).history(period=period)
        if h.empty:
            return None
        closes = h["Close"].dropna()
        if len(closes) < 2:
            return None

        start = float(closes.iloc[0])
        end = float(closes.iloc[-1])
        perf_1y = (end / start - 1) * 100

        # 6 mois
        mid_idx = len(closes) // 2
        perf_6m = (end / float(closes.iloc[mid_idx]) - 1) * 100 if mid_idx > 0 else 0.0

        # MTD
        today = dt.date.today()
        mtd_start = dt.date(today.year, today.month, 1)
        mtd_closes = closes[closes.index.date >= mtd_start]  # type: ignore
        perf_mtd = (end / float(mtd_closes.iloc[0]) - 1) * 100 if len(mtd_closes) > 1 else 0.0

        # Série temporelle (derniers 365 jours, réduit à 52 points)
        step = max(1, len(closes) // 52)
        serie = [
            {"date": str(closes.index[i].date()), "valeur": round(float(closes.iloc[i]) / start * 100, 2)}
            for i in range(0, len(closes), step)
        ]
        return {
            "perf_1y_pct": round(perf_1y, 2),
            "perf_6m_pct": round(perf_6m, 2),
            "perf_mtd_pct": round(perf_mtd, 2),
            "serie": serie,
        }
    except Exception as exc:
        logger.warning("Benchmark %s indisponible: %s", ticker, exc)
        return None


def _fetch_and_store_benchmarks(tickers: list[str]) -> None:
    changed = False
    for ticker in tickers:
        data = _fetch_perf(ticker)
        if data:
            with _lock:
                _cache[ticker] = (time.time(), data)
            changed = True
    if changed:
        _save_disk_cache()
        from app.core.realtime import publish

        publish(
            "finance.market_data.changed",
            data={"kind": "benchmarks", "tickers": tickers},
            invalidate=[["finance", "benchmarks"]],
        )


def _refresh_benchmarks(tickers: list[str]) -> None:
    global _refreshing
    try:
        _fetch_and_store_benchmarks(tickers)
    finally:
        with _lock:
            _refreshing = False


def _schedule_benchmark_refresh(tickers: list[str]) -> None:
    global _last_refresh_attempt, _refreshing
    if not tickers or _analysis_running():
        return
    now = time.time()
    with _lock:
        if _refreshing or now - _last_refresh_attempt < REFRESH_RETRY_S:
            return
        _refreshing = True
        _last_refresh_attempt = now
    threading.Thread(
        target=_refresh_benchmarks,
        args=(tickers,),
        name="finance-benchmark-refresh",
        daemon=True,
    ).start()


def _benchmark_result() -> dict:
    with _lock:
        return {
            name: copy.deepcopy(_cache[ticker][1]) if ticker in _cache else None
            for name, ticker in BENCHMARKS.items()
        }


def get_benchmarks(*, background_refresh: bool = False) -> dict:
    """Retourne les métriques des benchmarks avec cache persistant 4 h.

    En mode interactif, les données périmées sont rendues immédiatement et la
    mise à jour réseau part en arrière-plan. Le mode synchrone reste disponible
    pour les jobs qui exigent une valeur fraîche avant de poursuivre.
    """
    _load_disk_cache()
    now = time.time()
    with _lock:
        stale = [
            ticker
            for ticker in BENCHMARKS.values()
            if ticker not in _cache or now - _cache[ticker][0] >= CACHE_TTL_H * 3600
        ]
    if not stale:
        return _benchmark_result()
    if background_refresh:
        _schedule_benchmark_refresh(stale)
        return _benchmark_result()

    _fetch_and_store_benchmarks(stale)
    return _benchmark_result()


def simulate_benchmark_dca(portfolio_snapshots: list, ticker: str = "CW8.PA") -> list:
    """Simule un portefeuille **100 % investi dans `ticker`** avec les MEMES apports.

    `portfolio_snapshots` : [{date, valeur, investit}] (investit = cumul investi).
    A chaque hausse de l'investi (= apport), on achete des parts de `ticker` au
    cours du jour ; on valorise la position cumulee a chaque date du portefeuille.
    Retourne [{date, valeur_eur}] aligne sur les dates des snapshots — la vraie
    comparaison "et si j'avais tout mis dans CW8 ?".
    """
    snaps = sorted(
        (s for s in portfolio_snapshots if s.get("investit") is not None),
        key=lambda s: s["date"],
    )
    if len(snaps) < 2:
        return []
    try:
        import pandas as pd
        import yfinance as yf

        from app.services.finance.yf_session import yf_session

        start = snaps[0]["date"]
        end_plus = (pd.to_datetime(snaps[-1]["date"]) + pd.Timedelta(days=3)).strftime("%Y-%m-%d")
        hist = yf.Ticker(ticker, session=yf_session()).history(start=start, end=end_plus)
        closes = hist["Close"].dropna()
        if closes.empty:
            return []
        idx = closes.index
        idx = idx.tz_localize(None) if getattr(idx, "tz", None) is not None else idx
        price_dates = [d.date().isoformat() for d in idx]
        price_vals = [float(v) for v in closes.values]
    except Exception as exc:
        logger.warning("Simulation benchmark %s indisponible: %s", ticker, exc)
        return []

    def price_on_or_before(date_str: str):
        chosen = None
        for d, v in zip(price_dates, price_vals, strict=False):
            if d <= date_str:
                chosen = v
            else:
                break
        return chosen if chosen is not None else price_vals[0]

    cum_shares = 0.0
    prev_inv = 0.0
    serie: list = []
    for s in snaps:
        inv = float(s.get("investit") or 0)
        contrib = inv - prev_inv
        prev_inv = inv
        price = price_on_or_before(s["date"])
        if price and price > 0:
            cum_shares += contrib / price
            val = cum_shares * price
        else:
            val = serie[-1]["valeur"] if serie else inv
        serie.append({"date": s["date"], "valeur": round(val, 2)})
    return serie


def _simulation_key(portfolio_snapshots: list, ticker: str) -> str:
    payload = [
        (str(snapshot.get("date")), float(snapshot.get("investit") or 0))
        for snapshot in sorted(portfolio_snapshots, key=lambda item: item.get("date", ""))
    ]
    digest = hashlib.sha256(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"{ticker}:{digest}"


def _store_simulation(key: str, simulation: list[dict]) -> None:
    if not simulation:
        return
    with _lock:
        _simulation_cache[key] = (time.time(), simulation)
    _save_disk_cache()


def _refresh_simulation(key: str, snapshots: list, ticker: str) -> None:
    try:
        _store_simulation(key, simulate_benchmark_dca(snapshots, ticker))
        from app.core.realtime import publish

        publish(
            "finance.market_data.changed",
            data={"kind": "benchmark_simulation", "ticker": ticker},
            invalidate=[["finance", "benchmarks"]],
        )
    finally:
        with _lock:
            _simulation_refreshing.discard(key)


def _schedule_simulation_refresh(key: str, snapshots: list, ticker: str) -> None:
    if _analysis_running():
        return
    now = time.time()
    with _lock:
        last_attempt = _simulation_last_attempt.get(key, 0.0)
        if key in _simulation_refreshing or now - last_attempt < REFRESH_RETRY_S:
            return
        _simulation_refreshing.add(key)
        _simulation_last_attempt[key] = now
    threading.Thread(
        target=_refresh_simulation,
        args=(key, copy.deepcopy(snapshots), ticker),
        name="finance-cw8-simulation-refresh",
        daemon=True,
    ).start()


def _cached_simulation(key: str) -> tuple[list[dict] | None, bool]:
    with _lock:
        entry = _simulation_cache.get(key)
        if entry is None:
            return None, False
        return copy.deepcopy(entry[1]), time.time() - entry[0] < CACHE_TTL_H * 3600


def clear_cache() -> None:
    """Vide les caches mémoire; utilisé par les tests et le rafraîchissement forcé."""
    global _disk_loaded, _last_refresh_attempt, _refreshing
    with _lock:
        _cache.clear()
        _simulation_cache.clear()
        _simulation_last_attempt.clear()
        _disk_loaded = False
        _last_refresh_attempt = 0.0
        _refreshing = False


def get_portfolio_vs_benchmarks(
    portfolio_snapshots: list,
    period_days: int = 365,
    *,
    background_refresh: bool = False,
) -> dict:
    """Compare les snapshots portefeuille aux benchmarks sur une période."""
    benchmarks = get_benchmarks(background_refresh=background_refresh)

    # Remplace la serie CW8 par une SIMULATION 100 % CW8 (memes apports), en EUR
    # alignee sur les dates du portefeuille (et non le prix brut de CW8).
    if portfolio_snapshots:
        ticker = BENCHMARKS["CW8"]
        key = _simulation_key(portfolio_snapshots, ticker)
        simulation, fresh = _cached_simulation(key)
        if not fresh:
            if background_refresh:
                _schedule_simulation_refresh(key, portfolio_snapshots, ticker)
            else:
                simulation = simulate_benchmark_dca(portfolio_snapshots, ticker)
                _store_simulation(key, simulation)
        if benchmarks.get("CW8"):
            benchmarks["CW8"] = {
                **benchmarks["CW8"],
                "serie": simulation or [],
                "simule": bool(simulation),
            }

    if not portfolio_snapshots:
        return {"portfolio": [], "benchmarks": benchmarks}

    snaps = sorted(portfolio_snapshots, key=lambda s: s["date"])
    base_val = snaps[0]["valeur"] if snaps[0]["valeur"] > 0 else 1
    portfolio_serie = [
        {"date": s["date"], "valeur": round(s["valeur"] / base_val * 100, 2)}
        for s in snaps
    ]
    return {"portfolio": portfolio_serie, "benchmarks": benchmarks}
