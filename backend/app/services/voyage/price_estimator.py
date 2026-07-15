"""Estimation du prix moyen d'un vol économie aller simple à partir de la
distance à vol d'oiseau -- utilisé pour explorer beaucoup de combinaisons
d'itinéraire sans dépendre d'un appel Duffel par paire (~N² appels, Duffel
rate-limite après une quarantaine de requêtes rapprochées, cf. #timeout
planifier-auto).

Paliers calibrés sur des prix Duffel réels observés (routes courtes
Amérique du Nord, 233-2478 km, 38-113 $) puis extrapolés à un taux
dégressif au-delà (pratique tarifaire standard : le prix au km baisse sur
les longs courriers, compensé par une base plus élevée). C'est une
ESTIMATION, pas un prix live -- volontairement approximative, à corriger
dans la feuille "Prix" de `Voyage.xlsx` (matrice aéroport de départ (X) x
aéroport d'arrivée (Y), prioritaire sur la formule) pour les routes que
l'utilisateur connaît mieux. La durée reste toujours calculée par la formule.
"""

from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.services.voyage.airports import haversine_km, lookup_coords

_PALIERS = [
    (1_500, 45.0, 0.045),
    (5_000, 90.0, 0.050),
    (10_000, 220.0, 0.045),
    (float("inf"), 380.0, 0.035),
]

_VITESSE_CROISIERE_KMH = 800.0
_BATTEMENT_MIN = 45  # roulage + embarquement/débarquement, forfaitaire

SHEET_PRIX = "Prix"

_overrides_cache: dict[Path, dict[tuple[str, str], float]] = {}


def estimate_price_eur(distance_km: float) -> tuple[float, int]:
    """(prix_eur_estime, duree_min_estimee) pour une distance donnée."""
    distance_km = max(0.0, distance_km)
    for plafond, base, taux in _PALIERS:
        if distance_km <= plafond:
            prix = base + taux * distance_km
            break
    duree_min = round(distance_km / _VITESSE_CROISIERE_KMH * 60 + _BATTEMENT_MIN)
    return round(prix, 2), duree_min


def overrides_path() -> Path:
    return settings.imports_dir / "Voyage.xlsx"


def _load_overrides(path: Path) -> dict[tuple[str, str], float]:
    """Charge la feuille "Prix" de `Voyage.xlsx` : matrice avec les aéroports
    de DÉPART en colonnes (ligne d'en-tête) et les aéroports d'ARRIVÉE en
    lignes (colonne d'en-tête) -- toute cellule remplie à la main y prend le
    pas sur la formule par distance pour cette paire (départ, arrivée)."""
    if path not in _overrides_cache:
        table: dict[tuple[str, str], float] = {}
        if path.exists():
            import openpyxl

            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            if SHEET_PRIX in wb.sheetnames:
                ws = wb[SHEET_PRIX]
                rows = list(ws.iter_rows(values_only=True))
                if rows:
                    departs = rows[0][1:]  # en-tête colonnes = aéroports de départ
                    for row in rows[1:]:
                        if not row or not row[0]:
                            continue
                        arrivee = str(row[0]).strip().upper()
                        for depart_raw, prix in zip(departs, row[1:]):
                            if not depart_raw or prix in (None, ""):
                                continue
                            depart = str(depart_raw).strip().upper()
                            table[(depart, arrivee)] = round(float(prix), 2)
            wb.close()
        _overrides_cache[path] = table
    return _overrides_cache[path]


def clear_overrides_cache() -> None:
    _overrides_cache.clear()


def estimate_trajet(origine_iata: str, destination_iata: str) -> Optional[dict]:
    """Prix/durée estimés entre deux aéroports : le prix privilégie une
    cellule remplie dans la matrice "Prix" de `Voyage.xlsx`, sinon repli sur
    la formule par distance (la durée vient toujours de la formule).
    `None` si l'un des deux codes IATA est inconnu de la table locale."""
    a = lookup_coords(origine_iata)
    b = lookup_coords(destination_iata)
    if a is None or b is None:
        return None
    prix_formule, duree_min = estimate_price_eur(haversine_km(a, b))

    overrides = _load_overrides(overrides_path())
    key = (origine_iata.strip().upper(), destination_iata.strip().upper())
    prix = overrides.get(key, prix_formule)
    return {"prix": prix, "duree_min": duree_min}
