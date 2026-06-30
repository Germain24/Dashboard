"""Fonctions pures de l'onglet Objectif (échelle Q/P → Max)."""
from __future__ import annotations

from app.services.garderobe.objectif import (
    brand_position,
    build_echelle,
    fill_slots,
)


def test_build_echelle_dedup_strip_order():
    assert build_echelle(["Uniqlo U", "Beams Plus", None, " Beams Plus ", "Auralee", ""]) == [
        "Uniqlo U",
        "Beams Plus",
        "Auralee",
    ]


def test_brand_position_extremes_and_middle():
    ech = ["Uniqlo U", "Beams Plus", "Graphpaper", "Auralee", "Visvim"]  # 5 marques
    assert brand_position(ech, "Uniqlo U") == 0.0
    assert brand_position(ech, "Visvim") == 100.0
    assert brand_position(ech, "Graphpaper") == 50.0


def test_brand_position_absent_or_none():
    ech = ["Uniqlo U", "Visvim"]
    assert brand_position(ech, "Lacoste") is None
    assert brand_position(ech, None) is None


def test_brand_position_case_insensitive_and_single():
    assert brand_position(["Uniqlo U", "Visvim"], "visvim") == 100.0
    assert brand_position(["Auralee"], "Auralee") == 0.0  # échelle de longueur 1


def test_fill_slots_partial_fills_then_empty():
    ech = ["Uniqlo U", "Beams Plus", "Visvim"]
    owned = [{"id": "v1", "nom": "Tee gris", "marque": "Visvim"}]
    res = fill_slots(ech, 3, owned)
    assert res["rempli"] == 1
    assert len(res["emplacements"]) == 3
    assert res["emplacements"][0]["statut"] == "rempli"
    assert res["emplacements"][0]["position"] == 100.0
    assert res["emplacements"][1]["statut"] == "vide"
    assert res["excedent"] == []


def test_fill_slots_excess_goes_red():
    ech = ["Uniqlo U", "Visvim"]
    owned = [
        {"id": "a", "nom": "A", "marque": "Visvim"},
        {"id": "b", "nom": "B", "marque": "Uniqlo U"},
        {"id": "c", "nom": "C", "marque": "Visvim"},
    ]
    res = fill_slots(ech, 1, owned)  # objectif 1, possédés 3
    assert res["rempli"] == 1
    assert len(res["emplacements"]) == 1
    assert len(res["excedent"]) == 2
    # meilleure qualité conservée dans l'emplacement
    assert res["emplacements"][0]["position"] == 100.0


def test_fill_slots_unknown_brand_is_off_scale_and_last():
    ech = ["Uniqlo U", "Visvim"]
    owned = [
        {"id": "a", "nom": "A", "marque": "Lacoste"},   # hors échelle
        {"id": "b", "nom": "B", "marque": "Visvim"},
    ]
    res = fill_slots(ech, 1, owned)
    assert res["emplacements"][0]["marque"] == "Visvim"  # positionné d'abord
    assert res["excedent"][0]["marque"] == "Lacoste"
    assert res["excedent"][0]["hors_echelle"] is True
    assert res["excedent"][0]["position"] is None
