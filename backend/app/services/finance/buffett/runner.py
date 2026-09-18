"""Orchestrateur du run Buffett mensuel -- tourne en BackgroundTask FastAPI.

Flow exact (conforme au diagramme + regles utilisateur) :
  Pour chaque ticker :
    0. Cache chaud ? -> utiliser
    1. Charger donnees locales
    2. Si ETF -> type explicite, MOAT non applicable, Achat=True
    3. Si non-ETF ET trop frais (< MIN_AGE_YEARS) -> skip
    3bis. Si ETF connu sans cache/local exploitable -> aucun appel individuel;
       prix et volume viendront du download groupé de corrélation
    4. Telecharger yfinance si necessaire. En cas d'echec, rendre immédiatement
       le worker disponible et reprendre le ticker en fin de passe.
    5. Re-vérifier le type ETF après téléchargement
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
import traceback
from collections.abc import Callable
from datetime import datetime

# Tickers dont le fetch échoue (internet down ou erreur Yahoo) : on les
# collecte et les réessaie en batch à la fin. Aucun sleep ni deuxième appel
# immédiat ne doit retenir un worker sur le même ticker.
from .cache_manager import CacheManager, infer_country
from .config import Config
from .data_fetch import (
    fetch_data,
    load_local_data,
    merge_data,
    save_excel_mirror,
    save_local_data,
)
from .etf_detect import is_empty_financials as _is_empty_financials
from .fundamentals_resolver import FundamentalsLink
from .rate_limiter import RateLimiter
from .scoring import analyze_financials


def load_tickers(csv_path: str = Config.TICKERS_CSV) -> list[str]:
    """Lit la liste des tickers depuis tickers.csv (headerless, séparateur `;`,
    colonnes Ticker;Nom;Bourse;Type -- ex. certains libellés Bourse contiennent
    une virgule, ex. "Euronext Amsterdam, Brussels", d'où `sep=";"` obligatoire
    (un `pd.read_csv` sans séparateur explicite lève une ParserError dès la
    première virgule rencontrée -> tickers.csv silencieusement vide)."""
    from .ticker_universe import read_ticker_catalog

    return list(read_ticker_catalog(csv_path).tickers)


def remove_stale_tickers(csv_path: str, to_remove: set) -> None:
    """Compatibilité historique: place en quarantaine, sans toucher au CSV."""
    if not to_remove:
        return
    from .quarantine import record_quarantine
    for ticker in sorted(to_remove):
        record_quarantine(
            ticker,
            error_kind="empty_financials",
            error="réponse financière vide confirmée pendant le scoring",
        )
    print(f"[runner] {len(to_remove)} tickers places en quarantaine; catalogue inchange")


def _check_is_etf(ticker: str, data: dict | None = None) -> bool:
    """Vrai si le catalogue ou les données financières prouvent qu'il s'agit d'un ETF."""
    from .broker_availability import load_etf_tickers
    if ticker.upper() in load_etf_tickers():
        return True
    if data:
        from .etf_detect import is_etf
        return is_etf(data)
    return False


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
    """Construit un résultat ETF sans détourner l'échelle MOAT 0–100."""
    info = data.get("info", {})
    prix = info.get("currentPrice", info.get("regularMarketPrice", 0))
    metrics = {
        "Nom": info.get("longName", info.get("shortName", ticker)),
        "Pays": info.get("country", infer_country(ticker)),
        "Secteur": "ETF",
        "InstrumentType": "ETF",
        "QuoteType": info.get("quoteType", "ETF"),
        "Achat": True,
        "Prix": prix,
        # Yahoo expose généralement l'encours d'un fonds via totalAssets. Il
        # sert uniquement au classement des ETF d'un même indice; son absence
        # déclenche le repli déterministe sur le volume puis les frais.
        "Encours": info.get("totalAssets", info.get("netAssets", 0)),
    }
    # Le cours et le volume sont volontairement complétés depuis le download
    # groupé utilisé pour les corrélations, pas par un appel `.info` par ETF.
    return 0.0, metrics


def _internet_available(timeout: float = 4.0) -> bool:
    """Sonde réseau conservée pour compatibilité avec les intégrations.

    Elle n'est volontairement plus appelée par le chemin de scoring : même une
    coupure réseau doit rendre immédiatement le worker au pool et différer le
    ticker, pas déclencher une boucle d'attente locale.
    """
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
    stop_flag: threading.Event | None = None,
) -> dict | None:
    """Effectue une seule tentative.

    Le nom est conservé pour compatibilité interne, mais la reprise est
    orchestrée par ``run_buffett_analysis`` en fin de passe. Ainsi une erreur
    Yahoo ou réseau ne bloque jamais un worker avec un sleep ou un second appel
    immédiat.
    """
    if stop_flag is not None and stop_flag.is_set():
        return None
    return fetch_data(ticker, rate_limiter)


def _run_retry_batch(
    tickers: list[str],
    retry_one: Callable[[str], bool],
    *,
    max_workers: int,
) -> int:
    """Relance les échecs inline avec la même session Yahoo cohérente."""
    if not tickers:
        return 0
    recovered = 0
    for completed, ticker in enumerate(tickers, start=1):
        # `retry_one` attend ici si un précédent ticker a reçu un 429. Cela
        # garantit une seule sonde après le backoff au lieu de vider toute la
        # liste contre un Yahoo encore bloqué.
        try:
            if retry_one(ticker):
                recovered += 1
        except Exception as exc:
            print(f"[runner] retry {ticker}: {exc}")
        print(
            f"[runner] Reessais Yahoo: {completed}/{len(tickers)} "
            f"({recovered} recuperes)"
        )
    return recovered


def _analyze_one(
    ticker: str,
    results: dict,
    cache: CacheManager,
    rate_limiter: RateLimiter,
    deleted_tickers: set,
    deleted_lock: threading.Lock,
    on_result: Callable | None = None,
    stop_flag: threading.Event | None = None,
    fundamentals_link: FundamentalsLink | None = None,
    force: bool = False,
) -> bool:
    """Analyse un ticker. Thread-safe.

    - Règle ETF : type explicite et MOAT non applicable.
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

    def _remember_empty(metrics_: dict, reason: str) -> None:
        # ``getattr`` garde les doubles de test et les intégrations historiques
        # compatibles, tandis que le CacheManager de production persiste bien
        # systématiquement l'état négatif.
        update_empty = getattr(cache, "update_empty", None)
        if callable(update_empty):
            update_empty(ticker, metrics_, reason)
    fundamentals_symbol = (
        fundamentals_link.fundamentals_symbol
        if fundamentals_link is not None
        else ticker
    )
    identity_key = (
        fundamentals_link.identity_key
        if fundamentals_link is not None
        else ticker
    )
    uses_fundamentals_alias = fundamentals_symbol.upper() != ticker.upper()
    # 0. Cache chaud (les ETF explicitement typés restent valides). Les entrées
    # d'avant le passage de Volume en euros (2026-07-15) portent un volume en
    # nb d'actions : ensure_volume_eur convertit à la lecture (marqueur
    # VolumeDevise, idempotent) -- sinon le filtre de liquidité compare des
    # nb d'actions au seuil en euros (#bug run 40 : univers faussé).
    is_empty_confirmed = getattr(cache, "is_empty_confirmed", lambda _ticker: False)
    negative_cached = bool(is_empty_confirmed(ticker))
    cached = None if force and negative_cached else cache.get_cached_result(ticker)
    # Un ancien score nul peut provenir précisément de l'absence de comptes sur
    # la cotation secondaire. Dès qu'une liaison ISIN existe, on le répare au
    # lieu de figer ce faux zéro dans le cache.
    if cached and (
        negative_cached
        or not (uses_fundamentals_alias and float(cached[0]) <= 0)
    ):
        from . import progress_state
        from .currency import ensure_volume_eur
        progress_state.update(cache_hit=True)
        score, metrics = cached
        _emit(ticker, score, ensure_volume_eur(metrics, ticker))
        return True

    # Une ligne récemment analysée comme action peut venir d'être corrigée en
    # ETF par le catalogue broker. Son score action est jeté, mais ses métriques
    # de marché récentes suffisent pour créer immédiatement le résultat ETF,
    # sans refaire un appel Yahoo uniquement pour obtenir nom/prix/volume.
    if _check_is_etf(ticker) and not _is_forced(ticker):
        recent_metrics_getter = getattr(cache, "get_recent_metrics", None)
        recent_metrics = (
            recent_metrics_getter(ticker) if callable(recent_metrics_getter) else None
        )
        if recent_metrics:
            from .currency import ensure_volume_eur

            metrics = ensure_volume_eur(dict(recent_metrics), ticker)
            metrics.update({"Secteur": "ETF", "QuoteType": "ETF", "Achat": True})
            metrics["InstrumentType"] = "ETF"
            cache.update(ticker, datetime.now().year, 0.0, metrics)
            _emit(ticker, 0.0, metrics)
            print(f"[runner] {ticker} ETF (promotion cache récente) -> MOAT=N/A")
            return True

    file_path = Config.output_dir() / f"{ticker.replace(':', '_')}.xlsx"
    status = cache.get_status(ticker, file_path)

    # 1. Charger donnees locales si disponibles
    local_data = None
    if status in ("local_ok", "too_fresh", "update", "too_old") or uses_fundamentals_alias:
        if uses_fundamentals_alias:
            local_data = load_local_data(
                ticker,
                identity_key=identity_key,
                fundamentals_symbol=fundamentals_symbol,
            )
        else:
            local_data = load_local_data(ticker)

    # 2. Verifier si ETF sur les donnees locales
    if local_data and _check_is_etf(ticker, local_data):
        score, metrics = _etf_result(ticker, local_data)
        age = _get_data_age(local_data)
        yr = datetime.now().year - age if age >= 0 else datetime.now().year
        cache.update(ticker, yr, score, metrics)
        _emit(ticker, score, metrics)
        print(f"[runner] {ticker} ETF (local) -> MOAT=N/A")
        return True

    # 3. Non-ETF trop frais (dernier rapport annuel < MIN_AGE_YEARS) -> pas de
    # nouveau rapport possible, donc RIEN A RETELECHARGER, mais le titre reste
    # valide ce mois-ci : on le score depuis les donnees locales deja chargees
    # (etape 1), sans le moindre appel reseau, au lieu de l'abandonner (#bug
    # rapporte : le titre disparaissait purement et simplement de l'univers
    # eligible du run tant que son rapport restait "trop frais", meme s'il
    # avait deja un score valide).
    if status == "too_fresh":
        if not local_data:
            return False
        try:
            score, metrics = analyze_financials(ticker, local_data)
            income = local_data.get("income")
            yr = income.index.max().year if income is not None and not income.empty else 0
            cache.update(ticker, yr, score, metrics)
            _emit(ticker, score, metrics)
            return True
        except Exception as e:
            print(f"[runner] Erreur analyse (too_fresh) {ticker}: {e}")
            return False

    # 3bis. Un ETF froid ne déclenche aucun appel Yahoo individuel. Le volume
    # sera dérivé plus tard du download groupé déjà nécessaire aux corrélations.
    if _check_is_etf(ticker):
        score, metrics = _etf_result(ticker, {"info": {}})
        yr = datetime.now().year
        cache.update(ticker, yr, score, metrics)
        _emit(ticker, score, metrics)
        print(f"[runner] {ticker} ETF (catalogue) -> MOAT=N/A, sans appel individuel")
        return True

    # 4. Télécharger / fusionner. En cas d'échec, le ticker est repris en fin
    # de passe sans bloquer ce worker.
    data = local_data
    yfinance_repondu = False
    fresh_empty = False  # yfinance a repondu mais SANS aucune donnee financiere
    needs_network = status in ("download", "update", "too_old") or data is None
    # Le cache SQLite est partagé par ISIN. Il peut donc être exploitable même
    # si CacheManager ne connaît encore aucun fichier pour la cotation locale.
    if uses_fundamentals_alias and data is not None:
        needs_network = False
    if needs_network:
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

    # Une cotation secondaire officiellement reliée par ISIN peut n'exposer
    # aucun état financier chez Yahoo. On télécharge alors la cotation primaire
    # pour le scoring, tout en conservant `ticker` comme symbole d'exécution et
    # comme clé du résultat broker.
    if yfinance_repondu and fresh_empty and uses_fundamentals_alias:
        primary_data = _fetch_with_retry(
            fundamentals_symbol,
            rate_limiter,
            stop_flag,
        )
        if primary_data is None:
            return False
        if not _is_empty_financials(primary_data):
            data = primary_data
            fresh_empty = False
            info = data.setdefault("info", {})
            if isinstance(info, dict):
                info["fundamentalsSymbol"] = fundamentals_symbol
                info["quoteSymbol"] = ticker
                if identity_key and identity_key.upper() != ticker.upper():
                    info.setdefault("isin", identity_key)
            print(
                f"[runner] {ticker}: fondamentaux {fundamentals_symbol} "
                f"partages par ISIN {identity_key}"
            )

    if not data:
        return False

    # 5. Re-verifier si ETF apres download (quoteType peut changer)
    if _check_is_etf(ticker, data):
        score, metrics = _etf_result(ticker, data)
        age = _get_data_age(data)
        yr = datetime.now().year - age if age >= 0 else datetime.now().year
        cache.update(ticker, yr, score, metrics)
        save_local_data(ticker, data)
        if yfinance_repondu:
            save_excel_mirror(ticker, data)
        _emit(ticker, score, metrics)
        print(f"[runner] {ticker} ETF (yfinance) -> MOAT=N/A")
        return True

    # 6. Suppression UNIQUEMENT si yfinance a repondu avec des donnees VIDES
    #    (action delistee / invalide). On se base sur la réponse fraîche
    #    (`fresh_empty`), pas sur le cache local fusionné. Jamais sur l'age,
    #    jamais sur une coupure reseau. Les tickers présents dans ToutBroker.xlsx
    #    (univers curé : ETF non marqués, titres sans comptes…) sont PROTÉGÉS.
    if yfinance_repondu and fresh_empty:
        from . import progress_state
        progress_state.update(error_kind="empty_financials")
        from .broker_availability import load_broker_universe
        if ticker.upper() in load_broker_universe():
            metrics = {
                "Nom": ticker,
                "Secteur": "Inconnu",
                "Achat": False,
                "Erreur": "empty_financials_confirmed",
            }
            _remember_empty(metrics, "empty_financials_confirmed")
            _emit(ticker, 0.0, metrics)
            print(f"[runner] {ticker} donnees vides mais present dans ToutBroker -> conserve (score 0)")
            return True
        with deleted_lock:
            deleted_tickers.add(ticker)
        # Une réponse vide confirmée est un résultat définitif pour ce snapshot.
        # La persister à 0 évite de la retélécharger à chaque reprise tout en
        # conservant le catalogue source intact.
        metrics = {
            "Nom": ticker,
            "Secteur": "Inconnu",
            "Achat": False,
            "Erreur": "empty_financials_confirmed",
        }
        _remember_empty(metrics, "empty_financials_confirmed")
        _emit(ticker, 0.0, metrics)
        print(f"[runner] {ticker} donnees vides (yfinance confirme) -> quarantaine")
        # Réponse Yahoo valide et traitement terminé : ce n'est pas un échec à
        # remettre dans la file de reprise.
        return True

    # 7. Scorer normalement (et persister immediatement)
    try:
        score, metrics = analyze_financials(ticker, data)
        if uses_fundamentals_alias:
            metrics["FundamentalsSymbol"] = fundamentals_symbol
            metrics["QuoteSymbol"] = ticker
            metrics["ISIN"] = identity_key
        if uses_fundamentals_alias:
            saved = save_local_data(
                fundamentals_symbol,
                data,
                identity_key=identity_key,
            )
            mirror_ticker = fundamentals_symbol
        else:
            saved = save_local_data(ticker, data)
            mirror_ticker = ticker
        # Double persistance uniquement après un téléchargement réel. SQLite
        # sert au quotidien ; le classeur constitue la copie restaurable.
        if saved and yfinance_repondu:
            save_excel_mirror(mirror_ticker, data)
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
    max_workers: int = 1,
    n_sim: int = 500_000,
    on_progress: Callable | None = None,
    run_id: int | None = None,
    initial_total: int | None = None,
) -> dict:
    """Pipeline complet Buffett (analyse + optimisation DE) -- BackgroundTask.

    run_id : si fourni, persiste chaque resultat dans buffett_run_result via upsert_result.
    """
    Config.load_params()
    Config.ensure_dirs()
    try:
        from .manual_etf_sources import ensure_manual_sheets
        ensure_manual_sheets()
    except Exception as exc:
        # Le classeur peut être ouvert dans Excel; cela ne doit pas empêcher le
        # run, mais l'erreur reste explicite dans le journal.
        print(f"[runner] Initialisation des feuilles ETF manuelles impossible: {exc}")

    # Publier un état mémoire actif AVANT le warm-up FX et la lecture du gros
    # classeur broker. Sans cela, /live-state devait retomber sur SQLite durant
    # toute la préparation ; sous la pression openpyxl, le proxy Next finissait
    # régulièrement en ECONNRESET et l'UI affichait une phase « idle » figée.
    from . import progress_state

    if run_id is not None:
        progress_state.start(
            run_id=run_id,
            total=max(0, int(initial_total or 0)),
            unique_instruments=0,
        )
        progress_state.update(phase="preparation")

    # Taux devise->EUR de la colonne Volume : à précharger avant le scoring
    # (le garde fx._analysis_running bloque tout fetch FX pendant l'analyse).
    # Borné dans le temps, jamais bloquant pour le run (cf. currency.py) ; le
    # run est déjà créé à ce stade -> l'UI affiche la progression pendant ce
    # warm-up (#bug POST /buffett/run « ne fait rien »).
    from .currency import warm_fx_cache
    try:
        warm_fx_cache()
    except Exception as e:
        print(f"[runner] warm-up FX: {e}")

    # Les collecteurs broker et le registre d'indices évoluent entre deux runs.
    # SQLite étant désormais la source de vérité, réconcilier leurs caches
    # locaux AVANT de construire l'univers évite de conserver des ISIN/indices
    # absents et des disponibilités sans lien jusqu'à une migration manuelle.
    try:
        from app.services.finance.catalog.repository import (
            sync_local_broker_catalog_metadata,
        )
        catalog_sync = sync_local_broker_catalog_metadata()
        print(
            "[runner] Catalogue broker/ETF synchronisé: "
            f"{catalog_sync['availability_upserted']} disponibilités, "
            f"{catalog_sync['isin_filled']} ISIN, "
            f"{catalog_sync['registry_metadata']} métadonnées d'indice"
        )
    except Exception as e:
        # Un cache local corrompu ne doit pas supprimer un catalogue valide.
        print(f"[runner] Synchronisation catalogue broker/ETF impossible: {e}")

    # ETF = AUTORITAIRE depuis ToutBroker.xlsx (colonne 'Secteur 1' == 'ETF').
    # On relit le fichier à chaque run (il a pu être édité).
    from .broker_availability import reset_etf_cache
    reset_etf_cache()

    # Le périmètre du scoring dépend des comptes réellement financés, pas de la
    # totalité du catalogue mondial. Appliquer les soldes avant de lire l'univers
    # permet de ne conserver que l'union des titres explicitement achetables chez
    # au moins un broker dont le budget est strictement positif.
    from .broker_budgets import apply_live_broker_budgets

    try:
        budgets = apply_live_broker_budgets()
    except Exception as exc:
        return {"error": f"Chargement des soldes brokers impossible: {exc}"}
    funded_brokers = [
        broker for broker, amount in budgets.items() if float(amount or 0.0) > 0.0
    ]
    print(f"[runner] Budgets brokers (live): {budgets}")

    # Auto-correction des anciens caches ETF mal classés.
    # qui ne sont PLUS des ETF selon ToutBroker -> force leur réanalyse. Idempotent.
    try:
        from .cache_manager import purge_misclassified_etf_cache
        purged = purge_misclassified_etf_cache()
        if purged["removed"]:
            print(f"[runner] {purged['removed']} faux ETF purgés du cache "
                  f"({purged['files_deleted']} fichiers locaux supprimés) -> réanalyse")
    except Exception as e:
        print(f"[runner] purge faux ETF: {e}")

    try:
        tickers = load_tickers(csv_path)
    except Exception as exc:
        from .ticker_universe import TickerCatalogError

        if isinstance(exc, TickerCatalogError) and exc.diagnostics.row_count == 0:
            return {"error": "Aucun ticker dans tickers.csv"}
        return {"error": f"Catalogue ticker invalide: {exc}"}
    if not tickers:
        return {"error": "Aucun ticker dans tickers.csv"}
    # Les lignes actives de ``ETF_Manuels`` rejoignent le run en mémoire. Le
    # catalogue principal reste intact et l'identité ISIN/ticker sera contrôlée
    # lors de la superposition du catalogue broker.
    try:
        from .manual_etf_sources import load_manual_rows
        manual_tickers = [row["ETF_Ticker"] for row in load_manual_rows() if row["ETF_Ticker"]]
        tickers = list(dict.fromkeys([*tickers, *manual_tickers]))
    except Exception as exc:
        print(f"[runner] Lecture ETF_Manuels impossible: {exc}")

    from .fundamentals_resolver import (
        build_instrument_groups,
        load_fundamentals_links,
    )

    fundamentals_links = load_fundamentals_links()
    # Univers strict : seulement les actions/ETF explicitement disponibles chez
    # un broker financé. Une absence du catalogue ou une cellule vide ne signifie
    # jamais « achetable ». Désactivable uniquement pour les opérations de
    # maintenance explicites via BUFFETT_EXCLUDE_UNAVAILABLE=false.
    from app.core.config import settings
    if settings.buffett_exclude_unavailable:
        from .broker_availability import broker_investable_tickers

        if not funded_brokers:
            return {"error": "Aucun broker avec un solde positif : analyse non lancée"}
        investable = broker_investable_tickers(funded_brokers)
        if not investable:
            return {
                "error": "Aucun titre explicitement disponible chez les brokers financés"
            }
        before = len(tickers)
        tickers = [t for t in tickers if t.strip().upper() in investable]
        print(
            f"[runner] Filtre brokers financés {funded_brokers}: "
            f"{before} -> {len(tickers)} titres à analyser"
        )
        if not tickers:
            return {
                "error": "Le catalogue ticker ne contient aucun titre achetable "
                "chez les brokers financés"
            }

    groups = build_instrument_groups(tickers, fundamentals_links)
    # Plusieurs identités historiques peuvent exceptionnellement pointer vers
    # le même symbole fondamental (par exemple après correction d'un ISIN). Une
    # tâche Yahoo est définie par ce symbole, donc elle ne doit être comptée et
    # exécutée qu'une fois. On conserve toutefois tous les groupes pour propager
    # le résultat vers chacune de leurs cotations broker.
    analysis_tickers = list(dict.fromkeys(group.primary_symbol for group in groups))
    groups_by_primary: dict[str, list] = {}
    for group in groups:
        groups_by_primary.setdefault(group.primary_symbol, []).append(group)
    # Une reprise peut reutiliser un run qui contient encore des resultats issus
    # d'un univers plus large (par exemple avant activation du filtre broker).
    # Ces lignes restent utiles pour l'historique, mais ne doivent jamais revenir
    # dans la preparation ou l'optimisation de l'univers courant.
    current_result_tickers = {
        str(ticker).strip().upper()
        for ticker in (*tickers, *analysis_tickers)
        if str(ticker).strip()
    }
    secondary_count = sum(
        len(group.quote_symbols)
        - int(group.primary_symbol in group.quote_symbols)
        for group in groups
    )
    print(
        f"[runner] {len(tickers)} cotations -> {len(analysis_tickers)} tâches Yahoo "
        f"uniques ({len(groups)} groupes d'identité); "
        f"{secondary_count} cotations secondaires sans analyse Yahoo"
    )

    # Reprise : seul le résultat de la cotation principale marque l'instrument
    # comme analysé. Les secondaires seront reprojetées localement plus bas.
    total = len(analysis_tickers)
    done_tickers: set = set()
    if run_id is not None:
        try:
            from .reporting import get_done_tickers
            with session_factory() as s:
                done_tickers = get_done_tickers(s, run_id)
        except Exception as e:
            print(f"[runner] Lecture reprise: {e}")
    done_primary = {ticker for ticker in analysis_tickers if ticker in done_tickers}
    todo = [ticker for ticker in analysis_tickers if ticker not in done_primary]
    if run_id is not None:
        try:
            from app.services.finance.catalog.builder import load_registry
            catalog_version = load_registry().get("version")
        except Exception:
            catalog_version = None
        progress_state.start(
            run_id=run_id,
            total=total,
            catalog_version=catalog_version,
            already_completed=len(done_primary),
            unique_instruments=total,
            secondary_quotes_skipped=secondary_count,
        )
    if done_primary:
        print(
            f"[runner] Reprise: {len(done_primary)} instruments deja faits, "
            f"{len(todo)} restants / {total}"
        )

    if max_workers != 1:
        print(f"[runner] max_workers={max_workers} ignore : scoring inline impose")
    print(f"[runner] {len(todo)} tickers a analyser (mode inline)...")
    start_t = time.time()
    cache = CacheManager()
    from app.services.finance.yf_session import http_rate_limiter
    rate_limiter = http_rate_limiter()
    results: dict = {}
    deleted_tickers: set = set()
    deleted_lock = threading.Lock()
    n_done = len(done_primary)
    last_progress_done = n_done
    last_progress_at = time.monotonic()
    pending_results: list[tuple[str, float, dict]] = []

    # Publier immédiatement le total APRÈS exclusion des titres à zéro broker.
    # Sans cette mise à jour, le run conserve le total brut de tickers.csv et
    # termine visuellement à 10454/10490 alors que le scoring est bien achevé.
    if on_progress:
        try:
            on_progress(n_done, total)
        except Exception:
            pass

    def on_result(ticker, score, metrics):
        """Met les résultats en lot pour limiter les commits SQLite."""
        if run_id is None:
            return
        pending_results.append((ticker, score, metrics))
        if len(pending_results) < 50:
            return
        batch = list(pending_results)
        pending_results.clear()
        try:
            from .reporting import upsert_results_batch
            with session_factory() as session:
                upsert_results_batch(session, run_id, batch)
        except Exception as e:
            pending_results[:0] = batch
            print(f"[runner] persistance DB lot: {e}")
            return
        try:
            cache.checkpoint(every=100)
        except Exception as e:
            # La base reste la source de vérité du run; un échec de checkpoint
            # ne doit ni dupliquer le lot ni interrompre le scoring.
            print(f"[runner] checkpoint cache: {e}")

    def task(t):
        nonlocal n_done, last_progress_at, last_progress_done
        ok = _analyze_one(t, results, cache, rate_limiter,
                          deleted_tickers, deleted_lock, on_result=on_result)
        # Le débit/progrès mesure les résultats réellement terminés. Un échec
        # transitoire ne devient pas artificiellement un ticker « analysé ».
        if ok:
            n_done += 1
        progress_state.update(done=n_done, total=total)
        now = time.monotonic()
        publish = n_done == total or n_done - last_progress_done >= 50 or now - last_progress_at >= 5
        if on_progress and publish:
            try:
                on_progress(n_done, total)
                last_progress_done = n_done
                last_progress_at = now
            except Exception:
                pass
        return ok

    from .rate_limiter import set_active_limiter
    set_active_limiter(rate_limiter)
    failed_tickers: list[str] = []
    try:
        for ticker in todo:
            if progress_state.snapshot().get("stop_requested"):
                print("[runner] Scoring arrete a la demande utilisateur")
                break
            try:
                if not task(ticker):
                    progress_state.update(error_kind="transient")
                    failed_tickers.append(ticker)
            except Exception as exc:
                print(f"[runner] erreur inattendue {ticker}: {exc}")
                progress_state.update(error_kind="unknown")
                failed_tickers.append(ticker)
    finally:
        set_active_limiter(None)

    # Seuls les échecs transitoires arrivent ici. Les réponses Yahoo valides
    # mais vides (symbole invalide/délisté) sont déjà traitées définitivement
    # dans _analyze_one et ne sont jamais réessayées.
    retry_pass = 0
    from app.core.config import settings as app_settings
    max_retry_passes = max(0, int(app_settings.buffett_max_transient_retry_passes))
    while failed_tickers and retry_pass < max_retry_passes:
        if progress_state.snapshot().get("stop_requested"):
            print("[runner] Reessais Yahoo arretes a la demande utilisateur")
            break
        retry_pass += 1
        requests_before = rate_limiter.http_requests
        print(
            f"[runner] {len(failed_tickers)} echecs Yahoo transitoires, "
            f"nouvelle passe inline #{retry_pass}..."
        )
        next_failed: list[str] = []
        set_active_limiter(rate_limiter)
        try:
            for ticker in failed_tickers:
                if _analyze_one(
                    ticker,
                    results,
                    cache,
                    rate_limiter,
                    deleted_tickers,
                    deleted_lock,
                    on_result=on_result,
                ):
                    n_done += 1
                    progress_state.update(done=n_done, total=total)
                else:
                    next_failed.append(ticker)
        finally:
            set_active_limiter(None)
        print(
            f"[runner] Passe retry #{retry_pass}: "
            f"{len(failed_tickers) - len(next_failed)}/{len(failed_tickers)} recuperes"
        )
        if (
            len(next_failed) == len(failed_tickers)
            and rate_limiter.http_requests == requests_before
        ):
            # Une erreur locale de scoring/persistance ne doit pas créer une
            # boucle CPU sans aucune requête susceptible de changer le résultat.
            print("[runner] Reessais interrompus: aucun appel Yahoo n'a ete emis")
            break
        failed_tickers = next_failed

    if failed_tickers and retry_pass >= max_retry_passes:
        print(
            f"[runner] Reessais Yahoo bornes a {max_retry_passes} passe(s): "
            f"{len(failed_tickers)} ticker(s) restent a reprendre lors du prochain lancement"
        )

    if run_id is not None and pending_results:
        from .reporting import upsert_results_batch
        with session_factory() as session:
            upsert_results_batch(session, run_id, list(pending_results))
        pending_results.clear()

    cache.save()
    if deleted_tickers:
        remove_stale_tickers(csv_path, deleted_tickers)

    # Ne jamais optimiser/finaliser un univers incomplet. Les résultats déjà
    # écrits restent attachés au snapshot et la reprise ne retentera que les
    # tickers absents.
    if run_id is not None:
        from .reporting import get_done_tickers

        with session_factory() as session:
            persisted_done = get_done_tickers(session, run_id)
        persisted_primary = {
            ticker for ticker in analysis_tickers if ticker in persisted_done
        }
        n_done = len(persisted_primary)
        if n_done < total:
            missing = total - n_done
            progress_state.update(
                done=n_done,
                total=total,
                phase="paused",
                error_kind="incomplete",
            )
            if on_progress:
                on_progress(n_done, total)
            raise RuntimeError(
                f"run incomplet: {missing} ticker(s) Yahoo restent à reprendre; "
                "optimisation non lancée"
            )
    if on_progress:
        on_progress(n_done, total)

    progress_state.update(phase="preparation")

    # Les resultats sont deja persistes un a un (on_result). Pour l'optimisation
    # finale on recharge TOUT le run depuis la DB (inclut les tickers des sessions
    # precedentes en cas de reprise).
    if run_id is not None:
        try:
            from sqlmodel import select as _sel

            from app.models.finance import BuffettRunResult

            from .broker_availability import load_etf_tickers
            from .reporting import (
                update_run_buy_signal_diagnostics,
                upsert_results_batch,
            )
            from .sector_buy_signal import apply_sector_percentile_buy_signal

            with session_factory() as session:
                persisted_rows = list(session.exec(
                    _sel(BuffettRunResult).where(BuffettRunResult.run_id == run_id)
                ).all())
                rows = [
                    row for row in persisted_rows
                    if row.ticker.strip().upper() in current_result_tickers
                ]
                stale_rows_ignored = len(persisted_rows) - len(rows)
                rows_by_ticker = {row.ticker.upper(): row for row in rows}
                primary_rows = [
                    rows_by_ticker[ticker]
                    for ticker in analysis_tickers
                    if ticker in rows_by_ticker
                ]
                etf_quotes = load_etf_tickers()
                primary_etfs = {
                    group.primary_symbol
                    for group in groups
                    if any(quote.upper() in etf_quotes for quote in group.quote_symbols)
                }
                buy_diagnostics = apply_sector_percentile_buy_signal(
                    primary_rows,
                    etf_tickers=primary_etfs,
                    percentile=float(Config.BUY_SIGNAL_PERCENTILE),
                )
                for row in primary_rows:
                    session.add(row)
                session.commit()
                update_run_buy_signal_diagnostics(
                    session,
                    run_id,
                    buy_diagnostics,
                )
                propagated: list[tuple[str, float, dict]] = []
                for primary_row in primary_rows:
                    primary_groups = groups_by_primary.get(primary_row.ticker.upper(), [])
                    if not primary_groups:
                        continue
                    # Le score appartient à l'entreprise. Persister cette
                    # identité sur la cotation fondamentale permet à l'API de
                    # présenter une seule société, puis ses listings.
                    primary_extra = dict(primary_row.secteurs_extra or {})
                    primary_identity = next(
                        (
                            group.identity_key
                            for group in primary_groups
                            if group.identity_key
                        ),
                        primary_row.ticker,
                    )
                    primary_extra["entity"] = {
                        "company_id": primary_identity,
                        "isin": (
                            primary_identity
                            if primary_identity.upper() != primary_row.ticker.upper()
                            else None
                        ),
                        "fundamentals_symbol": primary_row.ticker.upper(),
                        "quote_symbol": primary_row.ticker.upper(),
                    }
                    primary_row.secteurs_extra = primary_extra
                    session.add(primary_row)
                    for group in primary_groups:
                        for quote in group.quote_symbols:
                            if quote.upper() == primary_row.ticker.upper():
                                continue
                            propagated.append((
                                quote,
                                primary_row.chance_moat or 0.0,
                                {
                                    "Nom": primary_row.nom,
                                    "Secteur": primary_row.secteur,
                                    "Volume": primary_row.volume,
                                    "Encours": (
                                        ((primary_row.secteurs_extra or {}).get("fund") or {})
                                        .get("aum")
                                    ),
                                    "Achat": bool(primary_row.achat),
                                    "Prix": primary_row.prix,
                                    "PER": primary_row.per,
                                    "PEG": primary_row.peg,
                                    "CAGR": (
                                        primary_row.croissance / 100.0
                                        if primary_row.croissance is not None
                                        else None
                                    ),
                                    "Pays": primary_row.pays,
                                    "FundamentalsSymbol": primary_row.ticker,
                                    "QuoteSymbol": quote,
                                    "ISIN": group.identity_key,
                                    "score_v3": dict(
                                        (primary_row.secteurs_extra or {}).get("scores") or {}
                                    ),
                                    "buffett_rules_score": (
                                        ((primary_row.secteurs_extra or {}).get("scores") or {})
                                        .get("buffett_rules_score")
                                    ),
                                },
                            ))
                if propagated:
                    upsert_results_batch(session, run_id, propagated)
                else:
                    session.commit()
                progress_state.update(propagated_quotes=len(propagated))
                persisted_rows = list(session.exec(
                    _sel(BuffettRunResult).where(BuffettRunResult.run_id == run_id)
                ).all())
                rows = [
                    row for row in persisted_rows
                    if row.ticker.strip().upper() in current_result_tickers
                ]
                results = {
                    row.ticker: (
                        row.chance_moat or 0.0,
                        {
                            "Nom": row.nom,
                            "Secteur": row.secteur,
                            "Volume": row.volume,
                            "Encours": (
                                ((row.secteurs_extra or {}).get("fund") or {}).get("aum")
                            ),
                            "Achat": bool(row.achat),
                            "Prix": row.prix,
                            "PER": row.per,
                            "PEG": row.peg,
                            "Pays": row.pays,
                            **dict((row.secteurs_extra or {}).get("scores") or {}),
                            "ISIN": (
                                ((row.secteurs_extra or {}).get("entity") or {}).get("isin")
                            ),
                            "company_id": (
                                ((row.secteurs_extra or {}).get("entity") or {}).get("company_id")
                            ),
                            "FundamentalsSymbol": (
                                ((row.secteurs_extra or {}).get("entity") or {}).get(
                                    "fundamentals_symbol"
                                )
                            ),
                            "score_model_version": (
                                ((row.secteurs_extra or {}).get("scores") or {}).get("model_version")
                            ),
                            "score_confidence_pct": (
                                ((row.secteurs_extra or {}).get("scores") or {}).get("confidence_pct")
                            ),
                            "score_comparable_to_standard": (
                                ((row.secteurs_extra or {}).get("scores") or {}).get(
                                    "comparable_to_standard", True
                                )
                            ),
                        },
                    )
                    for row in rows
                }
            print(
                f"[runner] {len(primary_rows)} instruments scores, "
                f"{len(propagated)} cotations secondaires propagees; "
                f"{stale_rows_ignored} anciens resultats hors univers ignores; "
                f"signal Achat médian sectoriel: {buy_diagnostics['accepted']} retenus, "
                f"{buy_diagnostics['missing_quality_total']} qualité absente "
                f"({buy_diagnostics['missing_quality_accepted']} retenus stricts, "
                f"{buy_diagnostics['missing_quality_excluded']} exclus)"
            )
        except Exception as e:
            print(f"[runner] Rechargement DB: {e}")

    # Reporter les scores/indicateurs dans ToutBroker.xlsx (upsert par ticker,
    # disponibilite broker preservee). Une fois, mono-thread, jamais bloquant.
    if run_id is not None:
        try:
            from sqlmodel import select as _sel_b

            from app.models.finance import BuffettRunResult

            from .broker_availability import update_broker_file_scores_isolated
            with session_factory() as session:
                bres = list(session.exec(
                    _sel_b(BuffettRunResult).where(BuffettRunResult.run_id == run_id)
                ).all())
            bres = [
                row for row in bres
                if row.ticker.strip().upper() in current_result_tickers
            ]
            progress_state.update(phase="preparation")
            n_written = update_broker_file_scores_isolated(bres)
            print(f"[runner] {n_written} scores ecrits dans ToutBroker.xlsx")
        except Exception as e:
            print(f"[runner] Ecriture ToutBroker: {e}")

    # Optimisation DE
    from . import optimization_progress as opt_prog
    opt_error: str | None = None
    try:
        import pandas as pd

        from .allocation import (
            average_turnover_eur_from_download,
            close_prices_from_download,
            discretize_allocation,
            latest_prices_eur,
        )
        from .broker_availability import (
            current_target_weights,
            merge_broker_columns,
        )
        from .dedup import (
            deduplicate_same_index,
            deduplicate_tickers,
            returns_in_base_currency,
        )
        from .optimizer import (
            meets_optimization_score_threshold,
            optimize_portfolio_de,
            prepare_optimization,
        )
        from .reporting import (
            fundamental_mismatch_tickers,
            score_calibration,
            persist_optimization_outcome,
            update_allocations,
        )
        from .transaction_costs import (
            estimate_rebalance_costs_by_broker,
            ttf_tickers_from_dataframe,
        )

        ticker_col = "Ticker Yahoo Finance"
        from .broker_availability import load_broker_table, load_etf_tickers
        broker_table = load_broker_table()
        etf_set = load_etf_tickers(broker_table)
        forced_tickers = [ticker.upper() for ticker in Config.FORCED_BUY_TICKERS]
        mismatch_tickers = fundamental_mismatch_tickers(results)
        score_calibration_diagnostics = score_calibration(results)
        eligible = {}
        for t, v in results.items():
            metrics = v[1]
            is_etf = (
                t.upper() in etf_set
                or str(metrics.get("InstrumentType") or metrics.get("Secteur") or "").upper() == "ETF"
            )
            mismatch = t.upper() in mismatch_tickers
            reasons = []
            if not is_etf:
                if mismatch:
                    reasons.append("FUNDAMENTAL_MISMATCH")
                if not bool(metrics.get("score_comparable_to_standard", True)):
                    reasons.append("NOT_COMPARABLE")
                if not bool(metrics.get("score_model_complete", metrics.get("model_complete", True))):
                    reasons.append("MODEL_INCOMPLETE")
            metrics["fundamental_mismatch"] = mismatch
            metrics["eligible_for_purchase"] = not reasons
            metrics["purchase_ineligibility_reasons"] = reasons
            if meets_optimization_score_threshold(
                t,
                v[0],
                Config.SCORE_THRESHOLD,
                forced_tickers,
                quality_score=v[1].get("buffett_quality_score"),
                confidence_pct=v[1].get("score_confidence_pct"),
                comparable_to_standard=bool(
                    v[1].get("score_comparable_to_standard", True)
                ),
                model_complete=bool(
                    v[1].get("score_model_complete", v[1].get("model_complete", True))
                ),
                fundamental_mismatch=mismatch,
                min_confidence_pct=Config.SCORE_MIN_CONFIDENCE_PCT,
                is_etf=is_etf,
            ):
                eligible[t] = v
        # Résoudre les cross-listings AVANT le filtre Achat. Sinon la cotation
        # principale peut être retirée sur son signal de valorisation tandis
        # qu'une cotation secondaire du même ISIN survit (ex. OR.PA/LOR.DE).
        if eligible:
            # Cette déduplication appartient déjà à la préparation du
            # portefeuille. La signaler ici évite que l'interface reste à
            # ``idle`` entre la fin du scoring et le téléchargement des cours.
            opt_prog.start(
                run_id=run_id,
                message=f"Déduplication des cotations… {len(eligible)} candidats",
            )
            progress_state.update(phase="preparation")
            preliminary = pd.DataFrame([{
                ticker_col: t,
                "Nom": v[1].get("Nom", ""),
                "Secteur": v[1].get("Secteur", ""),
                "Volume": v[1].get("Volume", 0),
            } for t, v in eligible.items()])
            preliminary = merge_broker_columns(preliminary, ticker_col)
            canonical = set(
                deduplicate_tickers(
                    pd.DataFrame(columns=list(eligible)),
                    preliminary,
                    ticker_col,
                ).columns
            )
            eligible = {t: v for t, v in eligible.items() if t in canonical}
        eligible = {t: v for t, v in eligible.items() if v[1].get("Achat", False)}
        # Filtre de liquidité : on n'alloue pas un titre sous le seuil de volume
        # échangé €/jour (sauf titres forcés). Évite la sur-pondération d'illiquides.
        from .liquidity import passes_portfolio_liquidity
        _forced = [f.upper() for f in Config.FORCED_BUY_TICKERS]
        before_liq = len(eligible)
        eligible = {
            t: v for t, v in eligible.items()
            if passes_portfolio_liquidity(
                v[1].get("Volume"),
                is_etf=(
                    t.upper() in etf_set
                    or "ETF" in str(v[1].get("Secteur", "")).upper()
                ),
                is_forced=t.upper() in _forced,
            )
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
        etf_names = {
            str(row.get(ticker_col) or "").strip().upper(): str(row.get("Nom") or "")
            for _, row in broker_table.iterrows()
            if str(row.get(ticker_col) or "").strip()
        }
        investable_etf_set = {
            ticker for ticker in etf_set
            if not is_leveraged_product(etf_names.get(ticker, ""))
        }
        before_lev = len(eligible)
        excluded_lev = [
            t for t, v in eligible.items()
            if t.upper() not in _forced
            and (
                t.upper() in etf_set
                or "ETF" in str(v[1].get("Secteur", "")).upper()
            )
            and is_leveraged_product(v[1].get("Nom", ""))
        ]
        eligible = {t: v for t, v in eligible.items() if t not in excluded_lev}
        if excluded_lev:
            print(f"[runner] Effet de levier/inverse: {before_lev - len(eligible)} titres "
                  f"ecartes ({', '.join(excluded_lev)})")
        # Inventaire ETF AVANT la présélection : déterminer d'abord quels fonds
        # sont synthétiques et l'indice exact qu'ils répliquent. La composition
        # détaillée des indices reste récupérée plus bas pour les candidats
        # présélectionnés, mais aucun ETF synthétique ne disparaît silencieusement.
        known: dict[str, dict] = {}
        try:
            from collections import Counter

            from .broker_availability import (
                _cell_state,
                _find_ticker_col,
                _match_broker_column,
            )
            from .etf_index_registry import (
                resolve_index_registry,
                sync_registry_to_broker_workbook,
            )
            from .official_etf_enrichment import enrich_unknown_etf_replications

            # Ne résoudre que les ETF effectivement achetables avec l'argent
            # disponible. Résoudre les ~15k ETF du catalogue mondial avant la
            # sélection annulait précisément le gain de la présélection.
            index_inventory_etfs = set(investable_etf_set)
            ticker_column = _find_ticker_col(
                broker_table.columns, "Ticker Yahoo Finance"
            ) if broker_table is not None else None
            active_columns = [
                column
                for broker, budget in Config.BUDGET_BROKERS.items()
                if float(budget or 0) > 0
                if (column := _match_broker_column(broker, broker_table.columns))
                is not None
            ] if broker_table is not None else []
            if ticker_column is not None and active_columns:
                index_inventory_etfs = {
                    str(row.get(ticker_column) or "").strip().upper()
                    for _, row in broker_table.iterrows()
                    if str(row.get(ticker_column) or "").strip().upper()
                    in investable_etf_set
                    and any(
                        _cell_state(row.get(column)) is True
                        for column in active_columns
                    )
                }

            opt_prog.set_phase(
                "preparation",
                "Inventaire ETF synthétiques — identification des indices…",
                done=0,
                total=len(index_inventory_etfs),
            )
            replication_diagnostics = enrich_unknown_etf_replications(
                index_inventory_etfs,
                allow_network=False,
                broker_table=broker_table,
                progress_cb=lambda done, total, ticker: opt_prog.set_phase(
                    "preparation",
                    f"Inventaire ETF — indices {done}/{total}"
                    + (f" · {ticker}" if ticker else ""),
                    done=done,
                    total=total,
                    current_item=ticker,
                ),
                should_stop=lambda: bool(opt_prog.snapshot()["stop_requested"]),
            )
            known = resolve_index_registry(
                index_inventory_etfs, broker_table=broker_table,
            )
            replication_diagnostics["catalog_etfs_skipped_before_index_resolution"] = max(
                len(investable_etf_set) - len(index_inventory_etfs), 0
            )
            statuses = Counter(
                str(value.get("replication") or "unknown") for value in known.values()
            )
            synthetic = {
                ticker: value
                for ticker, value in known.items()
                if str(value.get("replication") or "unknown") == "synthetic"
            }
            synthetic_missing = sorted(
                ticker for ticker, value in synthetic.items()
                if not str(value.get("index_id") or "").strip()
            )
            replication_diagnostics.update({
                "statuses": dict(statuses),
                "synthetic_total": len(synthetic),
                "synthetic_index_found": len(synthetic) - len(synthetic_missing),
                "synthetic_index_not_found": len(synthetic_missing),
                "synthetic_index_not_found_tickers": synthetic_missing,
                "inventory_before_correlation": True,
            })
            workbook_counts = sync_registry_to_broker_workbook()
            replication_diagnostics["workbook"] = workbook_counts
            print(
                "[runner] Inventaire ETF synthétiques: "
                f"{len(synthetic) - len(synthetic_missing)}/{len(synthetic)} indices identifiés; "
                f"{len(synthetic_missing)} NOT_FOUND; feuille ETF_Indices mise à jour"
            )
            isin_diagnostics = {"included_in_index_inventory": True}
        except Exception as exc:
            replication_diagnostics = {
                "total": len(etf_set),
                "known_before": 0,
                "unknown_before": len(etf_set),
                "resolved_now": 0,
                "unknown_after": len(etf_set),
                "statuses": {},
                "error": str(exc),
            }
            print(f"[runner] Identification des réplications ETF incomplète: {exc}")
            isin_diagnostics = {"error": str(exc)}
        # Classification AVANT tout historique : inutile de télécharger cinq ans
        # de cours ou de calculer les corrélations d'un instrument qui ne pourra
        # jamais être alloué faute de compartiment de risque fiable.
        from .sector_constraints import resolve_risk_categories

        risk_categories, classification_diagnostics = resolve_risk_categories(
            {
                ticker: values[1].get("Secteur", "")
                for ticker, values in eligible.items()
            },
            broker_table=broker_table,
        )
        classification_diagnostics["replication_enrichment"] = replication_diagnostics
        classification_diagnostics["isin_enrichment"] = isin_diagnostics
        classification_diagnostics["score_calibration"] = score_calibration_diagnostics
        classification_diagnostics["fundamental_mismatch"] = {
            "count": len(mismatch_tickers),
            "tickers": sorted(mismatch_tickers),
            "purchase_blocking": True,
        }
        classification_diagnostics["excluded_products"] = {
            "reason": "leveraged_or_inverse",
            "count": len(excluded_lev),
            "tickers": sorted(str(ticker).upper() for ticker in excluded_lev),
        }
        eligible = {
            ticker: values
            for ticker, values in eligible.items()
            if ticker.upper() in risk_categories
        }
        if classification_diagnostics["excluded"]:
            examples = classification_diagnostics["excluded_tickers"][:8]
            print(
                "[runner] Classification risque: "
                f"{classification_diagnostics['excluded']} titres écartés avant cours "
                f"(ex. {examples})"
            )

        # ── ETF : sélection + composition AVANT les historiques ───────────
        # Les actions restent toutes dans l'univers. Pour chaque indice exact et
        # chaque broker financé, un seul ETF est retenu depuis les métadonnées
        # locales (physique > swap > inconnu, puis encours/volume). Si sa
        # composition échoue, on l'exclut et le même classement promeut le fonds
        # suivant. Ce n'est qu'après stabilisation que les cours 5 ans sont lus.
        from .equity_lookthrough import etf_composition_quality, fetch_etf_holdings
        from .etf_selection import select_index_representatives_before_history

        preselection_columns = [
            ticker_col, "Nom", "Secteur", "Volume", "Encours", "Poids"
        ]
        preselection_pool = pd.DataFrame([{
            ticker_col: ticker,
            "Nom": values[1].get("Nom", ""),
            "Secteur": values[1].get("Secteur", ""),
            "Volume": values[1].get("Volume", 0),
            "Encours": values[1].get("Encours", values[1].get("AUM", 0)),
            "Poids": values[1].get("Poids", 0),
        } for ticker, values in eligible.items()], columns=preselection_columns)
        preselection_pool = merge_broker_columns(
            preselection_pool,
            ticker_col,
            broker_table=broker_table,
        )
        eligible_metadata = {
            str(ticker).strip().upper(): {
                **dict(values[1]),
                **dict(known.get(str(ticker).strip().upper(), {}) or {}),
            }
            for ticker, values in eligible.items()
        }
        constituent_metadata: dict[str, dict] = {
            ticker.upper(): {
                "country": values[1].get("Pays", ""),
                "sector": values[1].get("Secteur", ""),
            }
            for ticker, values in eligible.items()
            if ticker.upper() not in etf_set
        }
        if broker_table is not None and not broker_table.empty:
            broker_ticker_col = next((
                column for column in broker_table.columns
                if str(column).strip().casefold() == "ticker yahoo finance"
            ), None)
            if broker_ticker_col is not None:
                for _, raw_row in broker_table.iterrows():
                    symbol = str(raw_row.get(broker_ticker_col) or "").strip().upper()
                    if not symbol or symbol in etf_set:
                        continue
                    info = {
                        "country": raw_row.get("Pays", ""),
                        "sector": raw_row.get("Secteur", raw_row.get("Secteur 1", "")),
                    }
                    constituent_metadata.setdefault(symbol, info)
                    isin = str(raw_row.get("ISIN") or "").strip().upper()
                    if isin:
                        constituent_metadata.setdefault(f"ISIN:{isin}", info)

        economic_compositions: dict[str, dict] = {}
        from .etf_research_budget import EtfResearchBudget
        etf_research_budget = EtfResearchBudget()
        composition_quality: dict[str, dict] = {}
        etf_exclusions: set[str] = set()
        rejected_by_broker: dict[str, set[str]] = {}
        attempted_upfront: set[str] = set()
        initial_broker_candidates: dict[str, int] = {}
        preselection_round = 0
        etf_selection_diagnostics: dict = {}
        selected_etfs: set[str] = set()
        selected_etf_frame = preselection_pool
        maximum_rounds = max(1, int(Config.ETF_COMPOSITION_MAX_ROUNDS))
        while preselection_round < maximum_rounds:
            if opt_prog.snapshot()["stop_requested"]:
                break
            preselection_round += 1
            selected_etfs, selected_etf_frame, etf_selection_diagnostics = (
                select_index_representatives_before_history(
                    preselection_pool,
                    eligible_metadata,
                    etf_tickers=etf_set,
                    ticker_col=ticker_col,
                    excluded_tickers=etf_exclusions,
                )
            )
            if not initial_broker_candidates:
                initial_broker_candidates = {
                    broker: int(values.get("candidates_before", 0))
                    for broker, values in (
                        etf_selection_diagnostics.get("brokers") or {}
                    ).items()
                }
            pending = sorted(selected_etfs - attempted_upfront)
            if not pending:
                break
            attempted_upfront.update(pending)
            opt_prog.set_phase(
                "preparation",
                f"Compositions ETF — sélection avant cours {len(pending)} fonds",
                done=0,
                total=len(pending),
            )
            try:
                economic_compositions.update(fetch_etf_holdings(
                    pending,
                    budget=etf_research_budget,
                    refresh_indices=True,
                    should_stop=lambda: bool(opt_prog.snapshot()["stop_requested"]),
                    progress_cb=lambda stage, done, total, item: opt_prog.set_phase(
                        "preparation",
                        f"Compositions ETF — {stage} {done}/{total}"
                        + (f" · {item}" if item else ""),
                        done=done,
                        total=total,
                        current_item=item,
                    ),
                ))
            except Exception as exc:
                print(f"[runner] Compositions ETF indisponibles: {exc}")
            rejected: set[str] = set()
            for ticker in pending:
                quality = etf_composition_quality(
                    economic_compositions.get(ticker, {}),
                    eligible_metadata.get(ticker, {}),
                    minimum_coverage=float(
                        Config.ETF_ECONOMIC_COMPOSITION_MIN_COVERAGE
                    ),
                    constituent_metadata=constituent_metadata,
                )
                composition_quality[ticker] = quality
                if not quality.get("eligible"):
                    rejected.add(ticker)
            if not rejected:
                break
            for broker, values in (
                etf_selection_diagnostics.get("brokers") or {}
            ).items():
                broker_selected = {
                    str(value).strip().upper()
                    for value in values.get("selected_tickers", [])
                }
                rejected_by_broker.setdefault(broker, set()).update(
                    rejected & broker_selected
                )
            etf_exclusions.update(rejected)
            print(
                f"[runner] Compositions ETF: {len(rejected)} fonds refusés; "
                "promotion du suivant du même indice"
            )
            if opt_prog.snapshot().get("stop_requested"):
                opt_prog.finish(
                    message="Arrêté pendant la sélection des ETF avant les cours.",
                    status="stopped",
                    termination_reason="user_stop",
                )
                return {
                    "n_analyzed": total,
                    "n_secondary_quotes": secondary_count,
                    "n_eligible": len(eligible),
                    "duree_sec": round(time.time() - start_t, 1),
                    "n_deleted": len(deleted_tickers),
                    "error": None,
                    "stopped": True,
                }

        # On bounded exit, never admit the last rejected/unverified selection.
        selected_etfs = {
            ticker for ticker in selected_etfs
            if composition_quality.get(ticker, {}).get("eligible")
        }
        etf_selection_diagnostics["research_budget"] = etf_research_budget.snapshot()
        print(f"[runner] Budget recherches ETF: {etf_research_budget.snapshot()}; "
              f"{len(selected_etfs)} ETF vérifiés conservés après {preselection_round} vagues")
        action_tickers = {
            ticker for ticker in eligible if ticker.upper() not in etf_set
        }
        history_universe = action_tickers | selected_etfs
        selected_etf_frame = selected_etf_frame[
            selected_etf_frame[ticker_col].astype(str).str.upper().isin(history_universe)
        ].copy()
        etf_selection_diagnostics["n_etf_after"] = len(selected_etfs)
        for values in (etf_selection_diagnostics.get("brokers") or {}).values():
            values["selected_tickers"] = [
                ticker for ticker in values.get("selected_tickers", [])
                if str(ticker).upper() in selected_etfs
            ]
            values["selected"] = len(values["selected_tickers"])
        eligible = {
            ticker: values
            for ticker, values in eligible.items()
            if ticker in history_universe
        }
        preselection_broker_masks = {
            (str(row.get(ticker_col) or "").strip(), broker): bool(row.get(broker))
            for _, row in selected_etf_frame.iterrows()
            for broker, budget in Config.BUDGET_BROKERS.items()
            if budget > 0 and broker in selected_etf_frame.columns
            and str(row.get(ticker_col) or "").strip().upper() in selected_etfs
        }
        print(
            "[runner] Univers avant historiques: "
            f"{len(action_tickers)} actions + {len(selected_etfs)} ETF "
            f"({etf_selection_diagnostics.get('n_etf_before', 0)} candidats ETF)"
        )
        # Les anciennes feuilles ETF_Pays/ETF_Defensif ne sont plus une source.
        # Les ETF seront décrits plus bas depuis les actions de l'indice exact ;
        # ici, seules les actions directes reçoivent leur propre pays/secteur.
        from .breakdown import _canon_sector, is_economic_risk_sector
        from .country_normalization import canonical_country
        from .sector_lookthrough import DEFENSIVE_SECTORS

        country_exposures: dict[str, dict[str, float]] = {}
        sector_exposures: dict[str, dict[str, float]] = {}
        defensive_exposures: dict[str, float] = {}
        for ticker, values in eligible.items():
            key = str(ticker).strip().upper()
            if key in etf_set:
                continue
            country = canonical_country(values[1].get("Pays"))
            country_exposures[key] = (
                {country: 1.0}
                if country and country.casefold() not in {"inconnu", "unknown", "nan"}
                else {"Inconnu": 1.0}
            )
            sector = _canon_sector(risk_categories.get(key, "Inconnu"))
            if sector != "Inconnu" and is_economic_risk_sector(sector):
                sector_exposures[key] = {sector: 1.0}
                defensive_exposures[key] = 1.0 if sector in DEFENSIVE_SECTORS else 0.0
        country_diagnostics = {
            "method": "actions_directes_puis_constituants_officiels_indice",
            "refresh_tickers": [],
            "sources": {"action_metadata": len(country_exposures)},
        }
        # Le benchmark doit etre telecharge meme s'il n'est pas eligible : c'est la
        # reference du score, pas un candidat a l'allocation.
        bench_ticker = str(Config.STARR_BENCHMARK_TICKER).strip().upper()
        t_list = list(eligible.keys())
        if bench_ticker and bench_ticker not in {t.upper() for t in t_list}:
            t_list.append(bench_ticker)

        # Le portail reste conditionne aux candidats REELS (eligible), pas a
        # t_list : sinon le seul ajout du benchmark (ci-dessus) empecherait a
        # tort ce garde-fou de se declencher quand il n'y a aucun candidat
        # (t_list ne serait alors plus jamais vide).
        if eligible:
            # Signale le début de la phase de préparation AVANT le téléchargement
            # (potentiellement long, ~600 titres) -- sans ça, `optimization_progress`
            # reste à "idle" pendant toute cette étape et l'UI n'affiche RIEN
            # (ni barre, ni bouton stop) jusqu'à ce que le téléchargement finisse,
            # contrairement au bouton manuel "Créer le portefeuille optimal" qui
            # le fait déjà (cf. app/api/finance/buffett.py `_run_portfolio_creation`).
            opt_prog.set_phase(
                "preparation",
                "Téléchargement des cours…",
                done=0,
                total=len(t_list),
            )
            progress_state.update(phase="preparation")
            from app.services.finance.yf_session import download_prices_bulk_with_retry
            raw = download_prices_bulk_with_retry(
                t_list, period="5y", interval="1d", progress=False, group_by="ticker",
                use_cache=True,
                on_progress=lambda done, tot: opt_prog.set_phase(
                    "preparation",
                    f"Téléchargement des cours… {done}/{tot} titres",
                    done=done,
                    total=tot,
                ),
                should_stop=lambda: bool(opt_prog.snapshot()["stop_requested"]),
            )
            if opt_prog.snapshot().get("stop_requested"):
                opt_prog.finish(
                    message="Arrêté par l’utilisateur pendant la préparation.",
                    status="stopped",
                    termination_reason="user_stop",
                )
                return {
                    "n_analyzed": total,
                    "n_secondary_quotes": secondary_count,
                    "n_eligible": len(eligible),
                    "duree_sec": round(time.time() - start_t, 1),
                    "n_deleted": len(deleted_tickers),
                    "error": None,
                    "stopped": True,
                }
            if raw.empty:
                opt_prog.finish(message="Cours indisponibles.")
                opt_error = "Cours indisponibles (téléchargement des cours vide ou expiré)"
            else:
                # Prix/volumes ETF calculés ici, une fois, depuis les données
                # déjà présentes pour la corrélation. Zéro téléchargement en plus.
                etf_turnover = average_turnover_eur_from_download(raw, list(etf_set))
                for ticker, turnover in etf_turnover.items():
                    if ticker in eligible:
                        eligible[ticker][1]["Volume"] = turnover
                        eligible[ticker][1]["VolumeDevise"] = "EUR"
                from .allocation import drop_short_history
                cd = close_prices_from_download(raw, t_list)
                cd, too_young = drop_short_history(cd, int(Config.STARR_MIN_HISTORY_DAYS))
                if too_young:
                    print(f"[runner] Historique < {Config.STARR_MIN_HISTORY_DAYS} jours : "
                          f"{len(too_young)} titres écartés (ex. {too_young[:8]})")
                cd = cd.ffill()
                rets = cd.pct_change().dropna().clip(-0.5, 0.5)
                # Extraction du benchmark AVANT dedup/selection : ces etapes peuvent
                # l'ecarter (jumeau d'indice, plafond de 50 ETF/broker) alors qu'il
                # doit rester la reference du score.
                bench_rets = None
                bench_col = next(
                    (c for c in rets.columns if str(c).upper() == bench_ticker), None
                )
                if bench_col is not None:
                    bench_rets = returns_in_base_currency(
                        rets[[bench_col]], "EUR", strict=True
                    )[bench_col]
                    print(f"[runner] Benchmark {bench_ticker} : {len(bench_rets)} jours")
                    if bench_ticker not in {t.upper() for t in eligible}:
                        # Ajoute uniquement pour extraire son rendement (pas eligible,
                        # cf. plus haut) : ne doit pas rester un candidat a
                        # l'allocation, sinon prepare_optimization lui accorderait un
                        # acces broker par defaut (ticker absent de df_m -> True) et
                        # le DE pourrait l'acheter reellement.
                        rets = rets.drop(columns=[bench_col])
                else:
                    print(f"[runner] ATTENTION : benchmark {bench_ticker} absent des cours")
                if len(rets):
                    print(f"[runner] Fenêtre commune de rendements : {len(rets)} jours "
                          f"({rets.index[0].date()} -> {rets.index[-1].date()})")
                # bench_ticker peut avoir ete ajoute a t_list sans etre eligible (cf.
                # plus haut) : il n'a alors aucune entree dans `eligible`, donc on
                # l'exclut ici (sinon KeyError) -- ce tableau ne decrit que les
                # candidats reels a l'allocation.
                df_m = pd.DataFrame([{
                    ticker_col: t, "Nom": eligible[t][1].get("Nom", ""),
                    "Secteur": eligible[t][1].get("Secteur", ""),
                    "Risk Category": risk_categories.get(t.upper(), ""),
                    "Volume": eligible[t][1].get("Volume", 0),
                    "Chance MOAT": eligible[t][0], "Achat": True,
                } for t in t_list if t in eligible])
                # Disponibilite par broker depuis ToutBroker.xlsx (sinon tout dispo)
                df_m = merge_broker_columns(
                    df_m,
                    ticker_col,
                    broker_table=broker_table,
                )
                # Réappliquer les routes gagnantes de la présélection par indice.
                # Sans ceci, la fusion catalogue rendrait de nouveau chaque ETF
                # accessible sur tous ses brokers et deux représentants du même
                # indice pourraient être achetés ensemble.
                for (selected_ticker, broker), allowed in preselection_broker_masks.items():
                    if broker not in df_m.columns:
                        continue
                    mask = (
                        df_m[ticker_col].astype(str).str.strip().str.upper()
                        == selected_ticker.upper()
                    )
                    df_m.loc[mask, broker] = allowed
                opt_prog.set_phase(
                    "preparation",
                    "Déduplication (cross-listings, jumeaux d'indice)…",
                )
                rets = deduplicate_tickers(rets, df_m, ticker_col)
                # L'identité d'indice est plus précise et moins coûteuse que la
                # corrélation. Elle est résolue une fois par ISIN et conserve un
                # représentant par broker. La corrélation reste ensuite le filet
                # de sécurité pour les indices encore non résolus.
                rets = deduplicate_same_index(
                    rets,
                    df_m,
                    ticker_col,
                    broker_table=broker_table,
                )
                # À partir d'ici, TOUTE l'estimation (moyennes, corrélations,
                # copules, CVaR et STARR) est faite du point de vue d'un investisseur EUR.
                rets = returns_in_base_currency(rets, "EUR", strict=True)
                # Métadonnées des ACTIONS sous-jacentes. Les lignes ETF sont
                # exclues pour empêcher tout repli sur leur pays/secteur catalogue.
                constituent_metadata: dict[str, dict] = {
                    ticker.upper(): {
                        "country": values[1].get("Pays", ""),
                        "sector": values[1].get("Secteur", ""),
                    }
                    for ticker, values in eligible.items()
                    if ticker.upper() not in etf_set
                }
                for ticker, values in eligible.items():
                    isin = str(values[1].get("ISIN") or "").strip().upper()
                    if ticker.upper() not in etf_set and isin:
                        constituent_metadata[f"ISIN:{isin}"] = constituent_metadata[
                            ticker.upper()
                        ]
                if broker_table is not None and not broker_table.empty:
                    broker_ticker_col = next(
                        (
                            column
                            for column in broker_table.columns
                            if str(column).strip().casefold()
                            == "ticker yahoo finance"
                        ),
                        None,
                    )
                    if broker_ticker_col is not None:
                        for _, raw_row in broker_table.iterrows():
                            symbol = str(raw_row.get(broker_ticker_col) or "").strip().upper()
                            if not symbol or symbol in etf_set:
                                continue
                            info = {
                                "country": raw_row.get("Pays", ""),
                                "sector": raw_row.get("Secteur", ""),
                            }
                            constituent_metadata.setdefault(symbol, info)
                            isin = str(raw_row.get("ISIN") or "").strip().upper()
                            if isin:
                                constituent_metadata.setdefault(f"ISIN:{isin}", info)

                # L'univers ETF et ses compositions sont déjà figés avant le
                # téléchargement des cours. Il ne reste ici qu'à transformer les
                # compositions validées en expositions de risque.
                from .equity_lookthrough import (
                    _is_non_equity_etf,
                    economic_exposure_from_payload,
                    fetch_etf_holdings,
                    index_risk_lookthrough,
                    index_sector_country_lookthrough,
                )

                economic_minimum_coverage = float(
                    Config.ETF_ECONOMIC_COMPOSITION_MIN_COVERAGE
                )
                correlation_promotions: list[dict] = []
                round_index = preselection_round
                replacement_search_truncated = preselection_round >= maximum_rounds or etf_research_budget.exhausted()
                unverified_after_search_limit: set[str] = set()

                def report_etf_composition(
                    batch: int, stage: str, done: int, total: int, item: str,
                ) -> None:
                    nonlocal round_index
                    round_index = batch
                    label = {
                        "fonds": "fonds émetteurs",
                        "indices": "indices officiels",
                        "assemblage": "assemblage des expositions",
                    }.get(stage, stage)
                    current = str(item or "").strip()
                    message = (
                        f"Compositions ETF — lot {max(batch, 1)} · "
                        f"{label} {done}/{total}"
                        + (f" · {current}" if current else "")
                    )
                    opt_prog.set_phase(
                        "preparation",
                        message,
                        done=done,
                        total=total,
                        current_item=current,
                    )
                # Le classeur reste un filet de secours. La cible de reprise
                # doit provenir de la meilleure allocation réellement persistée
                # du même mode, sinon une ancienne exportation Excel peut
                # détrôner un champion exécutable plus récent.
                from .champion import select_best_stored_target

                previous_target_source = "workbook_fallback"
                previous_target_run_id = None
                previous_target_mode = None
                previous_target_score_rank = 0
                previous_target_historical_score = None
                previous_weights = {}
                if run_id is not None:
                    with session_factory() as champion_session:
                        selected_target = select_best_stored_target(
                            champion_session,
                            current_run_id=run_id,
                            requested_mode="actions_and_etfs",
                            include_legacy_as_requested=True,
                        )
                    previous_weights = selected_target["weights"]
                    previous_target_source = selected_target["source"]
                    previous_target_run_id = selected_target["run_id"]
                    previous_target_mode = selected_target["mode"]
                    previous_target_score_rank = selected_target["score_rank"]
                    previous_target_historical_score = selected_target[
                        "historical_score"
                    ]
                if not previous_weights:
                    previous_weights = current_target_weights(df_m, ticker_col)
                print(
                    "[runner] Champion précédent: "
                    f"source={previous_target_source}, run_id={previous_target_run_id}, "
                    f"score={previous_target_historical_score}"
                )
                ttf_tickers = ttf_tickers_from_dataframe(df_m, ticker_col)
                print(
                    "[runner] Présélection ETF : "
                    f"{etf_selection_diagnostics.get('n_etf_before', 0)} -> "
                    f"{etf_selection_diagnostics.get('n_etf_after', 0)} ETF dans l'union brokers"
                )
                t_opt = list(rets.columns)
                mat_access, active_b = prepare_optimization(t_opt, df_m)
                rows_by_asset = {
                    str(row[ticker_col]).strip(): row
                    for _, row in df_m.iterrows()
                    if str(row.get(ticker_col) or "").strip()
                }
                sector_by_ticker = {
                    ticker.upper(): risk_categories[ticker.upper()]
                    for ticker in t_opt
                    if ticker.upper() in risk_categories
                }
                # Matrice économique : la partie connue alimente les concentrations
                # par action; le reliquat exact alimente le plafond dur « Autres ».

                economic_action_exposures: dict[str, dict[str, float]] = {
                    ticker.upper(): {ticker.upper(): 1.0}
                    for ticker in t_opt
                    if ticker.upper() not in etf_set
                }
                economic_unknown_exposures: dict[str, float] = {}
                sector_country_exposures: dict[
                    str, dict[str, dict[str, float]]
                ] = {}
                coverage_by_ticker: dict[str, float] = {}
                etf_in_optimization = [
                    ticker for ticker in t_opt if ticker.upper() in etf_set
                ]
                if etf_in_optimization:
                    opt_prog.set_phase(
                        "preparation",
                        "Compositions économiques des ETF…",
                    )
                    try:
                        still_missing = [
                            ticker for ticker in etf_in_optimization
                            if ticker.upper() not in economic_compositions
                        ]
                        if still_missing:
                            economic_compositions.update(fetch_etf_holdings(
                                still_missing,
                                budget=etf_research_budget,
                                refresh_indices=True,
                                should_stop=lambda: bool(opt_prog.snapshot()["stop_requested"]),
                                progress_cb=lambda stage, done, total, item: (
                                    report_etf_composition(
                                        max(round_index, 1), stage, done, total, item
                                    )
                                ),
                            ))
                        action_compositions = economic_compositions
                    except Exception as exc:
                        print(f"[runner] Compositions actions ETF indisponibles: {exc}")
                        action_compositions = {}
                    for ticker in etf_in_optimization:
                        metadata = eligible_metadata.get(ticker.upper(), {})
                        if _is_non_equity_etf(metadata):
                            continue
                        clean, coverage, _, source_is_economic = economic_exposure_from_payload(
                            action_compositions.get(ticker.upper(), []),
                            minimum_coverage=0.0,
                        )
                        # Pour un synthétique sans constituants d'indice, le payload
                        # éventuel est du collatéral : 0 % connu économiquement.
                        if not source_is_economic:
                            clean, coverage = {}, 0.0
                        key = ticker.upper()
                        economic_action_exposures[key] = clean
                        economic_unknown_exposures[key] = max(0.0, 1.0 - coverage)
                        coverage_by_ticker[key] = coverage
                    etf_countries, etf_sectors, etf_defensive = index_risk_lookthrough(
                        action_compositions,
                        constituent_metadata,
                    )
                    sector_country_exposures = index_sector_country_lookthrough(
                        action_compositions,
                        constituent_metadata,
                    )
                    country_exposures.update(etf_countries)
                    sector_exposures.update(etf_sectors)
                    defensive_exposures.update(etf_defensive)
                    try:
                        from .etf_index_registry import sync_registry_to_broker_workbook

                        registry_counts = sync_registry_to_broker_workbook()
                        print(
                            "[runner] ToutBroker indices: "
                            f"{registry_counts['etf_indices']} correspondances, "
                            f"{registry_counts['constituants']} constituants"
                        )
                    except Exception as exc:
                        # Excel peut être ouvert : le registre JSON reste intact et
                        # la prochaine run retentera la publication des deux tables.
                        print(f"[runner] Tables d'indices ToutBroker non écrites: {exc}")
                # Actions directes : leur couple secteur-pays est exact. Les ETF
                # ne reçoivent jamais ce repli catalogue ; ils doivent conserver
                # la table conjointe calculée depuis leurs constituants officiels.
                for ticker in t_opt:
                    key = ticker.upper()
                    if key in etf_set:
                        continue
                    sectors = sector_exposures.get(key, {})
                    countries = country_exposures.get(key, {})
                    if sectors and countries:
                        sector_country_exposures[key] = {
                            sector: {
                                country: float(sector_weight) * float(country_weight)
                                for country, country_weight in countries.items()
                            }
                            for sector, sector_weight in sectors.items()
                        }
                from collections import Counter

                reason_counts = Counter(
                    str(value.get("reason") or "unknown")
                    for value in composition_quality.values()
                )
                index_status_counts = Counter(
                    str(value.get("index_status") or "no_status")
                    for value in composition_quality.values()
                )
                provider_counts = Counter(
                    str(value.get("provider") or "unknown")
                    for value in composition_quality.values()
                )
                # Les compteurs ci-dessus couvrent TOUS les ETF contrôlés, y
                # compris les éligibles. Le statut d'enrichissement d'indice
                # (« licence_required »…) peut donc dépasser le nombre d'ETF
                # réellement exclus. On publie aussi la répartition scindée aux
                # seuls non-éligibles, qui seule explique une exclusion.
                unresolved_reason_counts = Counter(
                    str(value.get("reason") or "unknown")
                    for value in composition_quality.values()
                    if not bool(value.get("eligible"))
                )
                unresolved_status_counts = Counter(
                    str(value.get("index_status") or "no_status")
                    for value in composition_quality.values()
                    if not bool(value.get("eligible"))
                )
                unresolved_indices = [
                    {
                        "ticker": ticker,
                        "replication": str(value.get("replication") or "unknown"),
                        "index": str(value.get("index") or ""),
                        "index_id": str(value.get("index_id") or ""),
                        "provider": str(value.get("provider") or "unknown"),
                        "status": str(value.get("index_status") or "no_status"),
                        "error": str(value.get("index_error") or ""),
                        "source_url": str(value.get("index_source_url") or ""),
                        "reason": str(value.get("reason") or "unknown"),
                        "pipeline_errors": list(value.get("enrichment_errors") or []),
                    }
                    for ticker, value in sorted(composition_quality.items())
                    if not bool(value.get("eligible"))
                ]
                economic_composition_filter = {
                    "quality_reference_coverage": economic_minimum_coverage,
                    "descriptive_only": False,
                    "excluded_for_economic_coverage": len(etf_exclusions),
                    "coverage_by_ticker": coverage_by_ticker,
                    "replaced_during_selection": len(etf_exclusions),
                    "replaced_tickers": sorted(etf_exclusions),
                    "quality_by_ticker": composition_quality,
                    "correlation_promotions": correlation_promotions,
                    "replacement_search": {
                        "rounds": round_index,
                        "batches": round_index,
                        "batch_buffer_per_broker": 0,
                        "selection_before_history": True,
                        "attempted_count": len(attempted_upfront),
                        "rejected_count": len(etf_exclusions),
                        "max_network_workers": int(Config.ETF_ENRICHMENT_MAX_WORKERS),
                        "max_rounds": maximum_rounds,
                        "research_budget": etf_research_budget.snapshot(),
                        "truncated": replacement_search_truncated,
                        "unverified_count": len(unverified_after_search_limit),
                        "unverified_tickers": sorted(unverified_after_search_limit),
                    },
                    "index_resolution": {
                        "checked_etfs": len(composition_quality),
                        "identified_indices": sum(
                            bool(str(value.get("index_id") or "").strip())
                            for value in composition_quality.values()
                        ),
                        "official_compositions": sum(
                            str(value.get("source") or "")
                            in {
                                "index_composition_cache",
                                "official_index_constituents",
                                "issuer_index_constituents",
                                "manual_official_index_constituents",
                            }
                            for value in composition_quality.values()
                        ),
                        "physical_tracker_proxies": sum(
                            str(value.get("source") or "")
                            in {"physical_tracker_proxy", "manual_physical_tracker_proxy"}
                            for value in composition_quality.values()
                        ),
                        "unresolved_count": len(unresolved_indices),
                        "status_counts": dict(index_status_counts),
                        "reason_counts": dict(reason_counts),
                        "provider_counts": dict(provider_counts),
                        "unresolved_reason_counts": dict(unresolved_reason_counts),
                        "unresolved_status_counts": dict(unresolved_status_counts),
                        "unresolved": unresolved_indices,
                    },
                    "broker_verification": {
                        broker: {
                            "target": int(values.get("indices", 0)),
                            "catalog_candidates": int(
                                initial_broker_candidates.get(
                                    broker, values.get("candidates_before", 0)
                                )
                            ),
                            "verified": int(values.get("selected", 0)),
                            "shortage": max(
                                int(values.get("indices", 0))
                                - int(values.get("selected", 0)),
                                0,
                            ),
                            "rejected": len(rejected_by_broker.get(broker, set())),
                            "rejected_tickers": sorted(rejected_by_broker.get(broker, set())),
                            "rejected_by_reason": dict(Counter(
                                str(composition_quality.get(ticker, {}).get("reason") or "unknown")
                                for ticker in rejected_by_broker.get(broker, set())
                            )),
                            "shortfall_reason": (
                                "eligible_catalog_exhausted"
                                if int(values.get("selected", 0))
                                < int(values.get("indices", 0))
                                else ""
                            ),
                        }
                        for broker, values in (
                            etf_selection_diagnostics.get("brokers") or {}
                        ).items()
                    },
                }
                classification_diagnostics["economic_composition_filter"] = (
                    economic_composition_filter
                )
                try:
                    from .manual_etf_sources import write_manual_status
                    written_manual = write_manual_status(
                        composition_quality, economic_compositions,
                    )
                    economic_composition_filter["manual_status_rows"] = written_manual
                except Exception as exc:
                    economic_composition_filter["manual_status_error"] = str(exc)
                total_cap = sum(Config.BUDGET_BROKERS.values())
                # Discrétisation : actions entières (hors Trading212) / pies (Trading212)
                prices = latest_prices_eur(cd, t_opt)
                # Figer les cours d'exécution AVANT de comparer les candidats.
                # Une cotation secondaire peut avoir un prix unitaire différent
                # de la principale : la charger après le DE changeait l'arrondi
                # et invalidait le score utilisé pour choisir le gagnant.
                from .execution import prepare_execution_quotes

                opt_prog.set_phase("preparation", "Chargement des cours d’exécution…")
                execution_routes, execution_prices = prepare_execution_quotes(
                    t_opt, active_b, mat_access, df_m, prices,
                )
                from .broker_positions import current_broker_weights
                with session_factory() as position_session:
                    broker_holdings = current_broker_weights(
                        position_session,
                        prices_eur=prices,
                        total_capital_eur=total_cap,
                        active_brokers=active_b,
                    )

                # Aucun enrichissement ETF paresseux : l'objectif ne doit jamais
                # basculer vers Yahoo ou les anciennes feuilles ToutBroker au
                # milieu d'une optimisation. Le registre officiel est figé avant DE.
                refresh_attempted: set[str] = set(attempted_upfront)
                refresh_failed: set[str] = set()
                refresh_lock = threading.Lock()
                refresh_ready = threading.Event()

                def _queue_selected_etfs(w_matrix) -> None:
                    return None

                def _consume_refresh_updates() -> list[dict]:
                    return []

                def _apply_refresh_updates(updates: list[dict]) -> list[str]:
                    return []

                def _on_new_best(w_matrix) -> None:
                    """Expose le meilleur candidat courant sans attendre la fin.

                    L'allocation finale reste validée et réécrite en fin de run,
                    mais persister le candidat discret permet à l'interface de
                    montrer un vrai portefeuille provisoire au lieu du Top 50
                    des scores individuels pendant une optimisation longue.
                    L'appel est déjà limité par ``optimize_portfolio_de``.
                    """
                    if run_id is None:
                        return
                    try:
                        provisional = discretize_allocation(
                            t_opt,
                            w_matrix,
                            active_b,
                            prices,
                            total_cap,
                            sector_by_ticker=sector_by_ticker,
                            sector_exposures_by_ticker=sector_exposures,
                            is_etf_tickers=etf_set,
                            execution_routes=execution_routes,
                            execution_prices=execution_prices,
                        )
                        if not provisional:
                            return
                        with session_factory() as provisional_session:
                            update_allocations(
                                provisional_session,
                                run_id,
                                provisional,
                                reset=True,
                            )
                    except Exception as exc:
                        print(f"[runner] Allocation provisoire non persistée: {exc}")

                # L'identité de cette optimisation a été créée avant la
                # déduplication. Ne pas la recréer ici : le frontend utiliserait
                # sinon deux historiques pour une même tentative.
                opt_prog.set_phase("preparation", "Préparation de l'optimisation…")
                progress_state.update(phase="optimisation")
                opt_prog.set_phase(
                    "optimisation",
                    f"Optimisation Differential Evolution ({len(t_opt)} titres)…",
                )
                def _executable_weights(continuous_weights):
                    """Version réellement achetable du portefeuille, pour la scorer.

                    Reconstruit une matrice de poids depuis une discrétisation en
                    actions entières / pies. La réserve de frais est calculée sur
                    la même cible, avec les positions courantes et les routes
                    d'exécution déjà connues, afin que le score comparé et
                    l'allocation finale correspondent au même ordre achetable.
                    """
                    from .allocation import alloc_to_weight_matrix

                    fee_reserve = estimate_rebalance_costs_by_broker(
                        t_opt,
                        continuous_weights,
                        active_b,
                        total_cap,
                        current_broker_holdings=broker_holdings,
                        is_etf_tickers=etf_set,
                        ttf_tickers=ttf_tickers,
                        execution_routes=execution_routes,
                    )
                    trial = discretize_allocation(
                        t_opt,
                        continuous_weights,
                        active_b,
                        prices,
                        total_cap,
                        sector_by_ticker=sector_by_ticker,
                        sector_exposures_by_ticker=sector_exposures,
                        execution_routes=execution_routes,
                        execution_prices=execution_prices,
                        fee_reserve_eur_by_broker=fee_reserve,
                    )
                    return alloc_to_weight_matrix(trial, t_opt, active_b, total_cap)

                user_stopped = False
                try:
                    seed_offset = 0
                    optimization_cycles: list[dict] = []
                    while True:
                        weights, metric, diagnostics = optimize_portfolio_de(
                            t_opt, rets, mat_access, active_b,
                            progress_cb=opt_prog.update_de,
                            initialization_cb=opt_prog.update_initialization,
                            discretize_cb=_executable_weights,
                            preparation_cb=lambda msg: opt_prog.set_phase("optimisation", msg),
                            on_new_best=_on_new_best,
                            on_candidate=_queue_selected_etfs,
                            should_stop=lambda: opt_prog.snapshot()["stop_requested"],
                            should_restart=refresh_ready.is_set,
                            continuous_until_stopped=True,
                            current_weights=previous_weights,
                            current_broker_holdings=broker_holdings,
                            sector_by_ticker=sector_by_ticker,
                            sector_exposures_by_ticker=sector_exposures,
                            defensive_exposures_by_ticker=defensive_exposures,
                            country_exposures=country_exposures,
                            economic_action_exposures=economic_action_exposures,
                            economic_unknown_exposures=economic_unknown_exposures,
                            sector_country_exposures_by_ticker=sector_country_exposures,
                            ttf_tickers=ttf_tickers,
                            benchmark_returns=bench_rets,
                            quality_scores_by_ticker={
                                ticker.upper(): float(eligible[ticker][1].get("buffett_quality_score") or 0.0)
                                for ticker in t_opt
                                if ticker in eligible and ticker.upper() not in etf_set
                            },
                            seed_number_offset=seed_offset,
                            return_diagnostics=True,
                        )
                        termination = diagnostics.get("termination", {})
                        user_stopped = termination.get("reason") == "user_stop"
                        seeds_run = max(1, int(termination.get("seeds_run", 1)))
                        seed_offset += seeds_run
                        optimization_cycles.append({
                            "cycle": len(optimization_cycles) + 1,
                            "reason": termination.get("reason"),
                            "seeds_run": seeds_run,
                            "seed_offset_after": seed_offset,
                        })
                        if termination.get("reason") != "etf_composition_refresh":
                            break

                        updates = _consume_refresh_updates()
                        refreshed = _apply_refresh_updates(updates)
                        if refreshed:
                            print(
                                "[runner] Compositions ETF actualisées pendant le DE: "
                                f"{refreshed}"
                            )

                        previous_weights = {
                            str(ticker): float(sum(weights[index]))
                            for index, ticker in enumerate(t_opt)
                        }
                        opt_prog.reset_objective_score(
                            "Compositions ETF actualisées — nouvel objectif STARR…"
                        )
                        opt_prog.set_phase(
                            "optimisation",
                            "Compositions ETF mises à jour — redémarrage du DE…",
                        )

                    # Si Stop a gagné la course contre un worker déjà lancé, on
                    # conserve tout de même les données pour l'analyse suivante,
                    # sans modifier l'allocation que l'utilisateur vient d'arrêter.
                    if refresh_ready.is_set():
                        deferred = _apply_refresh_updates(_consume_refresh_updates())
                        if deferred:
                            country_diagnostics["refreshed_after_stop"] = deferred

                    diagnostics["optimization_cycles"] = optimization_cycles
                    with refresh_lock:
                        country_diagnostics["attempted_tickers"] = sorted(
                            refresh_attempted
                        )
                        country_diagnostics["failed_tickers"] = sorted(refresh_failed)
                    diagnostics["etf_selection"] = etf_selection_diagnostics
                    diagnostics["classification_filter"] = classification_diagnostics
                    diagnostics["economic_composition_filter"] = (
                        economic_composition_filter
                    )
                    diagnostics["country_filter"] = country_diagnostics
                    diagnostics["portfolio_universe"] = {
                        "include_etfs": True,
                        "mode": "actions_and_etfs",
                        "previous_target_source": previous_target_source,
                        "previous_target_run_id": previous_target_run_id,
                        "previous_target_mode": previous_target_mode,
                        "previous_target_historical_score": (
                            previous_target_historical_score
                        ),
                        "previous_target_score_kind": (
                            "executable"
                            if previous_target_score_rank == 2
                            else "continuous"
                            if previous_target_score_rank == 1
                            else "unavailable"
                        ),
                    }
                finally:
                    # L'état reste actif pendant la discrétisation et la
                    # persistance. Le marquer terminé ici permettait aux
                    # comparaisons World de repartir après un clic sur Arrêter.
                    opt_prog.set_phase(
                        "finalisation",
                        "Finalisation du meilleur portefeuille…",
                    )

                # Réutiliser les cours figés de la comparaison exécutable.
                execution_fee_reserve = estimate_rebalance_costs_by_broker(
                    t_opt,
                    weights,
                    active_b,
                    total_cap,
                    current_broker_holdings=broker_holdings,
                    is_etf_tickers=etf_set,
                    ttf_tickers=ttf_tickers,
                    execution_routes=execution_routes,
                )
                alloc = discretize_allocation(
                    t_opt,
                    weights,
                    active_b,
                    prices,
                    total_cap,
                    sector_by_ticker=sector_by_ticker,
                    sector_exposures_by_ticker=sector_exposures,
                    execution_routes=execution_routes,
                    execution_prices=execution_prices,
                    fee_reserve_eur_by_broker=execution_fee_reserve,
                )
                diagnostics.setdefault("transaction_costs", {})[
                    "allocation_fee_reserve_eur_by_broker"
                ] = {
                    broker: float(value)
                    for broker, value in execution_fee_reserve.items()
                }
                diagnostics["transaction_costs"][
                    "allocation_reserve_matches_executable_score"
                ] = True
                if isinstance(diagnostics.get("executed_portfolio"), dict):
                    diagnostics["executed_portfolio"][
                        "fee_reserve_eur_by_broker"
                    ] = {
                        broker: float(value)
                        for broker, value in execution_fee_reserve.items()
                    }
                # Quatre hypothèses comparables. Les mêmes cours, expositions,
                # paramètres, seed et budget de générations reproduisent les
                # mêmes simulations; seul le plancher World change. ``free``
                # reste la cible active et les autres allocations sont des
                # snapshots de recherche, jamais des ordres.
                user_stopped = bool(
                    user_stopped or opt_prog.snapshot().get("stop_requested")
                )
                from .world_scenarios import SCENARIOS, identify_world_tickers, serialize_allocation

                world_metadata = {
                    str(ticker).upper(): {
                        **(eligible.get(ticker, ({}, {}))[1] if ticker in eligible else {}),
                        **(
                            rows_by_asset[ticker].to_dict()
                            if ticker in rows_by_asset and hasattr(rows_by_asset[ticker], "to_dict")
                            else {}
                        ),
                    }
                    for ticker in t_opt
                }
                world_tickers = identify_world_tickers(t_opt, world_metadata)
                world_tickers = {
                    ticker
                    for ticker in world_tickers
                    if ticker in {str(value).upper() for value in t_opt}
                    and any(mat_access[[str(value).upper() for value in t_opt].index(ticker)])
                }
                scenarios = {
                    "active": "free",
                    "free": {
                        "minimum_world_weight": 0.0,
                        "world_tickers": sorted(world_tickers),
                        "allocation": serialize_allocation(alloc),
                        "score": float(metric),
                        "diagnostics": {
                            key: diagnostics.get(key)
                            for key in (
                                "benchmark_relative", "score_breakdown", "sector_constraints",
                                "country_constraints", "region_constraints", "transaction_costs",
                                "estimation", "regimes", "world_constraint",
                            )
                        },
                    },
                }
                if user_stopped:
                    scenarios["skipped_reason"] = "user_stop"
                elif world_tickers:
                    comparison_generation_budget = max(
                        1,
                        int(
                            (diagnostics.get("termination") or {}).get(
                                "generations",
                                Config.STARR_DE_MAX_GENERATIONS,
                            )
                        ),
                    )
                    scenarios["methodology"] = {
                        "seed": 42,
                        "generation_budget": comparison_generation_budget,
                        "same_inputs": True,
                        "only_world_floor_changes": True,
                    }
                    for scenario_key, floor in SCENARIOS.items():
                        if scenario_key == "free":
                            continue
                        opt_prog.set_phase(
                            "optimisation",
                            f"Comparaison {scenario_key.replace('_', ' ')}…",
                        )
                        scenario_weights, scenario_score, scenario_diagnostics = optimize_portfolio_de(
                            t_opt, rets, mat_access, active_b,
                            seed=42,
                            discretize_cb=_executable_weights,
                            continuous_until_stopped=False,
                            current_weights=previous_weights,
                            current_broker_holdings=broker_holdings,
                            sector_by_ticker=sector_by_ticker,
                            sector_exposures_by_ticker=sector_exposures,
                            defensive_exposures_by_ticker=defensive_exposures,
                            country_exposures=country_exposures,
                            economic_action_exposures=economic_action_exposures,
                            economic_unknown_exposures=economic_unknown_exposures,
                            sector_country_exposures_by_ticker=sector_country_exposures,
                            ttf_tickers=ttf_tickers,
                            benchmark_returns=bench_rets,
                            quality_scores_by_ticker={
                                ticker.upper(): float(eligible[ticker][1].get("buffett_quality_score") or 0.0)
                                for ticker in t_opt
                                if ticker in eligible and ticker.upper() not in etf_set
                            },
                            world_tickers=world_tickers,
                            world_min_weight=floor,
                            max_generations=comparison_generation_budget,
                            return_diagnostics=True,
                        )
                        scenario_alloc = discretize_allocation(
                            t_opt,
                            scenario_weights,
                            active_b,
                            prices,
                            total_cap,
                            sector_by_ticker=sector_by_ticker,
                            sector_exposures_by_ticker=sector_exposures,
                            execution_routes=execution_routes,
                            execution_prices=execution_prices,
                            fee_reserve_eur_by_broker=estimate_rebalance_costs_by_broker(
                                t_opt,
                                scenario_weights,
                                active_b,
                                total_cap,
                                current_broker_holdings=broker_holdings,
                                is_etf_tickers=etf_set,
                                ttf_tickers=ttf_tickers,
                                execution_routes=execution_routes,
                            ),
                        )
                        scenarios[scenario_key] = {
                            "minimum_world_weight": floor,
                            "world_tickers": sorted(world_tickers),
                            "allocation": serialize_allocation(scenario_alloc),
                            "score": float(scenario_score),
                            "diagnostics": {
                                key: scenario_diagnostics.get(key)
                                for key in (
                                    "benchmark_relative", "score_breakdown", "sector_constraints",
                                    "country_constraints", "region_constraints", "transaction_costs",
                                    "estimation", "regimes", "world_constraint",
                                )
                            },
                        }
                else:
                    scenarios["unavailable_reason"] = (
                        "Aucun ETF répliquant le MSCI World large dans l'univers retenu"
                    )
                diagnostics["world_scenarios"] = scenarios
                from .allocation import allocation_sector_diagnostics
                post_sector = allocation_sector_diagnostics(
                    alloc,
                    total_cap=total_cap,
                    sector_by_ticker=sector_by_ticker,
                    sector_exposures_by_ticker=sector_exposures,
                )
                diagnostics["sector_constraints"]["post_discretization"] = post_sector
                diagnostics["sector_constraints"]["compliant"] = post_sector["compliant"]
                from .champion import allocation_replacement_decision

                replacement = allocation_replacement_decision(
                    diagnostics, min_improvement=Config.STARR_DE_MIN_IMPROVEMENT,
                )
                diagnostics["allocation_replacement"] = replacement
                replace_allocation = replacement["accepted"]
                replacement_reason = replacement["reason"]
                persisted_diagnostics = diagnostics
                if run_id is not None:
                    with session_factory() as session:
                        alloc, persisted_diagnostics = persist_optimization_outcome(
                            session, run_id, alloc, diagnostics,
                        )
                    print(
                        f"[runner] Allocation "
                        f"{'remplacee' if replace_allocation else 'conservee'} "
                        f"({len(alloc)} lignes retenues, {replacement_reason})"
                    )
                # Le fichier broker est lui aussi une cible active : ne pas y
                # écrire un candidat refusé par la comparaison exécutable.
                if replace_allocation:
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
                    log_portfolio_breakdown(
                        alloc,
                        country_exposures=country_exposures,
                        sector_exposures=sector_exposures,
                        defensive_exposures=defensive_exposures,
                    )
                except Exception as e:
                    print(f"[runner] breakdown: {e}")

                if user_stopped:
                    opt_prog.finish(
                        message="Arrêté par l’utilisateur — meilleur portefeuille conservé.",
                        status="stopped",
                        termination_reason="user_stop",
                    )
                else:
                    opt_prog.finish(
                        message="Optimisation terminée.",
                        status="completed",
                        termination_reason=(diagnostics.get("termination") or {}).get("reason"),
                    )

                return {
                    "n_analyzed": total,
                    "n_secondary_quotes": secondary_count,
                    "n_eligible": len(eligible),
                    "n_optimized": len(t_opt), "metric": metric,
                    "optimization": persisted_diagnostics,
                    "alloc": alloc, "duree_sec": round(time.time() - start_t, 1),
                    "n_deleted": len(deleted_tickers),
                    "error": None,
                }
    except Exception as e:
        print(f"[runner] Erreur optimisation: {e}")
        traceback.print_exc()
        opt_prog.finish(
            message=f"Erreur optimisation : {e}",
            status="error",
            termination_reason="error",
        )
        opt_error = str(e)

    return {
        "n_analyzed": total,
        "n_secondary_quotes": secondary_count,
        "duree_sec": round(time.time() - start_t, 1),
        "n_deleted": len(deleted_tickers),
        "error": opt_error,
    }


def analyze_single_ticker(
    ticker: str,
    cache: CacheManager | None = None,
    force: bool = False,
) -> tuple[float, dict] | None:
    """Analyse un seul ticker (bouton 'Analyser ticker unique').

    ETF -> MOAT non applicable, sans téléchargement individuel.
    Retourne (score, metrics) ou None si echec.
    """
    Config.load_params()
    Config.ensure_dirs()
    if cache is None:
        cache = CacheManager()
    is_empty_confirmed = getattr(cache, "is_empty_confirmed", lambda _ticker: False)
    if force and is_empty_confirmed(ticker):
        cache.invalidate(ticker)
    from app.services.finance.yf_session import http_rate_limiter
    rate_limiter = http_rate_limiter()
    results: dict = {}
    dummy_deleted: set = set()
    dummy_lock = threading.Lock()

    ok = _analyze_one(
        ticker,
        results,
        cache,
        rate_limiter,
        dummy_deleted,
        dummy_lock,
        force=force,
    )
    if ok and ticker in results:
        cache.save()
        return results[ticker]
    return None
