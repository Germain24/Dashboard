"""Tests des recommandations d'achat."""

from app.services.garderobe.recommendations import get_purchase_recommendations


def test_empty_wardrobe_returns_seed_recommendation():
    recs = get_purchase_recommendations([])
    assert len(recs) == 1
    assert recs[0]["potentiel"] == 100
    assert "vide" in recs[0]["raison"].lower()


def test_missing_essentials_recommended():
    # Garde-robe avec seulement un haut
    wardrobe = [
        {"id": "h1", "categorie": "Haut", "couleur": "Bleu marine", "style": ["Old Money"]},
    ]
    recs = get_purchase_recommendations(wardrobe)
    # Doit recommander au moins une catégorie essentielle (Pantalon, Chaussures…)
    types = {r["type"] for r in recs}
    assert "Basique" in types


def test_caps_at_five_recommendations():
    wardrobe = [
        {"id": "h1", "categorie": "Haut", "couleur": "Or", "style": ["Streetwear"]},
    ]
    recs = get_purchase_recommendations(wardrobe)
    assert len(recs) <= 5


def test_recommendations_sorted_by_potentiel_desc():
    wardrobe = [
        {"id": "h1", "categorie": "Haut", "couleur": "Or", "style": ["Streetwear"]},
    ]
    recs = get_purchase_recommendations(wardrobe)
    pots = [r["potentiel"] for r in recs]
    assert pots == sorted(pots, reverse=True)
