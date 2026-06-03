"""Diversification sectorielle + détection de surpondération."""

from app.services.finance.risk import compute_sector_diversification


def test_overweight_detected():
    items = [
        {"valeur": 700, "secteur": "Tech"},   # 70 % -> surpondéré
        {"valeur": 200, "secteur": "Santé"},  # 20 %
        {"valeur": 100, "secteur": "Énergie"},  # 10 %
    ]
    r = compute_sector_diversification(items, seuil_pct=30.0)
    assert r["n_secteurs"] == 3
    tech = next(s for s in r["secteurs"] if s["secteur"] == "Tech")
    assert tech["poids_pct"] == 70.0
    assert tech["surpondere"] is True
    assert r["n_surponderes"] == 1
    # secteurs triés par poids décroissant
    assert r["secteurs"][0]["secteur"] == "Tech"


def test_well_diversified_no_overweight():
    items = [{"valeur": 250, "secteur": s} for s in ("A", "B", "C", "D")]
    r = compute_sector_diversification(items, seuil_pct=30.0)
    assert r["n_surponderes"] == 0
    assert r["hhi_secteur"] == 0.25  # 4 secteurs égaux -> 4*(0.25^2)=0.25


def test_empty():
    r = compute_sector_diversification([])
    assert r["secteurs"] == []
    assert r["n_secteurs"] == 0


def test_missing_sector_is_inconnu():
    r = compute_sector_diversification([{"valeur": 100}])
    assert r["secteurs"][0]["secteur"] == "Inconnu"
