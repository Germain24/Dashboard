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

Thread-local, PAS un singleton process-wide : l'analyse Buffett complète
lance jusqu'à 10 workers (`ThreadPoolExecutor`) qui appellent `yf_session()`
concurremment. `curl_cffi` (bindings natifs autour de libcurl) n'est pas
garanti thread-safe pour un usage concurrent du MÊME objet Session — un
singleton partagé provoquait un crash natif intermittent du process (aucune
trace Python : `job_monthly_buffett` catch déjà toute Exception avec
exc_info=True, donc un crash sans traceback loggé n'est pas une exception
Python). Une session par thread élimine le partage.
"""

from __future__ import annotations

import random
import threading
import time

_local = threading.local()

# Yahoo Finance limite a 2000 requetes/minute -- espace CHAQUE requete HTTP
# sortante d'au moins cet intervalle, PEU IMPORTE l'appelant (scoring par
# ticker, telechargement groupe pour l'optimisation DE, conversion FX, cours
# de portefeuille, snapshots...). #bug rapporte : un telechargement groupe de
# ~900 tickers d'un coup (ou une rafale d'appels FX) declenchait un rate-limit
# meme si le volume total sur l'heure restait sous un plafond plus large (le
# RateLimiter de buffett/rate_limiter.py ne couvre QUE le scoring par ticker).
GLOBAL_MIN_INTERVAL_S = 60.0 / 2000  # 0.03s

_global_lock = threading.Lock()
_global_next_slot = 0.0


def _wait_for_global_slot() -> None:
    """Bloque jusqu'a ce qu'au moins GLOBAL_MIN_INTERVAL_S se soit ecoule
    depuis la derniere requete HTTP Yahoo Finance (thread-safe, file d'attente
    "prochain crenau disponible" -- des appels concurrents sont mis en fille
    et espaces plutot que de tous passer en meme temps des que le verrou se
    libere)."""
    global _global_next_slot
    with _global_lock:
        now = time.monotonic()
        wait = _global_next_slot - now
        _global_next_slot = (now + GLOBAL_MIN_INTERVAL_S) if wait <= 0 else (_global_next_slot + GLOBAL_MIN_INTERVAL_S)
    if wait > 0:
        time.sleep(wait)


def _wrap_session_with_throttle(session):
    """Enveloppe les methodes HTTP sortantes d'une session (`.get`/`.post`/
    `.request`, celles que `curl_cffi.requests.Session` expose) pour appeler
    `_wait_for_global_slot()` juste avant chaque requete reelle. Modifie la
    session EN PLACE (retourne la meme instance) -- toutes ses autres methodes/
    attributs (cookies, headers, mount...) restent intacts."""
    if session is None:
        return None
    for method_name in ("get", "post", "request"):
        original = getattr(session, method_name, None)
        if original is None:
            continue

        def _throttled(*args, __original=original, **kwargs):
            _wait_for_global_slot()
            return __original(*args, **kwargs)

        setattr(session, method_name, _throttled)
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
    """Retourne la session curl_cffi impersonée du THREAD COURANT (créée au
    premier appel, réutilisée ensuite dans ce thread), ou None si indispo."""
    if not getattr(_local, "init_done", False):
        _local.session = _new_session()
        _local.init_done = True
    return _local.session


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


def download_prices_bulk_with_retry(
    tickers: list[str], *, retries: int = 2, cooldown_s: float = 30.0, **download_kwargs,
):
    """`download_with_timeout` avec une nouvelle tentative si le premier essai
    revient vide.

    Un rate-limit Yahoo Finance transitoire (frequent juste apres une rafale de
    milliers de requetes individuelles de scoring -- cf. `runner.py`) peut faire
    echouer TOUT le telechargement groupe en quelques secondes, bien avant le
    timeout de `download_with_timeout` (#bug rapporte : le run finissait en
    erreur ~40s apres la fin du scoring, pas apres 180s). Sans retry, cet echec
    etait auparavant invisible (portefeuille jamais calcule, run silencieusement
    marque "termine") ; desormais il ne devient une vraie erreur que si TOUTES
    les tentatives echouent -- on laisse d'abord une chance au rate-limit de se
    calmer.
    """
    import time

    def _attempt():
        return download_with_timeout(tickers=tickers, session=yf_session(), **download_kwargs)

    raw = _attempt()
    attempt = 0
    while raw.empty and attempt < retries:
        attempt += 1
        print(f"[yf_session] Telechargement groupe vide (tentative {attempt}/{retries}), "
              f"pause {cooldown_s:.0f}s avant nouvel essai...")
        time.sleep(cooldown_s)
        raw = _attempt()
    return raw


def rotate_session():
    """Force le prochain `yf_session()` du thread courant à recréer une session
    (nouvelle IP si un pool de proxys est configuré). À appeler quand Yahoo
    bloque l'IP courante."""
    _local.session = None
    _local.init_done = False


def reset_sessions() -> None:
    """Réinitialise la session du thread courant (isolation des tests)."""
    _local.session = None
    _local.init_done = False


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
