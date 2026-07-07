"""TDD — classification des ingrédients en catégories d'achat (Pantry/Viandes/
Fruits&Légumes/Tofu-Protéines) pour la comparaison de prix multi-magasins."""
from __future__ import annotations

from app.services.cuisine.store_categories import categorie_achat, search_keywords


def test_pantry_item_classified():
    assert categorie_achat("Riz basmati (sec)") == "pantry"
    assert search_keywords("Riz basmati (sec)") == ["basmati rice"]


def test_viande_volume_item_classified():
    assert categorie_achat("Poitrine de poulet") == "viande_volume"


def test_viande_noble_item_classified():
    assert categorie_achat("Saumon atlantique") == "viande_noble"


def test_tofu_proteines_item_classified():
    assert categorie_achat("Tofu ferme") == "tofu_proteines"


def test_fruits_legumes_reuses_adonis_produce_map():
    # "Banane" est dans PRODUCE_MAP (adonis_pricing.py) -> classé fruits_legumes
    assert categorie_achat("Banane") == "fruits_legumes"
    assert search_keywords("Banane") == ["banana"]


def test_unclassified_ingredient_returns_none():
    assert categorie_achat("Fromage cheddar") is None
    assert search_keywords("Fromage cheddar") == []
