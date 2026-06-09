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
