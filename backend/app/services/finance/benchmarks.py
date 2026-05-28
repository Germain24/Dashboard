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


def get_portfolio_vs_benchmarks(portfolio_snapshots: list, period_days: int = 365) -> dict:
    """Compare les snapshots portefeuille aux benchmarks sur une période."""
    if not portfolio_snapshots:
        return {"portfolio": [], "benchmarks": get_benchmarks()}

    snaps = sorted(portfolio_snapshots, key=lambda s: s["date"])
    base_val = snaps[0]["valeur"] if snaps[0]["valeur"] > 0 else 1
    portfolio_serie = [
        {"date": s["date"], "valeur": round(s["valeur"] / base_val * 100, 2)}
        for s in snaps
    ]
    return {
        "portfolio": portfolio_serie,
        "benchmarks": get_benchmarks(),
    }
