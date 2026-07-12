"""Orchestrateur du run Buffett mensuel -- tourne en BackgroundTask FastAPI.

Flow exact (conforme au diagramme + regles utilisateur) :
  Pour chaque ticker :
    0. Cache chaud ? -> utiliser
    1. Charger donnees locales
    2. Si ETF (peu importe l'age) -> Score=200, Achat=True
    3. Si non-ETF ET trop frais (< MIN_AGE_YEARS) -> skip
    3bis. Si ETF connu sans cache/local exploitable -> fetch ".info" seul
       (1 appel yfinance au lieu de 4) -> Score=200, JAMAIS de financials
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
from .data_fetch import (
    fetch_data,
    fetch_info_only,
    load_local_data,
    merge_data,
    save_local_data,
)
from .etf_detect import is_empty_financials as _is_empty_financials
from .rate_limiter import RateLimiter
from .scoring import analyze_financials


def _refresh_bond_yields() -> None:
    """Rafraîchit Config.TAUX_OBLIGATAIRES en direct (cache quotidien, repli
    sur les valeurs courantes/statiques si le réseau échoue). Best-effort."""
    try:
        from .bond_yields import get_bond_yields
        Config.TAUX_OBLIGATAIRES = get_bond_yields(defaults=Config.TAUX_OBLIGATAIRES)
    except Exception as e:
        print(f"[runner] taux obligataires non rafraîchis ({e}) — repli statique")


def load_tickers(csv_path: str = Config.TICKERS_CSV) -> list[str]:
    """Lit la liste des tickers depuis tickers.csv (headerless, séparateur `;`,
    colonnes Ticker;Nom;Bourse;Type -- ex. certains libellés Bourse contiennent
    une virgule, ex. "Euronext Amsterdam, Brussels", d'où `sep=";"` obligatoire
    (un `pd.read_csv` sans séparateur explicite lève une ParserError dès la
    première virgule rencontrée -> tickers.csv silencieusement vide)."""
    if not Path(csv_path).exists():
        return []
    try:
        import pandas as pd
        df = pd.read_csv(csv_path, sep=";", header=None)
        tickers = df[0].dropna().astype(str).str.strip().unique().tolist()
        return [t for t in tickers if t.upper() not in ("TICKER", "NAN", "")]
    except Exception as e:
        print(f"[runner] Erreur lecture {csv_path}: {e}")
        return []


def remove_stale_tickers(csv_path: str, to_remove: set) -> None:
    """Supprime les tickers delistes de tickers.csv (headerless, séparateur `;`)."""
    if not to_remove or not Path(csv_path).exists():
        return
    try:
        import pandas as pd
        df = pd.read_csv(csv_path, sep=";", header=None)
        before = len(df)
        df = df[~df[0].astype(str).str.strip().str.upper().isin(
            {t.upper() for t in to_remove}
        )]
        df.to_csv(csv_path, index=False, header=False, sep=";")
        print(f"[runner] {before - len(df)} tickers supprimes de {csv_path}")
    except Exception as e:
        print(f"[runner] Erreur suppression tickers: {e}")


def _check_is_etf(ticker: str, data: dict | None = None) -> bool:
    """Vrai si le ticker est un ETF — source AUTORITAIRE : colonne 'Secteur 1' de
    ToutBroker.xlsx (== 'ETF'). Plus d'heuristique de nom/quoteType : la liste des
    ETF est entièrement sous contrôle de l'utilisateur (cf. ``load_etf_tickers``).
    ``data`` est ignoré (conservé pour compat d'appel).
    """
    from .broker_availability import load_etf_tickers
    return ticker.upper() in load_etf_tickers()


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


def _fetch_info_with_retry(
    ticker: str,
    rate_limiter: RateLimiter,
    stop_flag: "threading.Event | None" = None,
) -> dict | None:
    """Version allegee de `_fetch_with_retry` : ne telecharge que `.info`
    (cf. `fetch_info_only`) au lieu des 4 appels de `fetch_data`. Meme
    politique de reprise sur coupure reseau (retente LE MEME ticker)."""
    while True:
        if stop_flag is not None and stop_flag.is_set():
            return None
        data = fetch_info_only(ticker, rate_limiter)
        if data is not None:
            return data
        if _internet_available():
            return None
        print(f"[runner] {ticker}: internet coupe, attente {RETRY_WAIT_SEC}s puis nouvelle tentative (info)...")
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

    # 3bis. ETF connu (ou ticker force) sans cache ni fichier local exploitable
    # (cache-froid) : le Score=200 est fige par convention, JAMAIS derive des
    # financials -- inutile de telecharger income/balance/cashflow (3 des 4
    # appels yfinance de fetch_data()). Un fetch allege ".info" seul suffit
    # (Nom/Prix/Volume) et epargne le budget rate-limiter pour les actions,
    # dont les fondamentaux doivent reellement etre reverifies.
    if _check_is_etf(ticker) or _is_forced(ticker):
        info_data = _fetch_info_with_retry(ticker, rate_limiter, stop_flag) or {"info": {}}
        info_data.setdefault("info", {})
        score, metrics = _etf_result(ticker, info_data)
        age = _get_data_age(info_data)
        yr = datetime.now().year - age if age >= 0 else datetime.now().year
        cache.update(ticker, yr, score, metrics)
        save_local_data(ticker, info_data)
        _emit(ticker, score, metrics)
        print(f"[runner] {ticker} ETF (info seul) -> Score=200")
        return True

    # 4. Telecharger / fusionner. Si internet coupe -> attendre et retenter CE ticker.
    data = local_data
    yfinance_repondu = False
    fresh_empty = False  # yfinance a repondu mais SANS aucune donnee financiere
    if status in ("download", "update", "too_old") or data is None:
        new_data = _fetch_with_retry(ticker, rate_limiter, stop_flag)
        if new_data is not None:
            yfinance_repondu = True
            # La décision de suppression se prend sur la réponse FRAÎCHE : sinon
            # merge_data réinjecte le vieux cache local et le ticker delisté n'est
            # jamais supprimé (relances inutiles).
            fresh_empty = _is_empty_financials(new_data)
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
    #    (action delistee / invalide). On se base sur la réponse fraîche
    #    (`fresh_empty`), pas sur le cache local fusionné. Jamais sur l'age,
    #    jamais sur une coupure reseau. Les tickers présents dans ToutBroker.xlsx
    #    (univers curé : ETF non marqués, titres sans comptes…) sont PROTÉGÉS.
    if yfinance_repondu and fresh_empty:
        from .broker_availability import load_broker_universe
        if ticker.upper() in load_broker_universe():
            _emit(ticker, 0.0, {"Nom": ticker, "Secteur": "Inconnu", "Achat": False})
            print(f"[runner] {ticker} donnees vides mais present dans ToutBroker -> conserve (score 0)")
            return True
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
    _refresh_bond_yields()

    # ETF = AUTORITAIRE depuis ToutBroker.xlsx (colonne 'Secteur 1' == 'ETF').
    # On relit le fichier à chaque run (il a pu être édité).
    from .broker_availability import reset_etf_cache
    reset_etf_cache()

    # Auto-correction : purge du cache les titres classés ETF (Score=200 figé)
    # qui ne sont PLUS des ETF selon ToutBroker -> force leur réanalyse. Idempotent.
    try:
        from .cache_manager import purge_misclassified_etf_cache
        purged = purge_misclassified_etf_cache()
        if purged["removed"]:
            print(f"[runner] {purged['removed']} faux ETF purgés du cache "
                  f"({purged['files_deleted']} fichiers locaux supprimés) -> réanalyse")
    except Exception as e:
        print(f"[runner] purge faux ETF: {e}")

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

    from .rate_limiter import set_active_limiter
    set_active_limiter(rate_limiter)
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(task, t): t for t in todo}
            for _ in as_completed(futures):
                pass
    finally:
        set_active_limiter(None)

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
    from . import optimization_progress as opt_prog
    opt_error: str | None = None
    try:
        from .dedup import deduplicate_correlated, deduplicate_tickers
        from .optimizer import optimize_portfolio_de, prepare_optimization
        from .allocation import close_prices_from_download, discretize_allocation, latest_prices
        from .broker_availability import merge_broker_columns
        from .broker_budgets import apply_live_broker_budgets
        from .reporting import update_allocations
        import pandas as pd
        import numpy as np

        # Budgets par broker = soldes RÉELS des comptes (account_balances.json).
        budgets = apply_live_broker_budgets()
        print(f"[runner] Budgets brokers (live): {budgets}")

        ticker_col = "Ticker Yahoo Finance"
        eligible = {
            t: v for t, v in results.items()
            if v[0] >= Config.SCORE_THRESHOLD
            or v[0] >= 200  # ETF
            or t.upper() in [f.upper() for f in Config.FORCED_BUY_TICKERS]
        }
        eligible = {t: v for t, v in eligible.items() if v[1].get("Achat", False)}
        # Filtre de liquidité : on n'alloue pas un titre sous le seuil de volume
        # échangé €/jour (sauf titres forcés). Évite la sur-pondération d'illiquides.
        from .liquidity import is_liquid
        _forced = [f.upper() for f in Config.FORCED_BUY_TICKERS]
        before_liq = len(eligible)
        eligible = {
            t: v for t, v in eligible.items()
            if t.upper() in _forced
            or is_liquid(v[1].get("Volume"), v[1].get("Prix"))
        }
        if before_liq != len(eligible):
            print(f"[runner] Liquidité: {before_liq - len(eligible)} titres écartés "
                  f"(< {Config.MIN_VOLUME_EUR:,.0f} €/j)")
        # Filtre ETF à effet de levier / inverse : rebalancement quotidien ->
        # performance qui diverge de N×l'indice sur la durée (volatility decay).
        # Détruisent la fiabilité du backtest STARR sans apporter de vraie
        # diversification long terme. Cf. leverage_filter.is_leveraged_product.
        # Une ACTION ne peut pas être "à effet de levier" (c'est une notion de
        # produit/fonds) -> le filtre ne s'applique qu'aux tickers classés ETF.
        from .leverage_filter import is_leveraged_product
        from .broker_availability import load_etf_tickers
        etf_set = load_etf_tickers()
        before_lev = len(eligible)
        excluded_lev = [
            t for t, v in eligible.items()
            if t.upper() not in _forced
            and t.upper() in etf_set
            and is_leveraged_product(v[1].get("Nom", ""))
        ]
        eligible = {t: v for t, v in eligible.items() if t not in excluded_lev}
        if excluded_lev:
            print(f"[runner] Effet de levier/inverse: {before_lev - len(eligible)} titres "
                  f"ecartes ({', '.join(excluded_lev)})")
        t_list = list(eligible.keys())

        if t_list:
            # Signale le début de la phase de préparation AVANT le téléchargement
            # (potentiellement long, ~600 titres) -- sans ça, `optimization_progress`
            # reste à "idle" pendant toute cette étape et l'UI n'affiche RIEN
            # (ni barre, ni bouton stop) jusqu'à ce que le téléchargement finisse,
            # contrairement au bouton manuel "Créer le portefeuille optimal" qui
            # le fait déjà (cf. app/api/finance/buffett.py `_run_portfolio_creation`).
            opt_prog.start(run_id=run_id, message="Téléchargement des cours…")
            from app.services.finance.yf_session import download_with_timeout, yf_session
            raw = download_with_timeout(
                tickers=t_list, period="5y", interval="1d", progress=False,
                group_by="ticker", session=yf_session(),
            )
            if raw.empty:
                opt_prog.finish(message="Cours indisponibles.")
            else:
                cd = close_prices_from_download(raw, t_list)
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
                rets = deduplicate_correlated(rets, df_m, ticker_col)
                t_opt = list(rets.columns)
                mat_access, active_b = prepare_optimization(t_opt, df_m)
                total_cap = sum(Config.BUDGET_BROKERS.values())
                # Discrétisation : actions entières (hors Trading212) / pies (Trading212)
                prices = latest_prices(cd, t_opt)

                _write_lock = threading.Lock()

                def _on_new_best(w_matrix) -> None:
                    """Persiste le meilleur portefeuille trouvé jusqu'ici (toutes seeds
                    DE confondues) pendant l'optimisation -- affichage en direct au lieu
                    d'attendre la fin (peut durer des heures). Écriture DB dans un
                    thread séparé : ne bloque JAMAIS la boucle DE (avant ce correctif,
                    une écriture synchrone ici ralentissait progressivement chaque
                    génération à mesure que le WAL SQLite grossissait -- mesuré : 0.4s
                    -> 2.9s/génération sur plusieurs heures). Si une écriture précédente
                    est encore en cours, on ignore ce nouveau meilleur (la suivante,
                    quand elle arrivera, écrira de toute façon un état plus récent)."""
                    if run_id is None:
                        return
                    if not _write_lock.acquire(blocking=False):
                        return

                    def _write() -> None:
                        try:
                            partial_alloc = discretize_allocation(
                                t_opt, w_matrix, active_b, prices, total_cap,
                            )
                            with session_factory() as session:
                                update_allocations(session, run_id, partial_alloc)
                        except Exception as e:
                            print(f"[runner] Erreur allocation progressive: {e}")
                        finally:
                            _write_lock.release()

                    threading.Thread(target=_write, daemon=True).start()

                opt_prog.start(run_id=run_id, message="Préparation de l'optimisation…")
                opt_prog.set_phase(
                    "optimisation",
                    f"Optimisation Differential Evolution ({len(t_opt)} titres)…",
                )
                try:
                    weights, metric = optimize_portfolio_de(
                        t_opt, rets, mat_access, active_b,
                        progress_cb=opt_prog.update_de, on_new_best=_on_new_best,
                        should_stop=lambda: opt_prog.snapshot()["stop_requested"],
                    )
                finally:
                    opt_prog.finish(message="Optimisation terminée.")

                alloc = discretize_allocation(t_opt, weights, active_b, prices, total_cap)
                # Persister l'allocation finale en DB. Attend un éventuel écriture
                # progressive encore en vol (meme verrou que _on_new_best) pour
                # garantir que cette écriture finale est bien la DERNIERE -- sinon
                # une écriture progressive lente pourrait se terminer APRES celle-ci
                # et ecraser le resultat final avec une allocation plus ancienne.
                if run_id is not None:
                    try:
                        with _write_lock, session_factory() as session:
                            update_allocations(session, run_id, alloc)
                        print(f"[runner] Allocations persistees ({len(alloc)} lignes)")
                    except Exception as e:
                        print(f"[runner] Erreur persistance allocations: {e}")
                # Écrire le poids (%) de chaque action dans ToutBroker.xlsx (#1)
                try:
                    from .broker_availability import update_broker_file_weights
                    n_w = update_broker_file_weights(alloc)
                    print(f"[runner] {n_w} poids ecrits dans ToutBroker.xlsx")
                except Exception as e:
                    print(f"[runner] Ecriture Poids ToutBroker: {e}")

                # Répartition du portefeuille optimal dans les logs (géo / secteur /
                # défensif vs agressif), via look-through.
                try:
                    from .breakdown import log_portfolio_breakdown
                    log_portfolio_breakdown(alloc)
                except Exception as e:
                    print(f"[runner] breakdown: {e}")

                return {
                    "n_analyzed": len(results), "n_eligible": len(eligible),
                    "n_optimized": len(t_opt), "metric": metric,
                    "alloc": alloc, "duree_sec": round(time.time() - start_t, 1),
                    "n_deleted": len(deleted_tickers),
                }
    except Exception as e:
        print(f"[runner] Erreur optimisation: {e}")
        opt_prog.finish(message=f"Erreur optimisation : {e}")
        opt_error = str(e)

    return {
        "n_analyzed": len(results),
        "duree_sec": round(time.time() - start_t, 1),
        "n_deleted": len(deleted_tickers),
        "error": opt_error,
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
    _refresh_bond_yields()
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
