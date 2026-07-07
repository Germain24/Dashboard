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


from unittest.mock import patch

from app.models.cuisine import MealPlanEntry, Recipe, RecipeIngredient
from app.services.cuisine.shopping_list import compute_shopping


def test_compute_shopping_applies_store_recommendations(mem_session):
    recipe = Recipe(titre="Riz aux légumes")
    mem_session.add(recipe)
    mem_session.commit()
    mem_session.refresh(recipe)
    mem_session.add(RecipeIngredient(recipe_id=recipe.id, nom_libre="Riz basmati (sec)", quantite=200, unite="g"))
    mem_session.add(MealPlanEntry(semaine="2026-07-06", jour=0, repas="diner", recipe_id=recipe.id))
    mem_session.commit()

    with patch(
        "app.services.cuisine.shopping_list.store_pricing.apply_recommendations",
        side_effect=lambda items: [
            {**it, "magasin_recommande": "Super C", "prix_estime": 3.99, "promo": False} for it in items
        ],
    ):
        out = compute_shopping(mem_session, "2026-07-06")

    assert out[0]["magasin_recommande"] == "Super C"
    assert out[0]["prix_estime"] == 3.99


def test_compute_shopping_survives_store_pricing_failure(mem_session):
    recipe = Recipe(titre="Riz aux légumes")
    mem_session.add(recipe)
    mem_session.commit()
    mem_session.refresh(recipe)
    mem_session.add(RecipeIngredient(recipe_id=recipe.id, nom_libre="Riz basmati (sec)", quantite=200, unite="g"))
    mem_session.add(MealPlanEntry(semaine="2026-07-06", jour=0, repas="diner", recipe_id=recipe.id))
    mem_session.commit()

    with patch(
        "app.services.cuisine.shopping_list.store_pricing.apply_recommendations",
        side_effect=RuntimeError("cache corrompu"),
    ):
        out = compute_shopping(mem_session, "2026-07-06")   # ne doit pas lever

    assert out[0]["ingredient"] == "Riz basmati (sec)"
    assert "magasin_recommande" not in out[0]
