"""Taux obligataires souverains (10 ans) — rafraîchis automatiquement.

Le critère d'achat Buffett compare le prix à un plafond `EPS / (0,02 + taux)`,
où `taux` est le rendement obligataire du pays. Historiquement ces taux étaient
des constantes figées ; ce module les rafraîchit pour **tous les pays exposés
par FRED** (API publique, CSV sans clé), avec **repli sur les valeurs statiques**
quand le réseau échoue (offline-friendly).

Yahoo n'expose proprement que le 10 ans US (^TNX) ; FRED couvre ~18 pays via les
séries `IRLTLT01<ISO>M156N` (rendements souverains 10 ans, source OCDE) et
`DGS10` pour les États-Unis.

`merge_yields` / `_normalize_yield` / `_parse_fred_csv` sont purs (testables) ;
`get_bond_yields` gère le cache et le fetch réseau, injectable pour les tests.
"""

from __future__ import annotations

import datetime as dt
import threading

# Valeurs de repli (dernier point de référence connu). Source de vérité du défaut,
# importée par buffett.config pour Config.TAUX_OBLIGATAIRES.
STATIC_BOND_YIELDS: dict[str, float] = {
    "United States": 0.042, "France": 0.029, "Germany": 0.024,
    "United Kingdom": 0.040, "Switzerland": 0.007, "Canada": 0.035,
    "Japan": 0.008, "China": 0.023, "India": 0.067, "Italy": 0.038,
    "South Korea": 0.030, "Australia": 0.043, "Hong Kong": 0.038,
    "Taiwan": 0.015, "Brazil": 0.135, "Mexico": 0.095,
    "Sweden": 0.020, "Netherlands": 0.027, "Belgium": 0.030,
    "Denmark": 0.025, "Norway": 0.035, "Israel": 0.045,
    "Singapore": 0.030, "South Africa": 0.095, "Indonesia": 0.068,
    "Turkey": 0.280,
}

# Pays -> série FRED du rendement 10 ans (cotée en %). DGS10 = US (quotidien) ;
# IRLTLT01<ISO>M156N = rendements souverains 10 ans OCDE (mensuels). Liste validée
# en interrogeant FRED : on ne garde que les séries qui répondent réellement.
# Les pays sans série FRED (Chine, Inde, Hong Kong, Taïwan, Brésil, Singapour,
# Indonésie, Turquie…) gardent leur repli statique. Extensible.
SERIES_BY_COUNTRY: dict[str, str] = {
    "United States": "DGS10",
    "Canada": "IRLTLT01CAM156N",
    "France": "IRLTLT01FRM156N",
    "Germany": "IRLTLT01DEM156N",
    "Italy": "IRLTLT01ITM156N",
    "Japan": "IRLTLT01JPM156N",
    "United Kingdom": "IRLTLT01GBM156N",
    "Switzerland": "IRLTLT01CHM156N",
    "South Korea": "IRLTLT01KRM156N",
    "Australia": "IRLTLT01AUM156N",
    "Mexico": "IRLTLT01MXM156N",
    "Sweden": "IRLTLT01SEM156N",
    "Netherlands": "IRLTLT01NLM156N",
    "Belgium": "IRLTLT01BEM156N",
    "Denmark": "IRLTLT01DKM156N",
    "Norway": "IRLTLT01NOM156N",
    "Israel": "IRLTLT01ILM156N",
    "South Africa": "IRLTLT01ZAM156N",
}

_FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"

# Garde-fou de plausibilité (fraction) : un rendement live hors de cette plage
# est rejeté → on garde le repli.
_MIN_YIELD = 0.0
_MAX_YIELD = 0.25

_cache: dict = {}
_lock = threading.Lock()


def _normalize_yield(raw: float | None) -> float | None:
    """Convertit un rendement (en %, ex. 4,47) en fraction (0,0447).

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


def _parse_fred_csv(text: str) -> float | None:
    """Dernière valeur numérique d'un CSV FRED (ignore l'en-tête et les « . »)."""
    last: float | None = None
    for line in text.strip().splitlines():
        parts = line.split(",")
        if len(parts) < 2:
            continue
        try:
            last = float(parts[-1].strip())
        except ValueError:
            continue
    return last


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


def _default_fetch(series_map: dict[str, str]) -> dict[str, float | None]:
    """Derniers rendements via FRED (CSV public, best-effort, jamais d'exception)."""
    out: dict[str, float | None] = {}
    if not series_map:
        return out
    try:
        import httpx

        with httpx.Client(timeout=12.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
            for country, sid in series_map.items():
                try:
                    r = client.get(_FRED_CSV_URL.format(sid=sid))
                    out[country] = _parse_fred_csv(r.text) if r.status_code == 200 else None
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

    Fusionne les valeurs live (G7, via FRED) par-dessus ``defaults`` (ou le repli
    statique). En cas d'échec réseau, renvoie simplement ``defaults`` — jamais
    pire que les constantes.
    """
    today = today or dt.date.today()
    with _lock:
        cached = _cache.get("fetched") if (not force and _cache.get("date") == today) else None
    if cached is None:
        fetch = fetcher or _default_fetch
        try:
            cached = fetch(SERIES_BY_COUNTRY)
        except Exception:
            cached = {}
        with _lock:
            _cache["date"] = today
            _cache["fetched"] = cached
    return merge_yields(cached, defaults)
