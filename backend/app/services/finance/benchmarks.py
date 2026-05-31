"""Performance des benchmarks (CW8, S&P 500, MSCI World) vs portefeuille."""

from __future__ import annotations

import datetime as dt
from typing import Optional

BENCHMARKS = {
    "CW8": "CW8.PA",          # Amundi MSCI World
    "SP500": "^GSPC",          # S&P 500
    "MSCI_WORLD": "URTH",     # iShares MSCI World
}
CACHE_TTL_H = 4  # heures


_cache: dict[str, tuple[float, list]] = {}  # ticker → (timestamp, data)


def _fetch_perf(ticker: str, period: str = "1y") -> Optional[dict]:
    """Télécharge la performance d'un indice via yfinance."""
    try:
        import yfinance as yf
        h = yf.Ticker(ticker).history(period=period)
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
    except Exception as e:
        print(f"[benchmarks] Erreur {ticker}: {e}")
        return None


def get_benchmarks() -> dict:
    """Retourne les métriques des 3 benchmarks (avec cache 4h)."""
    import time
    now = time.time()
    result = {}
    for name, ticker in BENCHMARKS.items():
        cached = _cache.get(ticker)
        if cached and (now - cached[0]) < CACHE_TTL_H * 3600:
            result[name] = cached[1]
            continue
        data = _fetch_perf(ticker)
        if data:
            _cache[ticker] = (now, data)
            result[name] = data
        else:
            result[name] = None
    return result


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

        start = snaps[0]["date"]
        end_plus = (pd.to_datetime(snaps[-1]["date"]) + pd.Timedelta(days=3)).strftime("%Y-%m-%d")
        hist = yf.Ticker(ticker).history(start=start, end=end_plus)
        closes = hist["Close"].dropna()
        if closes.empty:
            return []
        idx = closes.index
        idx = idx.tz_localize(None) if getattr(idx, "tz", None) is not None else idx
        price_dates = [d.date().isoformat() for d in idx]
        price_vals = [float(v) for v in closes.values]
    except Exception as e:
        print(f"[benchmarks] simulation {ticker}: {e}")
        return []

    def price_on_or_before(date_str: str):
        chosen = None
        for d, v in zip(price_dates, price_vals):
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


def get_portfolio_vs_benchmarks(portfolio_snapshots: list, period_days: int = 365) -> dict:
    """Compare les snapshots portefeuille aux benchmarks sur une période."""
    benchmarks = get_benchmarks()

    # Remplace la serie CW8 par une SIMULATION 100 % CW8 (memes apports), en EUR
    # alignee sur les dates du portefeuille (et non le prix brut de CW8).
    if portfolio_snapshots and benchmarks.get("CW8"):
        sim = simulate_benchmark_dca(portfolio_snapshots, BENCHMARKS["CW8"])
        if sim:
            benchmarks["CW8"] = {**benchmarks["CW8"], "serie": sim, "simule": True}

    if not portfolio_snapshots:
        return {"portfolio": [], "benchmarks": benchmarks}

    snaps = sorted(portfolio_snapshots, key=lambda s: s["date"])
    base_val = snaps[0]["valeur"] if snaps[0]["valeur"] > 0 else 1
    portfolio_serie = [
        {"date": s["date"], "valeur": round(s["valeur"] / base_val * 100, 2)}
        for s in snaps
    ]
    return {"portfolio": portfolio_serie, "benchmarks": benchmarks}
