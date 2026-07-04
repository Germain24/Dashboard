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

_local = threading.local()

# Empreinte de navigateur à usurper (curl_cffi). Chrome récent = profil le plus sûr.
IMPERSONATE = "chrome"


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
    configuré (rotation d'IP). None si curl_cffi est indisponible."""
    try:
        from curl_cffi import requests as cffi_requests

        kwargs = {"impersonate": IMPERSONATE}
        pool = _proxy_pool()
        if pool:
            proxy = random.choice(pool)
            kwargs["proxies"] = {"http": proxy, "https": proxy}
        return cffi_requests.Session(**kwargs)
    except Exception:
        return None


def yf_session():
    """Retourne la session curl_cffi impersonée du THREAD COURANT (créée au
    premier appel, réutilisée ensuite dans ce thread), ou None si indispo."""
    if not getattr(_local, "init_done", False):
        _local.session = _new_session()
        _local.init_done = True
    return _local.session


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


def fast_last_price(ticker_obj) -> float:
    """Dernier cours d'un yf.Ticker, robuste.

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
            return float(v)
    except Exception:
        pass
    # 2) repli : dernier close de l'historique récent
    try:
        hist = ticker_obj.history(period="5d")
        closes = hist["Close"].dropna()
        if len(closes):
            return float(closes.iloc[-1])
    except Exception:
        pass
    return 0.0
