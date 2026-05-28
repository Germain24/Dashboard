"""Orchestrateur du run Buffett mensuel — tourne en BackgroundTask FastAPI.

Ce module lit tickers.csv, analyse chaque ticker via scoring.py,
persiste les résultats en DB via reporting.py, puis lance l'optimiseur.
Compatible avec > 50k tickers grâce au ThreadPoolExecutor paramétrable.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from .cache_manager import CacheManager
from .config import Config
from .data_fetch import fetch_data, load_local_data, merge_data, save_local_data
from .rate_limiter import RateLimiter
from .scoring import analyze_financials


def load_tickers(csv_path: str = Config.TICKERS_CSV) -> list[str]:
    """Lit la liste des tickers depuis tickers.csv."""
    if not Path(csv_path).exists():
        return []
    try:
        import pandas as pd
        df = pd.read_csv(csv_path)
        col = df.columns[0]
        tickers = df[col].dropna().astype(str).str.strip().unique().tolist()
        if len(col) <= 5 and col.isupper() and col != "TICKER":
            tickers.insert(0, col)
        return [t for t in tickers if t.upper() not in ("TICKER", "NAN", "")]
    except Exception as e:
        print(f"[runner] Erreur lecture {csv_path}: {e}")
        return []


def _analyze_one(
    ticker: str,
    results: dict,
    cache: CacheManager,
    rate_limiter: RateLimiter,
) -> bool:
    """Analyse un ticker (cache → local → yfinance). Thread-safe."""
    cached = cache.get_cached_result(ticker)
    if cached:
        results[ticker] = cached
        return True

    file_path = Config.output_dir() / f"{ticker.replace(':', '_')}.xlsx"
    status = cache.get_status(ticker, file_path)
    data = None

    if status == "local_ok":
        data = load_local_data(ticker)
        if data is None:
            status = "download"

    if status in ("download", "update", "too_old"):
        new_data = fetch_data(ticker, rate_limiter)
        if status in ("update", "too_old"):
            old_data = load_local_data(ticker)
            data = merge_data(old_data, new_data)
        else:
            data = new_data

    if not data:
        return False

    try:
        score, metrics = analyze_financials(ticker, data)
        results[ticker] = (score, metrics)
        saved = save_local_data(ticker, data)
        if saved:
            income = data.get("income")
            yr = income.index.max().year if income is not None and not income.empty else 0
            cache.update(ticker, yr, score, metrics)
        return True
    except Exception as e:
        print(f"[runner] Erreur analyse {ticker}: {e}")
        return False


def run_buffett_analysis(
    session_factory: Callable,
    csv_path: str = Config.TICKERS_CSV,
    max_workers: int = 10,
    n_sim: int = 500_000,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Pipeline complet Buffett (analyse + optimisation) — appelé en BackgroundTask.

    Paramètres :
        session_factory : callable → SQLModel Session (ex: lambda: next(get_session()))
        csv_path : chemin vers tickers.csv
        max_workers : parallélisme yfinance (adapter selon la taille de l'univers)
        n_sim : nombre de scénarios Monte Carlo
        on_progress : callback(n_done, n_total) pour mise à jour DB

    Retourne un dict résumé.
    """
    import threading

    Config.load_params()
    Config.ensure_dirs()
    tickers = load_tickers(csv_path)
    if not tickers:
        return {"error": "Aucun ticker dans tickers.csv"}

    print(f"[runner] {len(tickers)} tickers à analyser (workers={max_workers})...")
    start_t = time.time()
    cache = CacheManager()
    rate_limiter = RateLimiter()
    results: dict = {}
    lock = threading.Lock()
    n_done = 0

    def task(t):
        nonlocal n_done
        ok = _analyze_one(t, results, cache, rate_limiter)
        with lock:
            n_done += 1
            if on_progress:
                try:
                    on_progress(n_done, len(tickers))
                except Exception:
                    pass
        return ok

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(task, t): t for t in tickers}
        for _ in as_completed(futures):
            pass

    cache.save()

    # Optimisation
    try:
        from .dedup import deduplicate_tickers
        from .optimizer import optimize_portfolio, prepare_optimization
        from .vine_copula import DVineCopula, is_pos_def, nearest_pos_def
        import pandas as pd
        import numpy as np
        import yfinance as yf

        score_col = "Chance MOAT"
        ticker_col = "Ticker Yahoo Finance"
        eligible = {
            t: v for t, v in results.items()
            if v[0] >= Config.SCORE_THRESHOLD or "ETF" in str(v[1].get("Secteur","")).upper()
               or t.upper() in [f.upper() for f in Config.FORCED_BUY_TICKERS]
        }
        eligible = {t: v for t, v in eligible.items() if v[1].get("Achat", False)}
        t_list = list(eligible.keys())

        if t_list:
            raw = yf.download(t_list, period="5y", interval="1d", progress=False, group_by="ticker")
            if not raw.empty:
                if len(t_list) == 1:
                    cd = raw["Close"].to_frame(); cd.columns = t_list
                else:
                    cd = pd.DataFrame({t: raw[t]["Close"] for t in t_list if t in raw.columns.get_level_values(0)})
                cd = cd.dropna(axis=1, thresh=len(cd)*0.01).ffill()
                rets = cd.pct_change().dropna().clip(-0.5, 0.5)
                # Construct minimal df for deduplicate_tickers
                df_m = pd.DataFrame([{ticker_col: t, "Nom": eligible[t][1].get("Nom",""),
                                       "Secteur": eligible[t][1].get("Secteur",""),
                                       "Volume": eligible[t][1].get("Volume",0),
                                       score_col: eligible[t][0], "Achat": True}
                                      for t in t_list])
                rets = deduplicate_tickers(rets, df_m, ticker_col)
                t_opt = list(rets.columns)
                U = rets.rank() / (len(rets)+1)
                vine = DVineCopula(family=Config.VINE_FAMILY, trunc_high=Config.VINE_TRUNC_HIGH).fit(U.values)
                corr = vine.implied_correlation()
                if not is_pos_def(corr): corr = nearest_pos_def(corr)
                vols = rets.std() * np.sqrt(252)
                cov = np.outer(vols, vols) * corr
                mat_access, active_b = prepare_optimization(t_opt, df_m)
                units, final_starr = optimize_portfolio(t_opt, rets, cov, mat_access, active_b, vine, n_sim)
                total_cap = sum(Config.BUDGET_BROKERS.values())
                alloc = []
                for i, t in enumerate(t_opt):
                    for j, b in enumerate(active_b):
                        u = units[i, j]
                        if u > 0:
                            br = Config.BUDGET_BROKERS[b] / total_cap
                            alloc.append({"Ticker":t,"Broker":b,"Poids total (%)": u*br})
                return {"n_analyzed": len(results), "n_eligible": len(eligible),
                        "n_optimized": len(t_opt), "starr": final_starr,
                        "alloc": alloc, "duree_sec": round(time.time()-start_t, 1)}
    except Exception as e:
        print(f"[runner] Erreur optimisation: {e}")

    return {"n_analyzed": len(results), "duree_sec": round(time.time()-start_t, 1)}
