"""Estimation tarifaire par distance, avec repli sur la matrice éditable de
la feuille "Prix" de Voyage.xlsx pour les routes que l'utilisateur connaît
mieux que la formule."""

from __future__ import annotations

import openpyxl
import pytest

from app.services.voyage import price_estimator
from app.services.voyage.price_estimator import estimate_price_eur, estimate_trajet


def test_short_haul_close_to_real_duffel_cache_ballpark():
    # YUL-YQB : 233 km, prix Duffel réel observé ~38 $ -- la formule doit
    # rester dans un ordre de grandeur plausible (pas un facteur x2+).
    prix, _ = estimate_price_eur(233)
    assert 40 <= prix <= 120


def test_price_increases_monotonically_with_distance():
    prix_court, _ = estimate_price_eur(500)
    prix_moyen, _ = estimate_price_eur(5000)
    prix_long, _ = estimate_price_eur(15000)
    assert prix_court < prix_moyen < prix_long


def test_zero_distance_is_non_negative():
    prix, duree = estimate_price_eur(0)
    assert prix >= 0
    assert duree >= 0


def test_negative_distance_clamped_to_zero():
    assert estimate_price_eur(-100) == estimate_price_eur(0)


def test_duration_scales_with_distance():
    _, duree_court = estimate_price_eur(800)   # ~1h de vol + battement
    _, duree_long = estimate_price_eur(8000)   # ~10h de vol + battement
    assert duree_long > duree_court
    assert duree_court < 180   # < 3h pour 800km, cohérent avec 800km/h de croisière


@pytest.fixture(autouse=True)
def _clear_overrides_cache():
    price_estimator.clear_overrides_cache()
    yield
    price_estimator.clear_overrides_cache()


def test_estimate_trajet_falls_back_to_formula_when_no_override(tmp_path, monkeypatch):
    monkeypatch.setattr(price_estimator, "overrides_path", lambda: tmp_path / "absent.xlsx")
    resultat = estimate_trajet("YUL", "CPT")
    assert resultat is not None
    assert resultat["prix"] > 0
    assert resultat["duree_min"] > 0


def test_estimate_trajet_returns_none_for_unknown_airport(tmp_path, monkeypatch):
    monkeypatch.setattr(price_estimator, "overrides_path", lambda: tmp_path / "absent.xlsx")
    assert estimate_trajet("YUL", "ZZZZ") is None


def test_estimate_trajet_prioritizes_override_over_formula(tmp_path, monkeypatch):
    """Matrice : départs en colonnes (en-tête), arrivées en lignes."""
    path = tmp_path / "Voyage.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Prix"
    ws.append(["Arrivée \\ Départ", "YUL", "CPT"])
    ws.append(["YUL", None, 888.0])
    ws.append(["CPT", 999.0, None])
    wb.save(path)
    monkeypatch.setattr(price_estimator, "overrides_path", lambda: path)

    # Directionnel : chaque sens peut avoir sa propre valeur éditée.
    assert estimate_trajet("YUL", "CPT")["prix"] == 999.0
    assert estimate_trajet("CPT", "YUL")["prix"] == 888.0
    # La durée reste calculée par la formule même si le prix est écrasé.
    _, duree_formule = estimate_price_eur(
        price_estimator.haversine_km(price_estimator.lookup_coords("YUL"), price_estimator.lookup_coords("CPT"))
    )
    assert estimate_trajet("YUL", "CPT")["duree_min"] == duree_formule


def test_estimate_trajet_falls_back_to_formula_for_cell_left_blank(tmp_path, monkeypatch):
    path = tmp_path / "Voyage.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Prix"
    ws.append(["Arrivée \\ Départ", "YUL", "CPT"])
    ws.append(["YUL", None, None])
    ws.append(["CPT", None, None])
    wb.save(path)
    monkeypatch.setattr(price_estimator, "overrides_path", lambda: path)

    formule, _ = estimate_price_eur(
        price_estimator.haversine_km(price_estimator.lookup_coords("YUL"), price_estimator.lookup_coords("CPT"))
    )
    assert estimate_trajet("YUL", "CPT")["prix"] == formule
