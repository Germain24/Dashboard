"""Orchestrateur du run Buffett mensuel -- tourne en BackgroundTask FastAPI.

Flow exact (conforme au diagramme + regles utilisateur) :
  Pour chaque ticker :
    0. Cache chaud ? -> utiliser
    1. Charger donnees locales
    2. Si ETF (peu importe l'age) -> Score=200, Achat=True
    3. Si non-ETF ET trop frais (< MIN_AGE_YEARS) -> skip
    4. Telecharger yfinance si necessaire. Si internet est coupe -> attendre
       puis retenter LE MEME ticker (jamais le suivant) ; si yfinance echoue
       alors qu'internet est present -> garder le ticker pour un prochain run.
    5. Re-verifier si ETF apres download -> Score=200
    6. Supprimer fichier + tickers.csv UNIQUEMENT si yfinance a repondu avec
       des financials VIDES (action delistee / invalide). JAMAIS sur l'age,
       JAMAIS sur une coupure reseau.
    7. Scorer normalement (persistance immediate, un ticker a la fois)
  Optimisation DE sur les eligibles.
"""

from __future__ import annotations

import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Callable

# Attente entre deux tentatives quand internet est coupe (secondes)
RETRY_WAIT_SEC = 30

from .cache_manager import CacheManager, infer_country
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


def remove_stale_tickers(csv_path: str, to_remove: set) -> None:
    """Supprime les tickers delistes de tickers.csv."""
    if not to_remove or not Path(csv_path).exists():
        return
    try:
        import pandas as pd
        df = pd.read_csv(csv_path)
        col = df.columns[0]
        before = len(df)
        df = df[~df[col].astype(str).str.strip().str.upper().isin(
            {t.upper() for t in to_remove}
        )]
        df.to_csv(csv_path, index=False)
        print(f"[runner] {before - len(df)} tickers supprimes de {csv_path}")
    except Exception as e:
        print(f"[runner] Erreur suppression tickers: {e}")


def _check_is_etf(ticker: str, data: dict) -> bool:
    """Detecte si le ticker est un ETF depuis les donnees yfinance."""
    info = data.get("info", {})
    qt = info.get("quoteType", "").upper()
    ln = info.get("longName", "")
    sn = info.get("shortName", "")
    return qt == "ETF" or "ETF" in ln.upper() or "ETF" in sn.upper()


def _is_forced(ticker: str) -> bool:
    return ticker.upper() in [t.upper() for t in Config.FORCED_BUY_TICKERS]


def _get_data_age(data: dict) -> int:
    """Age (en annees) du rapport financier le plus recent."""
    try:
        import pandas as pd
        income = data.get("income")
        if income is not None and not income.empty:
            latest = pd.to_datetime(income.index).year.max()
            return datetime.now().year - latest
    except Exception:
        pass
    return 0


def _etf_result(ticker: str, data: dict) -> tuple[float, dict]:
    """Construit le resultat Score=200 pour un ETF."""
    info = data.get("info", {})
    metrics = {
        "Nom": info.get("longName", info.get("shortName", ticker)),
        "Pays": info.get("country", infer_country(ticker)),
        "Secteur": "ETF",
        "QuoteType": info.get("quoteType", "ETF"),
        "Achat": True,
        "Prix": info.get("currentPrice", info.get("regularMarketPrice", 0)),
        "Volume": info.get("volume", 0),
    }
    return 200.0, metrics


def _internet_available(timeout: float = 4.0) -> bool:
    """Vrai si une connexion sortante est possible (test DNS/HTTPS rapide)."""
    for host, port in (("8.8.8.8", 53), ("1.1.1.1", 53), ("query1.finance.yahoo.com", 443)):
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def _is_empty_financials(data: dict) -> bool:
    """Vrai si yfinance n'a renvoye aucune donnee financiere exploitable."""
    if not data:
        return True
    inc, bal = data.get("income"), data.get("balance")
    inc_empty = inc is None or getattr(inc, "empty", True)
    bal_empty = bal is None or getattr(bal, "empty", True)
    return inc_empty and bal_empty


def _fetch_with_retry(
    ticker: str,
    rate_limiter: RateLimiter,
    stop_flag: "threading.Event | None" = None,
) -> dict | None:
    """Telecharge via yfinance. Si internet est coupe, attend qu'il revienne et
    retente LE MEME ticker en boucle (jamais le suivant). Une erreur autre que
    reseau (internet present mais reponse vide/echec yfinance) -> abandon (None),
    le ticker est garde pour un prochain run.
    """
    while True:
        if stop_flag is not None and stop_flag.is_set():
            return None
        data = fetch_data(ticker, rate_limiter)
        if data is not None:
            return data  # yfinance a repondu (meme si donnees vides)
        if _internet_available():
            return None  # internet OK mais echec yfinance -> on garde pour plus tard
        print(f"[runner] {ticker}: internet coupe, attente {RETRY_WAIT_SEC}s puis nouvelle tentative...")
        time.sleep(RETRY_WAIT_SEC)


def _analyze_one(
    ticker: str,
    results: dict,
    cache: CacheManager,
    rate_limiter: RateLimiter,
    deleted_tickers: set,
    deleted_lock: threading.Lock,
    on_result: "Callable | None" = None,
    stop_flag: "threading.Event | None" = None,
) -> bool:
    """Analyse un ticker. Thread-safe.

    - Regle ETF : Score=200 peu importe l'age des donnees.
    - Persistance immediate via ``on_result(ticker, score, metrics)`` des qu'un
      resultat existe (chaque ticker sauve un a un).
    - Suppression UNIQUEMENT si yfinance a repondu avec des donnees vides
      (action delistee / invalide) -- jamais sur l'age ni sur une coupure reseau.
    """
    def _emit(ticker_: str, score_: float, metrics_: dict) -> None:
        results[ticker_] = (score_, metrics_)
        if on_result is not None:
            try:
                on_result(ticker_, score_, metrics_)
            except Exception as e:
                print(f"[runner] persistance {ticker_}: {e}")
    # 0. Cache chaud (ETF cached score=200 toujours retourne)
    cached = cache.get_cached_result(ticker)
    if cached:
        score, metrics = cached
        _emit(ticker, score, metrics)
        return True

    file_path = Config.output_dir() / f"{ticker.replace(':', '_')}.xlsx"
    status = cache.get_status(ticker, file_path)

    # 1. Charger donnees locales si disponibles
    local_data = None
    if status in ("local_ok", "too_fresh", "update", "too_old"):
        local_data = load_local_data(ticker)

    # 2. Verifier si ETF sur les donnees locales
    if local_data and (_check_is_etf(ticker, local_data) or _is_forced(ticker)):
        score, metrics = _etf_result(ticker, local_data)
        age = _get_data_age(local_data)
        yr = datetime.now().year - age if age >= 0 else datetime.now().year
        cache.update(ticker, yr, score, metrics)
        _emit(ticker, score, metrics)
        print(f"[runner] {ticker} ETF (local) -> Score=200")
        return True

    # 3. Non-ETF trop frais -> skip (pas de nouveau rapport annuel possible)
    if status == "too_fresh":
        return False

    # 4. Telecharger / fusionner. Si internet coupe -> attendre et retenter CE ticker.
    data = local_data
    yfinance_repondu = False
    if status in ("download", "update", "too_old") or data is None:
        new_data = _fetch_with_retry(ticker, rate_limiter, stop_flag)
        if new_data is not None:
            yfinance_repondu = True
            if data is not None and status in ("update", "too_old"):
                data = merge_data(data, new_data)
            else:
                data = new_data
        elif data is None:
            # Echec non-reseau et aucune donnee locale -> garder le ticker pour un prochain run
            return False

    if not data:
        return False

    # 5. Re-verifier si ETF apres download (quoteType peut changer)
    if _check_is_etf(ticker, data) or _is_forced(ticker):
        score, metrics = _etf_result(ticker, data)
        age = _get_data_age(data)
        yr = datetime.now().year - age if age >= 0 else datetime.now().year
        cache.update(ticker, yr, score, metrics)
        save_local_data(ticker, data)
        _emit(ticker, score, metrics)
        print(f"[runner] {ticker} ETF (yfinance) -> Score=200")
        return True

    # 6. Suppression UNIQUEMENT si yfinance a repondu avec des donnees VIDES
    #    (action delistee / invalide). Jamais sur l'age, jamais sur une coupure reseau.
    if yfinance_repondu and _is_empty_financials(data):
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception:
            pass
        with deleted_lock:
            deleted_tickers.add(ticker)
        print(f"[runner] {ticker} donnees vides (yfinance confirme) -> supprime de tickers.csv")
        return False

    # 7. Scorer normalement (et persister immediatement)
    try:
        score, metrics = analyze_financials(ticker, data)
        saved = save_local_data(ticker, data)
        if saved:
            income = data.get("income")
            yr = income.index.max().year if income is not None and not income.empty else 0
            cache.update(ticker, yr, score, metrics)
        _emit(ticker, score, metrics)
        return True
    except Exception as e:
        print(f"[runner] Erreur analyse {ticker}: {e}")
        return False


def run_buffett_analysis(
    session_factory: Callable,
    csv_path: str = Config.TICKERS_CSV,
    max_workers: int = 10,
    n_sim: int = 500_000,
    on_progress: Callable | None = None,
    run_id: int | None = None,
) -> dict:
    """Pipeline complet Buffett (analyse + optimisation DE) -- BackgroundTask.

    run_id : si fourni, persiste chaque resultat dans buffett_run_result via upsert_result.
    """
    Config.load_params()
    Config.ensure_dirs()
    tickers = load_tickers(csv_path)
    if not tickers:
        return {"error": "Aucun ticker dans tickers.csv"}

    # Exclure les titres présents dans ToutBroker.xlsx dont TOUS les brokers sont
    # explicitement Faux (cellule vide ≠ Faux). Tout le reste est analysé (y compris
    # les tickers absents du fichier). Désactivable via BUFFETT_EXCLUDE_UNAVAILABLE=false.
    from app.core.config import settings
    if settings.buffett_exclude_unavailable:
        from .broker_availability import broker_excluded_tickers
        excluded = broker_excluded_tickers()
        if excluded:
            before = len(tickers)
            tickers = [t for t in tickers if t.strip().upper() not in excluded]
            print(f"[runner] {before - len(tickers)} titres exclus (tous brokers Faux) ; "
                  f"{len(tickers)} à analyser")

    total = len(tickers)

    # Reprise : ignorer les tickers deja persistes pour ce run (programme ferme/rouvert)
    done_tickers: set = set()
    if run_id is not None:
        try:
            from .reporting import get_done_tickers
            with session_factory() as s:
                done_tickers = get_done_tickers(s, run_id)
        except Exception as e:
            print(f"[runner] Lecture reprise: {e}")
    todo = [t for t in tickers if t not in done_tickers]
    if done_tickers:
        print(f"[runner] Reprise: {len(done_tickers)} deja faits, {len(todo)} restants / {total}")

    print(f"[runner] {len(todo)} tickers a analyser (workers={max_workers})...")
    start_t = time.time()
    cache = CacheManager()
    rate_limiter = RateLimiter()
    results: dict = {}
    deleted_tickers: set = set()
    deleted_lock = threading.Lock()
    lock = threading.Lock()
    db_lock = threading.Lock()
    n_done = len(done_tickers)

    def on_result(ticker, score, metrics):
        """Sauvegarde immediate d'un ticker (un a un ; ecritures DB serialisees)."""
        if run_id is None:
            return
        with db_lock:
            try:
                from .reporting import upsert_result
                with session_factory() as session:
                    upsert_result(session, run_id, ticker, score, metrics)
            except Exception as e:
                print(f"[runner] persistance DB {ticker}: {e}")

    def task(t):
        nonlocal n_done
        ok = _analyze_one(t, results, cache, rate_limiter,
                          deleted_tickers, deleted_lock, on_result=on_result)
        with lock:
            n_done += 1
            if on_progress:
                try:
                    on_progress(n_done, total)
                except Exception:
                    pass
        return ok

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(task, t): t for t in todo}
        for _ in as_completed(futures):
            pass

    cache.save()

    if deleted_tickers:
        remove_stale_tickers(csv_path, deleted_tickers)

    # Les resultats sont deja persistes un a un (on_result). Pour l'optimisation
    # finale on recharge TOUT le run depuis la DB (inclut les tickers des sessions
    # precedentes en cas de reprise).
    if run_id is not None:
        try:
            from app.models.finance import BuffettRunResult
            from sqlmodel import select as _sel
            with session_factory() as session:
                rows = list(session.exec(
                    _sel(BuffettRunResult).where(BuffettRunResult.run_id == run_id)
                ).all())
            results = {
                r.ticker: (
                    r.chance_moat or 0.0,
                    {"Nom": r.nom, "Secteur": r.secteur, "Volume": r.volume,
                     "Achat": bool(r.achat), "Prix": r.prix},
                )
                for r in rows
            }
            print(f"[runner] {len(results)} resultats charges depuis la DB pour optimisation")
        except Exception as e:
            print(f"[runner] Rechargement DB: {e}")

    # Reporter les scores/indicateurs dans ToutBroker.xlsx (upsert par ticker,
    # disponibilite broker preservee). Une fois, mono-thread, jamais bloquant.
    if run_id is not None:
        try:
            from .broker_availability import update_broker_file_scores
            from app.models.finance import BuffettRunResult
            from sqlmodel import select as _sel_b
            with session_factory() as session:
                bres = list(session.exec(
                    _sel_b(BuffettRunResult).where(BuffettRunResult.run_id == run_id)
                ).all())
            n_written = update_broker_file_scores(bres)
            print(f"[runner] {n_written} scores ecrits dans ToutBroker.xlsx")
        except Exception as e:
            print(f"[runner] Ecriture ToutBroker: {e}")

    # Optimisation DE
    try:
        from .dedup import deduplicate_tickers
        from .optimizer import optimize_portfolio_de, prepare_optimization
        from .allocation import discretize_allocation, latest_prices
        from .broker_availability import merge_broker_columns
        import pandas as pd
        import numpy as np
        import yfinance as yf

        ticker_col = "Ticker Yahoo Finance"
        eligible = {
            t: v for t, v in results.items()
            if v[0] >= Config.SCORE_THRESHOLD
            or v[0] >= 200  # ETF
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
                    cd = pd.DataFrame({
                        t: raw[t]["Close"] for t in t_list
                        if t in raw.columns.get_level_values(0)
                    })
                cd = cd.dropna(axis=1, thresh=len(cd) * 0.01).ffill()
                rets = cd.pct_change().dropna().clip(-0.5, 0.5)
                df_m = pd.DataFrame([{
                    ticker_col: t, "Nom": eligible[t][1].get("Nom", ""),
                    "Secteur": eligible[t][1].get("Secteur", ""),
                    "Volume": eligible[t][1].get("Volume", 0),
                    "Chance MOAT": eligible[t][0], "Achat": True,
                } for t in t_list])
                # Disponibilite par broker depuis ToutBroker.xlsx (sinon tout dispo)
                df_m = merge_broker_columns(df_m, ticker_col)
                rets = deduplicate_tickers(rets, df_m, ticker_col)
                t_opt = list(rets.columns)
                mat_access, active_b = prepare_optimization(t_opt, df_m)
                weights, metric = optimize_portfolio_de(t_opt, rets, mat_access, active_b)
                total_cap = sum(Config.BUDGET_BROKERS.values())
                # Discrétisation : actions entières (hors Trading212) / pies (Trading212)
                prices = latest_prices(cd, t_opt)
                alloc = discretize_allocation(t_opt, weights, active_b, prices, total_cap)
                # Persister les allocations en DB
                if run_id is not None:
                    try:
                        from .reporting import update_allocations
                        with session_factory() as session:
                            update_allocations(session, run_id, alloc)
                        print(f"[runner] Allocations persistees ({len(alloc)} lignes)")
                    except Exception as e:
                        print(f"[runner] Erreur persistance allocations: {e}")

                return {
                    "n_analyzed": len(results), "n_eligible": len(eligible),
                    "n_optimized": len(t_opt), "metric": metric,
                    "alloc": alloc, "duree_sec": round(time.time() - start_t, 1),
                    "n_deleted": len(deleted_tickers),
                }
    except Exception as e:
        print(f"[runner] Erreur optimisation: {e}")

    return {
        "n_analyzed": len(results),
        "duree_sec": round(time.time() - start_t, 1),
        "n_deleted": len(deleted_tickers),
    }


def analyze_single_ticker(
    ticker: str,
    cache: CacheManager | None = None,
) -> tuple[float, dict] | None:
    """Analyse un seul ticker (bouton 'Analyser ticker unique').

    ETF -> Score=200 peu importe l'age.
    Retourne (score, metrics) ou None si echec.
    """
    Config.load_params()
    Config.ensure_dirs()
    if cache is None:
        cache = CacheManager()
    rate_limiter = RateLimiter(max_requests_per_hour=Config.MAX_REQUESTS_PER_HOUR)
    results: dict = {}
    dummy_deleted: set = set()
    dummy_lock = threading.Lock()

    ok = _analyze_one(ticker, results, cache, rate_limiter, dummy_deleted, dummy_lock)
    if ok and ticker in results:
        cache.save()
        return results[ticker]
    return None
