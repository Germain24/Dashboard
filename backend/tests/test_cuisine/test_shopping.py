from app.services.cuisine.shopping_list import RAYON_MAP


def test_rayon_map_grammes():
    assert RAYON_MAP["g"] == "Épicerie"
    assert RAYON_MAP["kg"] == "Épicerie"


def test_rayon_map_liquides():
    assert RAYON_MAP["ml"] == "Liquides"
    assert RAYON_MAP["L"] == "Liquides"


def test_rayon_map_no_unknown():
    assert "tablespoon" not in RAYON_MAP
