"""Conseils d'achat combinatoires (tenues débloquées)."""
from __future__ import annotations

from app.services.garderobe.purchase_combos import (
    base_slot_of,
    count_outfits,
    purchase_advice,
)


def test_base_slot_of():
    assert base_slot_of({"categorie": "Haut"}) == "Haut"
    assert base_slot_of({"categorie": "T-shirt"}) == "Haut"
    assert base_slot_of({"categorie": "Pantalon"}) == "Pantalon"
    assert base_slot_of({"categorie": "Jean"}) == "Pantalon"
    assert base_slot_of({"categorie": "Chaussures"}) == "Chaussures"
    assert base_slot_of({"categorie": "Montre"}) is None
    assert base_slot_of({"categorie": None}) is None


def test_count_outfits_compte_triplets_compatibles():
    wardrobe = [
        {"categorie": "Haut", "couleur": "Noir"},
        {"categorie": "Pantalon", "couleur": "Noir"},
        {"categorie": "Chaussures", "couleur": "Noir"},
    ]
    assert count_outfits(wardrobe) == 1
    # un 2e haut neutre ajoute un triplet
    wardrobe.append({"categorie": "Haut", "couleur": "Blanc"})
    assert count_outfits(wardrobe) == 2


def test_count_outfits_exclut_incompatibles():
    # Terracotta (accent hors palette) vs Bordeaux (secondaire) : pas dans
    # MATCHING_COLORS l'un de l'autre et catégories différentes -> incompatibles.
    # Note du brief : "Or vs Marron" était la paire citée, mais "Marron" figure
    # dans MATCHING_COLORS["Or"], donc ils sont compatibles. On utilise Terracotta.
    wardrobe = [
        {"categorie": "Haut", "couleur": "Terracotta"},
        {"categorie": "Pantalon", "couleur": "Bordeaux"},
        {"categorie": "Chaussures", "couleur": "Noir"},
    ]
    assert count_outfits(wardrobe) == 0


def test_purchase_advice_recommande_le_slot_manquant():
    # Haut + Pantalon mais pas de chaussures -> 0 tenue ; le meilleur achat = Chaussures
    wardrobe = [
        {"categorie": "Haut", "couleur": "Noir"},
        {"categorie": "Pantalon", "couleur": "Noir"},
    ]
    advice = purchase_advice(wardrobe, top=5)
    assert advice, "des conseils sont attendus"
    assert advice[0]["slot"] == "Chaussures"
    assert advice[0]["debloque"] >= 1
    assert advice[0]["total_apres"] == advice[0]["debloque"]  # base 0
    # aucun conseil Haut/Pantalon (ils ne débloquent rien sans chaussures)
    assert all(c["slot"] == "Chaussures" for c in advice)


def test_purchase_advice_exclut_gains_nuls_et_trie():
    # Pantalon Noir + Chaussures Marron : ajouter un Haut Or ne débloque rien
    # (Or incompatible avec Marron), un Haut neutre débloque 1.
    wardrobe = [
        {"categorie": "Pantalon", "couleur": "Noir"},
        {"categorie": "Chaussures", "couleur": "Marron"},
    ]
    advice = purchase_advice(wardrobe, top=10)
    assert advice[0]["slot"] == "Haut"
    assert advice[0]["debloque"] == 1
    # tri décroissant
    gains = [c["debloque"] for c in advice]
    assert gains == sorted(gains, reverse=True)
    # aucun gain nul, et "Or" (incompatible) absent des conseils Haut
    assert all(c["debloque"] > 0 for c in advice)
    assert not any(c["couleur"] == "Or" for c in advice)
