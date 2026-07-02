"""Lookup IATA -> coordonnées (table statique locale, aucun appel réseau)."""
from __future__ import annotations

from app.services.voyage.airports import lookup_coords


def _make_csv(path):
    path.write_text(
        "iata,name,lat,lon\n"
        "YUL,Montreal-Trudeau Intl,45.4706,-73.7408\n"
        "CDG,Charles de Gaulle,49.0097,2.5479\n",
        encoding="utf-8",
    )


def test_lookup_coords_known_code(tmp_path):
    p = tmp_path / "airports.csv"
    _make_csv(p)
    assert lookup_coords("YUL", path=p) == (45.4706, -73.7408)


def test_lookup_coords_case_insensitive(tmp_path):
    p = tmp_path / "airports.csv"
    _make_csv(p)
    assert lookup_coords("cdg", path=p) == (49.0097, 2.5479)


def test_lookup_coords_unknown_code_returns_none(tmp_path):
    p = tmp_path / "airports.csv"
    _make_csv(p)
    assert lookup_coords("ZZZ", path=p) is None


def test_lookup_coords_caches_per_path(tmp_path):
    """Deux lookups sur le même path ne relisent pas le fichier deux fois."""
    p = tmp_path / "airports.csv"
    _make_csv(p)
    lookup_coords("YUL", path=p)
    p.write_text("iata,name,lat,lon\n", encoding="utf-8")  # vide le fichier
    # toujours servi depuis le cache, pas relu depuis le fichier maintenant vide
    assert lookup_coords("YUL", path=p) == (45.4706, -73.7408)
