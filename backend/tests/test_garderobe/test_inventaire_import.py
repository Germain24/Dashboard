"""Import inventaire garde-robe (scripts/import_garderobe_inventaire.py).

Fonctions pures : normalisation couleurs (casse Excel != casse app),
résolution Type Excel -> ObjectifType, nommage des pixel arts numérotés,
parsing de l'Excel inventaire (motifs texte/booléen mélangés).
"""
from __future__ import annotations

import openpyxl
import pytest

from scripts.import_garderobe_inventaire import (
    normalize_couleur,
    parse_inventaire,
    resolve_type_objectif,
    target_asset_name,
)

OBJECTIF_NAMES = [
    "T-shirts", "Polos", "Chemises", "Jeans", "Pantalons chino",
    "Pantalons habillés", "Jogging", "Vestes légères", "Manteaux",
    "Coupe-vent / Imperméables", "Bottines", "Lunettes de soleil",
    "Vestes de sport", "Gilets",
]


# ── normalize_couleur ────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw, expected", [
    ("Bleu Marine", "Bleu marine"),        # casse Excel -> casse app
    ("Gris Anthracite", "Gris anthracite"),
    ("Beige Sable", "Beige sable"),
    ("Noir", "Noir"),
    ("Vert Émeraude", "Vert émeraude"),    # accents preserves cote canonique
    ("Vert Bouteille", "Vert bouteille"),  # nouvelle couleur canonique
    ("Blanc Casse", "Blanc cassé"),
    ("  Beige Camel ", "Beige camel"),
    (None, None),
    ("", None),
])
def test_normalize_couleur(raw, expected):
    assert normalize_couleur(raw) == expected


def test_couleur_inconnue_prend_une_forme_propre():
    assert normalize_couleur("ROSE FLUO") == "Rose fluo"


# ── resolve_type_objectif ────────────────────────────────────────────────────

@pytest.mark.parametrize("type_excel, expected", [
    ("T-shirt", "T-shirts"),
    ("T-shirt Manches Longues", "T-shirts"),
    ("Blouson", "Vestes légères"),
    ("Veste", "Vestes légères"),           # défaut, à préciser pièce par pièce
    ("Manteau", "Manteaux"),
    ("Coupe-vent", "Coupe-vent / Imperméables"),
    ("Jogging", "Jogging"),
    ("Chelsea Boots", "Bottines"),
    ("Lunettes de Soleil", "Lunettes de soleil"),
])
def test_resolve_type_objectif(type_excel, expected):
    assert resolve_type_objectif(type_excel, OBJECTIF_NAMES) == expected


@pytest.mark.parametrize("type_excel", [
    "Smartwatch", "Montre Analogique", "Montre Automatique",
    "Bracelet", "Collier", "Lunettes de Vue",
])
def test_accessoires_volontairement_non_rattaches(type_excel):
    # Le bug historique rattachait collier -> "Gilets" et lunettes de vue ->
    # "Lunettes de soleil" : ces types doivent rester SANS objectif.
    assert resolve_type_objectif(type_excel, OBJECTIF_NAMES) is None


def test_type_inconnu_non_rattache():
    assert resolve_type_objectif("Cape d'invisibilité", OBJECTIF_NAMES) is None


# ── target_asset_name ────────────────────────────────────────────────────────

def test_fichier_deja_en_slug_garde_son_nom():
    row = {"pixel": "bomber-shinzo-khaki.png", "type": "Blouson",
           "marque": "Shinzo", "couleur": "Beige"}
    # La DB reference deja ce nom : ne JAMAIS le renommer.
    assert target_asset_name(row) == "bomber-shinzo-khaki.png"


def test_fichier_numerote_renomme_en_slug():
    row = {"pixel": "Veste01.png", "type": "Veste",
           "marque": "Fender", "couleur": "Beige"}
    assert target_asset_name(row) == "veste-fender-beige.png"


def test_fichier_numerote_avec_accents_et_espaces():
    row = {"pixel": "Manteau07.png", "type": "Coupe-vent",
           "marque": "Equipe Foot Japon", "couleur": "Gris"}
    assert target_asset_name(row) == "coupe-vent-equipe-foot-japon-gris.png"


# ── parse_inventaire ─────────────────────────────────────────────────────────

HEADER = ["Marque", "Type", "Couleur", "Couleur Secondaire", "Motifs",
          "Photos Avant", "Photos Arriere", "Photos Pixelise", "Usure",
          "Coton", "Lin", "Cuir"]


def _write_xlsx(path, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(HEADER)
    for r in rows:
        ws.append(r)
    wb.save(path)


def test_parse_inventaire(tmp_path):
    path = tmp_path / "Vetements.xlsx"
    _write_xlsx(path, [
        ["Shinzo", "Blouson", "Beige", None, False,
         "a.jpg", "b.jpg", "bomber-shinzo-khaki.png", 0, 0, 0, 0],
        # Motifs en TEXTE 'TRUE' (mélange réel du fichier), matières remplies
        ["Fender", "Veste", "Beige", "Rouge", "TRUE",
         "c.jpg", "d.jpg", "Veste01.png", 0.8, 1, 0, 0.5],
        # Ligne vide (pas de marque) -> ignorée
        [None, None, None, None, None, None, None, None, None, None, None, None],
    ])
    rows = parse_inventaire(path)
    assert len(rows) == 2

    r1, r2 = rows
    assert r1["marque"] == "Shinzo" and r1["motifs"] is False
    assert r1["composition"] == {}

    assert r2["motifs"] is True                      # 'TRUE' texte -> bool
    assert r2["couleur_secondaire"] == "Rouge"
    assert r2["usure_pct"] == 0.8
    assert r2["composition"] == {"Coton": 1.0, "Cuir": 0.5}  # 0 exclus
    assert r2["photo_avant"] == "c.jpg" and r2["photo_arriere"] == "d.jpg"


# ── resolve_categorie : le TYPE décide du slot thermique, pas le dossier ─────
# (tous les extérieurs vivent dans Pixelisé/Manteau/, mais une Veste doit
# rester catégorie "Veste" -- slot "frais" -- et pas "Manteau" -- froid/pluie).

def test_resolve_categorie_veste_ne_devient_pas_manteau():
    from scripts.import_garderobe_inventaire import resolve_categorie
    assert resolve_categorie("Veste", "Manteau") == "Veste"


@pytest.mark.parametrize("type_excel, dossier, expected", [
    ("Blouson", "Manteau", "Manteau"),
    ("Coupe-vent", "Manteau", "Manteau"),
    ("T-shirt Manches Longues", "Haut", "Haut"),
    ("Chemise", "Shirt", "Shirt"),
    ("Jean Ballon", "Pantalon", "Pantalon"),
    ("Chelsea Boots", "Chaussures", "Chaussures"),
    ("Collier", "Cou", "Cou"),
    ("Type Inconnu", "DossierX", "DossierX"),   # repli sur le dossier réel
])
def test_resolve_categorie(type_excel, dossier, expected):
    from scripts.import_garderobe_inventaire import resolve_categorie
    assert resolve_categorie(type_excel, dossier) == expected
