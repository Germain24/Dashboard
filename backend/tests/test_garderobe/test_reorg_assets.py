"""Fonctions pures du script de réorganisation des images pixel art."""
from __future__ import annotations

from scripts.reorg_garderobe_assets import assign_paths, build_slug, slugify


def test_slugify_accents_espaces_casse():
    assert slugify("Vert Émeraude") == "vert-emeraude"
    assert slugify("  COS  ") == "cos"
    assert slugify("Noir/Anthracite") == "noir-anthracite"
    assert slugify(None) == ""


def test_build_slug_ignore_tokens_vides():
    assert build_slug("T-shirt", "Uniqlo", "Gris anthracite") == "t-shirt-uniqlo-gris-anthracite"
    assert build_slug(None, "Garmin", "Noir") == "garmin-noir"
    assert build_slug("", "", "") == "sans-nom"


def test_assign_paths_collision_suffixe_deterministe():
    rows = [
        {"id": "Fossil02", "categorie": "Montre", "sous_categorie": "Montre Automatique",
         "marque": "Fossil", "couleur": "Marron"},
        {"id": "Fossil01", "categorie": "Montre", "sous_categorie": "Montre Analogique",
         "marque": "Fossil", "couleur": "Marron"},
    ]
    paths = assign_paths(rows)
    # sous-catégorie distingue déjà → pas de suffixe
    assert paths["Fossil01"] == "Montre/montre-analogique-fossil-marron.png"
    assert paths["Fossil02"] == "Montre/montre-automatique-fossil-marron.png"


def test_assign_paths_vraie_collision_recoit_suffixe():
    rows = [
        {"id": "b", "categorie": "Haut", "sous_categorie": "Polo", "marque": "Lacoste", "couleur": "Vert"},
        {"id": "a", "categorie": "Haut", "sous_categorie": "Polo", "marque": "Lacoste", "couleur": "Vert"},
    ]
    paths = assign_paths(rows)
    # ordre par id croissant : 'a' d'abord (n=1), 'b' ensuite (n=2)
    assert paths["a"] == "Haut/polo-lacoste-vert.png"
    assert paths["b"] == "Haut/polo-lacoste-vert-2.png"
