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
"""

from __future__ import annotations

import threading

_lock = threading.Lock()
_session = None
_init_done = False

# Empreinte de navigateur à usurper (curl_cffi). Chrome récent = profil le plus sûr.
IMPERSONATE = "chrome"


def yf_session():
    """Retourne une session curl_cffi impersonée (singleton), ou None si indispo."""
    global _session, _init_done
    if _init_done:
        return _session
    with _lock:
        if _init_done:
            return _session
        try:
            from curl_cffi import requests as cffi_requests

            _session = cffi_requests.Session(impersonate=IMPERSONATE)
        except Exception:
            _session = None
        _init_done = True
    return _session
