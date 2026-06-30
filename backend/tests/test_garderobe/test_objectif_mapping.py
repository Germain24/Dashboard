"""Table de correspondance sous_categorie/categorie -> type objectif."""
from __future__ import annotations

from app.services.garderobe.objectif_mapping import derive_type_objectif, norm

TYPES = [
    "T-shirts", "Polos", "Chemises", "Bottines", "Pantalons chino",
    "Jeans", "Jogging", "Vestes légères", "Vestes de sport",
    "Pantalons habillés", "Lunettes de soleil",
]


def test_norm_accents_casse_separateurs():
    assert norm("Vert Émeraude") == "vert emeraude"
    assert norm("T-shirt") == "t shirt"
    assert norm("  Button  Up ") == "button up"
    assert norm(None) == ""


def test_derive_mappings_connus():
    assert derive_type_objectif("Haut", "Polo", TYPES) == "Polos"
    assert derive_type_objectif("Haut", "T-shirt", TYPES) == "T-shirts"
    assert derive_type_objectif("Haut", "T-shirt Manches Longues", TYPES) == "T-shirts"
    assert derive_type_objectif("Shirt", "Button Up", TYPES) == "Chemises"
    assert derive_type_objectif("Chaussures", "Chelsea Boots", TYPES) == "Bottines"
    assert derive_type_objectif("Pantalon", "Chino", TYPES) == "Pantalons chino"
    assert derive_type_objectif("Veste", "Veste Sport", TYPES) == "Vestes de sport"
    assert derive_type_objectif("Yeux", "Lunettes de Soleil", TYPES) == "Lunettes de soleil"


def test_derive_insensible_casse_accents():
    assert derive_type_objectif("Haut", "polo", TYPES) == "Polos"
    assert derive_type_objectif("x", "CHINO", TYPES) == "Pantalons chino"


def test_derive_non_mappable_renvoie_none():
    assert derive_type_objectif("Montre", "Smartwatch", TYPES) is None
    assert derive_type_objectif("Bijoux", "Bracelet", TYPES) is None
    assert derive_type_objectif("Yeux", "Lunettes de vue", TYPES) is None
    assert derive_type_objectif(None, None, TYPES) is None


def test_derive_type_absent_des_noms_renvoie_none():
    # "Polos" mappé mais absent de la liste fournie -> None
    assert derive_type_objectif("Haut", "Polo", ["T-shirts"]) is None
