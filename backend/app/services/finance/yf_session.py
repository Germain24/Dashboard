"""Session HTTP impersonée (anti rate-limit / blocage yfinance).

Yahoo Finance bloque de plus en plus les requêtes identifiées comme provenant
d'un script. La parade fiable est une session `curl_cffi` qui usurpe l'empreinte
TLS/HTTP d'un vrai navigateur (Chrome). On la passe à `yf.Ticker/Tickers/download`
via leur paramètre `session=`.

Usage :
    from app.services.finance.yf_session import yf_session
    t = yf.Ticker(symbol, session=yf_session())

`yf_session()` renvoie `None` si `curl_cffi` est indisponible — dans ce cas
yfinance retombe sur son comportement par défaut (pas de régression).

Une session unique est conservée dans le process. yfinance 1.5 utilise lui-même
un singleton ``YfData`` (session, cookie et crumb partagés) : lui injecter une
session différente par worker écrase sa session globale sans renouveler le
crumb, ce qui provoque des rafales de 401 ``Invalid Crumb``. Le scoring Buffett
est donc inline et toutes les requêtes utilisent cette même session cohérente.
"""

from __future__ import annotations

import random
import threading
from pathlib import Path

_session = None
_session_lock = threading.RLock()
_request_lock = threading.Lock()
_http_limiter = None


def _get_http_limiter():
    """Retourne l'unique cadence process-wide de 2 000 requêtes/heure."""
    global _http_limiter
    with _session_lock:
        if _http_limiter is None:
            from app.services.finance.buffett.rate_limiter import RateLimiter
            _http_limiter = RateLimiter()
        return _http_limiter


def http_rate_limiter():
    """Expose le quota HTTP partagé pour l'état de progression Buffett."""
    return _get_http_limiter()


def _wait_for_global_slot() -> None:
    """Réserve une requête réelle, espacée de la précédente d'au moins 1,8 s."""
    _get_http_limiter().wait_for_slot()


def _wrap_session_with_throttle(session):
    """Compte une fois chaque requête réelle au niveau de ``Session.request``.

    ``curl_cffi.Session.get/post`` délèguent à ``self.request``. Envelopper les
    trois méthodes comptait donc potentiellement deux fois le même appel.
    """
    if session is None:
        return None
    original = getattr(session, "request", None)
    if original is not None and not getattr(session, "_mission_control_limited", False):
        def _throttled(*args, **kwargs):
            # curl_cffi n'est pas garanti thread-safe. Les autres modules Finance
            # peuvent appeler Yahoo pendant le scoring inline. Réserver le créneau
            # SOUS ce verrou garantit que l'ordre des réservations est bien l'ordre
            # réel de départ des requêtes.
            with _request_lock:
                _wait_for_global_slot()
                return original(*args, **kwargs)

        session.request = _throttled
        session._mission_control_limited = True
    return session


# Empreinte de navigateur à usurper (curl_cffi). Chrome récent = profil le plus sûr.
IMPERSONATE = "chrome"

# Timeout par défaut (s) de CHAQUE requête HTTP faite via cette session -- sans
# lui, une connexion qui ne répond jamais (stall réseau, pas une erreur HTTP)
# bloque le thread indéfiniment. Constaté en prod : un run Buffett bloqué à
# quelques tickers de la fin, aucune progression pendant plusieurs minutes,
# process toujours "actif" (verrou tenu) -- un simple restart ne règle rien
# tant que la connexion suivante peut re-staller sur n'importe quel ticker.
DEFAULT_TIMEOUT_S = 20.0


def _proxy_pool() -> list[str]:
    """Proxys configurés (settings.yf_proxies, .env: YF_PROXIES), nettoyés."""
    try:
        from app.core.config import settings

        raw = settings.yf_proxies or ""
    except Exception:
        raw = ""
    return [p.strip() for p in raw.split(",") if p.strip()]


def _new_session():
    """Crée une session curl_cffi impersonée, derrière un proxy au hasard si
    configuré (rotation d'IP), et throttlée (cf. `_wrap_session_with_throttle`).
    None si curl_cffi est indisponible."""
    try:
        from curl_cffi import requests as cffi_requests

        kwargs = {"impersonate": IMPERSONATE, "timeout": DEFAULT_TIMEOUT_S}
        pool = _proxy_pool()
        if pool:
            proxy = random.choice(pool)
            kwargs["proxies"] = {"http": proxy, "https": proxy}
        return _wrap_session_with_throttle(cffi_requests.Session(**kwargs))
    except Exception:
        return None


def yf_session():
    """Retourne l'unique session cohérente avec le singleton interne yfinance."""
    global _session
    with _session_lock:
        if _session is None:
            _session = _new_session()
        return _session


DOWNLOAD_TIMEOUT_S = 180.0  # borne dure sur l'appel `yf.download()` en entier


def download_with_timeout(timeout_s: float = DOWNLOAD_TIMEOUT_S, **kwargs):
    """`yf.download(**kwargs)` avec un timeout GLOBAL dur sur l'appel entier,
    en plus du timeout par requête HTTP de la session (`DEFAULT_TIMEOUT_S`).

    Le chemin "bulk download" de yfinance (utilisé pour ~600 titres avant
    l'optimisation DE) ne respecte pas toujours ce dernier pour chaque
    sous-requête interne -- constaté en prod : un run resté bloqué PLUS DE 2H
    dans un unique `yf.download()`, alors que le scoring par-ticker (même
    session) se débloquait bien après 20s. Exécuté dans un thread séparé :
    si `timeout_s` est dépassé, ce thread continue en arrière-plan (Python ne
    peut pas tuer un thread proprement) mais n'est plus jamais consulté --
    fuite de thread acceptable pour éviter de bloquer TOUT le run. Renvoie un
    DataFrame vide au timeout (mêmes appelants : `if not raw.empty: ...`).
    """
    import concurrent.futures

    import pandas as pd
    import yfinance as yf

    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = ex.submit(yf.download, **kwargs)
    try:
        return future.result(timeout=timeout_s)
    except concurrent.futures.TimeoutError:
        return pd.DataFrame()
    finally:
        ex.shutdown(wait=False)


def _split_by_availability(raw, requested: list[str]):
    """Depuis un DataFrame `yf.download(group_by='ticker')` (colonnes MultiIndex
    (ticker, champ)), separe `requested` en (tickers obtenus, tickers encore
    manquants). Un ticker est "obtenu" s'il est present dans les colonnes ET a
    au moins une valeur non-NaN (absent des colonnes OU entierement NaN =
    manquant -- c'est ainsi que `yf.download` signale un ticker en echec au
    sein d'un lot par ailleurs reussi)."""
    import pandas as pd

    if raw is None or raw.empty:
        return pd.DataFrame(), list(requested)
    level0 = set(raw.columns.get_level_values(0))
    obtained, missing = [], []
    for t in requested:
        if t in level0 and not raw[t].isna().all().all():
            obtained.append(t)
        else:
            missing.append(t)
    if not obtained:
        return pd.DataFrame(), missing
    return raw[obtained], missing


# Taille des lots du telechargement groupe. Un yf.download unique de milliers
# de tickers ne peut JAMAIS finir sous un timeout de 180s des lors que le
# quota global de 2 000 requêtes par heure. #bug rapporte : 2898 tickers
# eligibles -> 3 tentatives vides -> run
# termine sans allocation ("Cours indisponibles").
BULK_CHUNK_SIZE = 50


def _chunk_timeout_s(n_tickers: int) -> float:
    """Timeout d'un lot hors temps normal nécessaire au quota horaire.

    yfinance peut émettre plusieurs requêtes par symbole. La marge de quatre
    créneaux par ticker empêche le timeout global de prendre l'attente volontaire
    de 1,8 s pour un blocage réseau.
    """
    from app.services.finance.buffett.config import Config

    interval = 3600.0 / max(Config.YAHOO_REQUESTS_PER_HOUR, 1)
    return DOWNLOAD_TIMEOUT_S + n_tickers * interval * 4.0


# Cache quotidien des CLOTURES ET VOLUMES par (ticker, period, interval) --
# uniquement les colonnes necessaires aux appelants (`Close` pour correlations
# et optimisation, `Volume` pour la liquidite). Cela reste bien plus leger que
# l'OHLCV complet tout en evitant qu'un cache hit transforme le volume en donnee
# inconnue. Opt-in (`use_cache=True`) : le bouton
# "Creer le portefeuille optimal" re-telechargait les MEMES ~2900 cours 5 ans
# que le run venait d'obtenir, pour rien.
# Deux niveaux : memoire (rapide) + disque (pickle par ticker) -- le disque
# survit aux redemarrages d'uvicorn --reload (chaque edition de code tuait le
# cache memoire et faisait repayer ~3h de telechargement a la reprise).
_bulk_close_cache: dict = {}  # (ticker, period, interval) -> (date, DataFrame)

PRICE_CACHE_DIR = Path(__file__).resolve().parents[4] / "data" / "cache" / "price_history"


def _cache_filename(ticker: str, key: tuple) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9._-]", "_", f"{ticker}__{key[0]}_{key[1]}") + ".pkl"


def _bulk_cache_get(ticker: str, key: tuple, today):
    """Close/Volume du jour, memoire puis disque.

    Les anciens fichiers contiennent une ``Series`` Close. Ils restent lisibles
    afin qu'une mise a jour ne force pas le retelechargement de milliers de
    cours ; le volume restera simplement absent jusqu'au prochain remplissage.
    """
    entry = _bulk_close_cache.get((ticker, *key))
    if entry and entry[0] == today:
        return entry[1]
    try:
        import pickle
        path = PRICE_CACHE_DIR / _cache_filename(ticker, key)
        if path.exists():
            with open(path, "rb") as f:
                day, series = pickle.load(f)
            if day == today:
                _bulk_close_cache[(ticker, *key)] = (today, series)
                return series
    except Exception:
        pass
    return None


def _bulk_cache_put(ticker: str, key: tuple, today, frame) -> None:
    """Stocke Close/Volume en memoire ET sur disque (best-effort)."""
    _bulk_close_cache[(ticker, *key)] = (today, frame)
    try:
        import pickle
        PRICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(PRICE_CACHE_DIR / _cache_filename(ticker, key), "wb") as f:
            pickle.dump((today, frame), f)
    except Exception:
        pass


def clear_bulk_cache() -> None:
    """Vide le cache MEMOIRE des clotures (tests / rafraichissement force).
    Le cache disque expire seul (date du jour verifiee a la lecture)."""
    _bulk_close_cache.clear()


def download_prices_bulk_with_retry(
    tickers: list[str], *, retries: int = 2, cooldown_s: float = 30.0,
    chunk_size: int = BULK_CHUNK_SIZE, on_progress=None, should_stop=None,
    use_cache: bool = False,
    **download_kwargs,
):
    """Telechargement groupe PAR LOTS de `chunk_size` tickers, chaque lot avec
    un timeout proportionnel a sa taille (cf. `_chunk_timeout_s`), avec une
    nouvelle tentative PAR TICKER : seuls les tickers encore sans donnees sont
    redemandes (ceux deja obtenus ne sont pas re-telecharges) ; un ticker
    toujours sans donnees apres `retries` tentatives est ignore (absent du
    resultat final) SANS faire echouer les autres.

    `on_progress(n_traites, n_total)` est appele apres chaque lot (best-effort).
    `should_stop()` permet une interruption cooperative entre deux lots : le lot
    courant finit proprement et les donnees deja obtenues sont conservees.

    Un rate-limit Yahoo Finance transitoire (frequent juste apres une rafale de
    milliers de requetes individuelles de scoring -- cf. `runner.py`) peut faire
    echouer une partie ou la totalite d'un telechargement groupe en quelques
    secondes, bien avant le timeout du lot (#bug rapporte : le run finissait en
    erreur ~40s apres la fin du scoring ; et un run pouvait s'arreter en erreur
    a cause d'une poignee de tickers persistants alors que le reste du lot
    etait disponible). Le resultat n'est vide QUE si aucun ticker n'a jamais
    pu etre obtenu."""
    import datetime as _dt

    import pandas as pd

    remaining = list(tickers)
    n_total = len(remaining)
    frames = []

    cache_key = (str(download_kwargs.get("period")), str(download_kwargs.get("interval")))
    today = _dt.date.today()
    if use_cache:
        hits = {}
        for t in remaining:
            cached = _bulk_cache_get(t, cache_key, today)
            if cached is not None:
                if isinstance(cached, pd.Series):
                    hits[t] = pd.DataFrame({"Close": cached})
                else:
                    columns = [c for c in ("Close", "Volume") if c in cached.columns]
                    if "Close" in columns:
                        hits[t] = cached[columns].copy()
        if hits:
            frames.append(pd.concat(hits, axis=1))
            remaining = [t for t in remaining if t not in hits]
            print(f"[yf_session] {len(hits)} ticker(s) servis par le cache du jour, "
                  f"{len(remaining)} a telecharger")
            if on_progress is not None:
                try:
                    on_progress(len(hits), n_total)
                except Exception:
                    pass

    attempt = 0
    stopped = False
    while remaining:
        if should_stop is not None and should_stop():
            break
        still_missing: list[str] = []
        n_processed = n_total - len(remaining)
        for i in range(0, len(remaining), chunk_size):
            if should_stop is not None and should_stop():
                stopped = True
                break
            chunk = remaining[i:i + chunk_size]
            raw = download_with_timeout(
                timeout_s=_chunk_timeout_s(len(chunk)),
                tickers=chunk, session=yf_session(), **download_kwargs,
            )
            obtained_df, missing = _split_by_availability(raw, chunk)
            if not obtained_df.empty:
                frames.append(obtained_df)
                if use_cache:
                    for t in set(obtained_df.columns.get_level_values(0)):
                        try:
                            available = [
                                c for c in ("Close", "Volume")
                                if c in obtained_df[t].columns
                            ]
                            if "Close" in available:
                                _bulk_cache_put(
                                    t,
                                    cache_key,
                                    today,
                                    obtained_df[t][available].copy(),
                                )
                        except Exception:
                            pass
            still_missing.extend(missing)
            n_processed += len(chunk)
            if on_progress is not None:
                try:
                    on_progress(n_processed, n_total)
                except Exception:
                    pass
            if should_stop is not None and should_stop():
                stopped = True
                break
        if stopped:
            break
        remaining = still_missing
        if not remaining:
            break
        attempt += 1
        if attempt > retries:
            print(f"[yf_session] {len(remaining)} ticker(s) sans donnees apres {retries} "
                  f"tentative(s) -- ignores : {remaining}")
            break
        print(
            f"[yf_session] {len(remaining)} ticker(s) sans donnees "
            f"(tentative {attempt}/{retries}) -> reprise différée immédiate"
        )

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, axis=1)


def rotate_session():
    """Recrée la session et invalide aussi le cookie/crumb singleton de yfinance."""
    global _session
    with _session_lock:
        _session = None
        try:
            from yfinance.data import YfData
            data = YfData()
            with data._cookie_lock:
                data._session = None
                data._cookie = None
                data._crumb = None
        except Exception:
            pass


def reset_sessions() -> None:
    """Réinitialise la session et le quota global (isolation des tests)."""
    global _http_limiter
    rotate_session()
    with _session_lock:
        _http_limiter = None


def _pence_divisor(fast_info) -> float:
    """100 si le titre est coté en pence (GBX/GBp, convention LSE), sinon 1.

    Yahoo Finance cote les valeurs londoniennes en pence (ex. "GBp") tout en
    répondant `currency="GBP"` ailleurs dans l'API -- sans cette conversion,
    un cours en pence traité comme des livres gonfle la valeur ×100 (ex. un
    ETC or à 59,29 £ remonte comme 5929, cf. #bug SGLN.L)."""
    try:
        try:
            c = fast_info["currency"]
        except Exception:
            c = getattr(fast_info, "currency", None)
        if c in ("GBp", "GBX"):  # pence -- distinct de "GBP" (livres)
            return 100.0
    except Exception:
        pass
    return 1.0


def fast_last_price(ticker_obj) -> float:
    """Dernier cours d'un yf.Ticker, robuste, normalisé en unité principale de
    la devise (jamais en pence pour les titres londoniens, cf. `_pence_divisor`).

    ⚠️ Dans yfinance 1.x, `FastInfo.get("last_price")` est cassé : il renvoie
    toujours le défaut (None). On accède donc par CLÉ (`fast_info["last_price"]`)
    puis on retombe sur le dernier close de l'historique si besoin (certains
    titres n'ont pas de last_price intraday). Renvoie 0.0 en dernier recours.
    """
    # 1) fast_info par clé (PAS .get — bug yfinance)
    try:
        fi = ticker_obj.fast_info
        try:
            v = fi["last_price"]
        except Exception:
            v = getattr(fi, "last_price", None)
        if v:
            return float(v) / _pence_divisor(fi)
    except Exception:
        pass
    # 2) repli : dernier close de l'historique récent
    try:
        hist = ticker_obj.history(period="5d")
        closes = hist["Close"].dropna()
        if len(closes):
            return float(closes.iloc[-1]) / _pence_divisor(getattr(ticker_obj, "fast_info", None))
    except Exception:
        pass
    return 0.0
