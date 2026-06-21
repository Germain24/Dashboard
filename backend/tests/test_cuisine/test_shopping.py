from app.services.cuisine.shopping_list import (
    RAYON_MAP,
    apply_inventaire,
    pantry_to_inventaire,
)


def test_pantry_to_inventaire_sums_by_ingredient():
    pantry = [
        {"ingredient": "Banane", "quantite": 200, "unite": "g"},
        {"ingredient": "Banane", "quantite": 100, "unite": "g"},   # sommé → 300
        {"ingredient": "  ", "quantite": 5},                       # vide → ignoré
        {"ingredient": "Lait", "quantite": "x"},                   # invalide → 0 → ignoré
    ]
    assert pantry_to_inventaire(pantry) == {"Banane": 300.0}


def test_apply_inventaire_deducts_pantry_stock():
    items = [{"ingredient": "Banane", "quantite": 500, "unite": "g", "rayon": "Épicerie"}]
    out = apply_inventaire(items, {"Banane": 200})
    assert out[0]["quantite"] == 300          # 500 - 200 possédés
    assert out[0]["disponible"] == 200


def test_apply_inventaire_removes_fully_covered_item():
    items = [{"ingredient": "Lait", "quantite": 100, "unite": "ml", "rayon": "Liquides"}]
    assert apply_inventaire(items, {"Lait": 150}) == []   # tout en stock → rien à acheter


def test_rayon_map_grammes():
    assert RAYON_MAP["g"] == "Épicerie"
    assert RAYON_MAP["kg"] == "Épicerie"


def test_rayon_map_liquides():
    assert RAYON_MAP["ml"] == "Liquides"
    assert RAYON_MAP["L"] == "Liquides"


def test_rayon_map_no_unknown():
    assert "tablespoon" not in RAYON_MAP
