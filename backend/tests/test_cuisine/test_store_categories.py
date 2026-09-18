"""TDD — classification des ingrédients en catégories d'achat (Pantry/Viandes/
Fruits&Légumes/Tofu-Protéines) pour la comparaison de prix multi-magasins."""
from __future__ import annotations

from app.services.cuisine.store_categories import categorie_achat, search_keywords


def test_pantry_item_classified():
    assert categorie_achat("Riz basmati (sec)") == "pantry"
    assert search_keywords("Riz basmati (sec)") == ["riz basmati", "basmati"]


def test_viande_volume_item_classified():
    assert categorie_achat("Poitrine de poulet") == "viande_volume"


def test_viande_noble_item_classified():
    assert categorie_achat("Saumon atlantique") == "viande_noble"


def test_tofu_proteines_item_classified():
    assert categorie_achat("Tofu ferme") == "tofu_proteines"


def test_fruits_legumes_reuses_adonis_produce_map():
    # "Banane" est dans PRODUCE_MAP (adonis_pricing.py) -> classé fruits_legumes
    assert categorie_achat("Banane") == "fruits_legumes"
    assert search_keywords("Banane") == ["banane"]


def test_unclassified_ingredient_returns_none():
    assert categorie_achat("Ingredient inexistant") is None
    assert search_keywords("Ingredient inexistant") == []


def test_laitiers_et_fromages_sont_classifies():
    """Ils ne l'étaient pas : sans mots-clés, `refresh_if_stale` ne les cherchait
    jamais sur superc.ca et leur prix restait figé à sa valeur d'origine."""
    for nom in ("Fromage cheddar", "Kefir", "Lait 2%", "Oeufs", "Parmesan"):
        assert categorie_achat(nom) == "laitiers", nom
        assert search_keywords(nom), nom
