"""Lookup IATA -> (lat, lon) depuis une table statique locale.

Source : `data/airports_iata.csv` (colonnes iata,name,lat,lon), dérivé du
dataset public domain OurAirports (CC0), filtré aux entrées ayant un code
IATA renseigné. Généré une fois via `scripts/build_airports_iata.py`
(backend/) — pas régénéré automatiquement au runtime, aucun appel réseau
lors du lookup.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

_DATA_PATH = Path(__file__).parent / "data" / "airports_iata.csv"
_cache: dict[Path, dict[str, tuple[float, float]]] = {}


def _load(path: Path) -> dict[str, tuple[float, float]]:
    if path not in _cache:
        table: dict[str, tuple[float, float]] = {}
        with path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                iata = (row.get("iata") or "").strip().upper()
                if iata:
                    table[iata] = (float(row["lat"]), float(row["lon"]))
        _cache[path] = table
    return _cache[path]


def lookup_coords(iata: str, *, path: Optional[Path] = None) -> Optional[tuple[float, float]]:
    """Renvoie `(lat, lon)` pour un code IATA, ou `None` si absent de la table."""
    table = _load(path or _DATA_PATH)
    return table.get(iata.strip().upper())
