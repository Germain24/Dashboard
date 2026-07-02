"""Génère `app/services/voyage/data/airports_iata.csv` depuis OurAirports
(dataset public domain, CC0) — filtré aux aéroports ayant un code IATA.

Script one-shot, pas couvert par les tests automatisés (appel réseau) : à
relancer manuellement si la table doit être rafraîchie.

Usage (depuis `backend/`) : `uv run python -m scripts.build_airports_iata`
"""
from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

import httpx

_SOURCE_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
_OUT_PATH = Path(__file__).parent.parent / "app" / "services" / "voyage" / "data" / "airports_iata.csv"


def main() -> None:
    resp = httpx.get(_SOURCE_URL, timeout=60, follow_redirects=True)
    resp.raise_for_status()
    reader = csv.DictReader(StringIO(resp.text))

    _OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with _OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["iata", "name", "lat", "lon"])
        for row in reader:
            iata = (row.get("iata_code") or "").strip().upper()
            lat, lon = row.get("latitude_deg"), row.get("longitude_deg")
            if not iata or not lat or not lon:
                continue
            writer.writerow([iata, row.get("name", ""), lat, lon])
            n += 1

    print(f"écrit {n} aéroports -> {_OUT_PATH}")


if __name__ == "__main__":
    main()
