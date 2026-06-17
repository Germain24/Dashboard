"""Taux obligataires souverains (10 ans) — rafraîchis automatiquement.

Le critère d'achat Buffett compare le prix à un plafond `EPS / (0,02 + taux)`,
où `taux` est le rendement obligataire du pays. Historiquement ces taux étaient
des constantes figées ; ce module les rafraîchit (yfinance, cache quotidien)
avec **repli sur les valeurs statiques** quand le réseau échoue (offline-friendly).

`merge_yields` / `_normalize_yield` sont purs (testables) ; `get_bond_yields`
gère le cache et le fetch réseau, injectable pour les tests.
"""

from __future__ import annotations

import datetime as dt
import threading

# Valeurs de repli (dernier point de référence connu). Source de vérité du défaut,
# importée par buffett.config pour Config.TAUX_OBLIGATAIRES.
STATIC_BOND_YIELDS: dict[str, float] = {
    "United States": 0.042, "France": 0.029, "Germany": 0.024,
    "United Kingdom": 0.040, "Switzerland": 0.007, "Canada": 0.035,
    "Japan": 0.008, "China": 0.023, "India": 0.067,
    "South Korea": 0.030, "Australia": 0.043, "Hong Kong": 0.038,
    "Taiwan": 0.015, "Brazil": 0.135, "Mexico": 0.095,
    "Sweden": 0.020, "Netherlands": 0.027, "Belgium": 0.030,
    "Denmark": 0.025, "Norway": 0.035, "Israel": 0.045,
    "Singapore": 0.030, "South Africa": 0.095, "Indonesia": 0.068,
    "Turkey": 0.280,
}

# Pays -> ticker Yahoo du rendement 10 ans (coté en %). Conservateur : on ne met
# que les symboles fiables (^TNX = US 10Y). Les pays absents gardent leur repli.
# Extensible : ajouter d'autres tickers souverains validés ici.
TICKER_BY_COUNTRY: dict[str, str] = {
    "United States": "^TNX",
}

# Garde-fou de plausibilité (fraction) : un rendement live hors de cette plage
# (ex. ^TNX renvoyé ×10) est rejeté → on garde le repli.
_MIN_YIELD = 0.0
_MAX_YIELD = 0.25

_cache: dict = {}
_lock = threading.Lock()


def _normalize_yield(raw: float | None) -> float | None:
    """Convertit un rendement Yahoo (en %, ex. 4,23) en fraction (0,0423).

    Renvoie None si absent, nul, ou hors plage plausible (garde-fou).
    """
    if raw is None:
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    frac = v / 100.0
    if _MIN_YIELD < frac <= _MAX_YIELD:
        return round(frac, 4)
    return None


def merge_yields(
    fetched: dict[str, float | None], defaults: dict[str, float] | None = None,
) -> dict[str, float]:
    """Fusionne les rendements live (normalisés) par-dessus les valeurs de repli."""
    base = dict(defaults if defaults is not None else STATIC_BOND_YIELDS)
    for country, raw in fetched.items():
        norm = _normalize_yield(raw)
        if norm is not None:
            base[country] = norm
    return base


def _default_fetch(tickers: dict[str, str]) -> dict[str, float | None]:
    """Derniers rendements via yfinance (best-effort, jamais d'exception)."""
    out: dict[str, float | None] = {}
    if not tickers:
        return out
    try:
        import yfinance as yf

        from app.services.finance.yf_session import fast_last_price, yf_session
        data = yf.Tickers(" ".join(tickers.values()), session=yf_session())
        for country, tk in tickers.items():
            try:
                out[country] = fast_last_price(data.tickers[tk])
            except Exception:
                out[country] = None
    except Exception:
        pass
    return out


def get_bond_yields(
    *,
    defaults: dict[str, float] | None = None,
    fetcher=None,
    today: dt.date | None = None,
    force: bool = False,
) -> dict[str, float]:
    """Rendements obligataires par pays, rafraîchis une fois par jour (cache).

    Fusionne les valeurs live (fetchées) par-dessus ``defaults`` (ou le repli
    statique). En cas d'échec réseau, renvoie simplement ``defaults`` — jamais
    pire que les constantes.
    """
    today = today or dt.date.today()
    with _lock:
        cached = _cache.get("fetched") if (not force and _cache.get("date") == today) else None
    if cached is None:
        fetch = fetcher or _default_fetch
        try:
            cached = fetch(TICKER_BY_COUNTRY)
        except Exception:
            cached = {}
        with _lock:
            _cache["date"] = today
            _cache["fetched"] = cached
    return merge_yields(cached, defaults)
