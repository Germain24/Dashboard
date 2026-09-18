"""TDD — matching produits Super C en FRANÇAIS (repoint superc.ca 2026-07-23).

Bug corrigé : le matching tournait sur des mots-clés ANGLAIS (vitrine
Instacart) alors que superc.ca renvoie des noms de produits FRANÇAIS ->
faux matchs (ex. "Oeufs" matchait "eggplant" = aubergine, cf.
orchestration/a-faire/2026-07-23-superc-ca-repoint-design.md §B). Ce fichier
fige le comportement attendu contre un cache FR réaliste (styles de noms
observés sur superc.ca, cf. task-1-report.md) : plus aucun mot-clé anglais
ne doit survivre dans CATALOG_MAP / PRODUCE_MAP.
"""
from __future__ import annotations

import pytest

from app.services.sante.adonis_pricing import build_price_overlay
from app.services.sante.adonis_pricing import purchase_unit_weight_kg
from app.services.sante.cart_matcher import best_product, resolve_products
from app.services.sante.superc_catalog_rebuild import CATALOG_MAP

# Cache FR réaliste : styles de noms réellement observés sur superc.ca
# (task-1-report.md), UPC en `id`, `price_per_100g` direct comme le scraper
# Task 1 le fournit. Volontairement mélangé (ordre alphabétique du vrai
# superc.json) pour ne pas dépendre d'un ordre de scan favorable.
FR_CACHE: list[dict] = [
    {
        "name": "Aubergine bio", "id": "111", "sku": "111",
        "href": "/allees/fruits-et-legumes/legumes/aubergines/p/111",
        "price": 2.99, "price_per_100g": 0.45, "unit_price": 4.5, "unit": "kg",
        "original_price": None, "on_sale": False, "format": "1 un",
    },
    {
        "name": "Brocoli", "id": "222", "sku": "222",
        "href": "/allees/fruits-et-legumes/legumes/brocoli/p/222",
        "price": 2.99, "price_per_100g": None, "unit_price": None, "unit": None,
        "original_price": None, "on_sale": False, "format": "1 un",
    },
    {
        "name": "MINUTE RICE Riz blanc à grains longs précuit", "id": "333", "sku": "333",
        "href": "/allees/epicerie/riz-et-cereales/riz/p/333",
        "price": 6.99, "price_per_100g": 0.50, "unit_price": None, "unit": None,
        "original_price": None, "on_sale": False, "format": "1,4 kg",
    },
    {
        "name": "555 Riz basmati", "id": "444", "sku": "444",
        "href": "/allees/format-economique/marche-frais/riz-basmati/p/444",
        "price": 14.99, "price_per_100g": 0.33, "unit_price": 3.3, "unit": "kg",
        "original_price": 16.79, "on_sale": True, "format": "4,54 kg",
    },
    {
        "name": "Selection Gros œufs", "id": "555", "sku": "555",
        "href": "/allees/produits-laitiers-et-oeufs/oeufs/oeufs-entiers/gros-oeufs/p/555",
        "price": 4.17, "price_per_100g": None, "unit_price": None, "unit": None,
        "original_price": None, "on_sale": False, "format": "12 un",
    },
]


def test_oeufs_matches_eggs_never_aubergine():
    # LE bug historique (Instacart EN "egg" -> "eggplant") : en FR, "Oeufs"
    # doit matcher "Selection Gros œufs" et ne JAMAIS matcher "Aubergine bio".
    # Les cartons sont convertis avec 50 g comestibles par œuf afin de produire
    # le même prix aux 100 g que le reste du catalogue.
    prod = best_product(FR_CACHE, CATALOG_MAP["Oeufs"])
    assert prod is not None
    assert prod["id"] == "555"
    assert "aubergine" not in (prod["name"] or "").lower()
    # Sanity : aucun aliment du cache FR ne se retrouve, à tort, à matcher
    # sur les œufs pour un autre aliment (ex. l'aubergine ne doit pas non
    # plus apparaitre dans l'overlay sous la clé "Oeufs").
    overlay = build_price_overlay(FR_CACHE, CATALOG_MAP)
    assert overlay["Oeufs"] == pytest.approx(0.695)


def test_circulaire_naturalia_sans_format_est_un_carton_de_douze_oeufs():
    item = {
        "name": "oeufs blancs poules en liberté Mieux-être Naturalia",
        "price": 3.75,
        "format": "",
    }
    assert purchase_unit_weight_kg(item) == pytest.approx(0.600)


def test_aubergine_matches_its_own_item_not_oeufs():
    # Sens inverse : "Aubergine" ne doit pas se faire polluer par les œufs.
    prod = best_product(FR_CACHE, CATALOG_MAP["Aubergine"])
    assert prod is not None
    assert prod["id"] == "111"


def test_brocoli_matches_broccoli_item():
    prod = best_product(FR_CACHE, CATALOG_MAP["Brocoli"])
    assert prod is not None
    assert prod["id"] == "222"
    overlay = build_price_overlay(FR_CACHE, CATALOG_MAP)
    assert "Brocoli" not in overlay   # pas de format/prix dérivable (vendu à l'unité) -> non chiffrable, cf. best_product qui retourne quand même l'item


def test_riz_basmati_matches_basmati_not_generic_white_rice():
    # Spécificité : "Riz basmati (sec)" doit matcher le riz basmati identifié
    # comme tel, PAS n'importe quel riz blanc générique (variété différente).
    prod = best_product(FR_CACHE, CATALOG_MAP["Riz basmati (sec)"])
    assert prod is not None
    assert prod["id"] == "444"
    overlay = build_price_overlay(FR_CACHE, CATALOG_MAP)
    assert overlay["Riz basmati (sec)"] == 0.33


def test_fromage_blanc_uses_quebec_cottage_name_not_brined_cheese():
    cache = [
        {
            "name": "Neilson Fromage cottage 2 %", "id": "601", "sku": "601",
            "href": "/allees/produits-laitiers-et-oeufs/fromages/cottage/p/601",
            "price": 4.29, "price_per_100g": 0.86, "format": "500 g",
        },
        {
            "name": "Krinos Fromage Blanc en Saumure", "id": "602", "sku": "602",
            "href": "/allees/produits-laitiers-et-oeufs/fromages/p/602",
            "price": 2.99, "price_per_100g": 0.50, "format": "400 g",
        },
    ]
    product = best_product(cache, CATALOG_MAP["Fromage blanc"])
    assert product is not None
    assert product["id"] == "601"


def test_cheddar_never_matches_macaroni_preparation():
    cache = [
        {
            "name": "Selection Préparation pour macaroni au fromage cheddar extra crémeux",
            "id": "603", "sku": "603", "price": 0.89,
            "price_per_100g": 0.45, "format": "200 g",
        },
        {
            "name": "Selection Fromage cheddar moyen", "id": "604", "sku": "604",
            "price": 5.49, "price_per_100g": 1.37, "format": "400 g",
        },
    ]
    product = best_product(cache, CATALOG_MAP["Fromage cheddar"])
    assert product is not None
    assert product["id"] == "604"


def test_orange_never_matches_popsicle():
    cache = [
        {"name": "Popsicle Bâtons glacés à saveur d'orange", "id": "605",
         "sku": "605", "price": 2.25, "price_per_100g": 0.20, "format": "1 kg"},
        {"name": "Sac d'oranges", "id": "606", "sku": "606",
         "price": 5.99, "price_per_100g": 0.60, "format": "1 kg"},
    ]
    product = best_product(cache, CATALOG_MAP["Orange"])
    assert product is not None
    assert product["id"] == "606"


def test_produits_purs_ne_matchent_pas_leurs_plats_ou_assaisonnements():
    cache = [
        {"name": "Gilly Dumplings au porc et crevette", "id": "607",
         "sku": "607", "price": 4.00, "price_per_100g": 0.45, "format": "900 g"},
        {"name": "Selection Crevettes nordiques cuites surgelées", "id": "608",
         "sku": "608", "price": 8.00, "price_per_100g": 2.00, "format": "400 g"},
        {"name": "Windsor Sel iodé et poivre noir", "id": "609",
         "sku": "609", "price": 2.00, "price_per_100g": 1.00, "format": "200 g"},
        {"name": "Windsor Sel iodé", "id": "610",
         "sku": "610", "price": 3.00, "price_per_100g": 1.50, "format": "200 g"},
        {"name": "Irrésistible Arachides à saveur de BBQ", "id": "611",
         "sku": "611", "price": 3.00, "price_per_100g": 0.50, "format": "600 g"},
        {"name": "Selection Arachides rôties à sec", "id": "612",
         "sku": "612", "price": 5.00, "price_per_100g": 0.72, "format": "700 g"},
    ]
    assert best_product(cache, CATALOG_MAP["Crevettes cuites"])["id"] == "608"
    assert best_product(cache, CATALOG_MAP["Sel iode"])["id"] == "610"
    assert best_product(cache, CATALOG_MAP["Arachides"])["id"] == "612"


def test_yogourts_grecs_nature_sont_separes_par_taux_de_gras():
    cache = [
        {"name": "Oikos Yogourt grec nature 0 %", "id": "610", "sku": "610",
         "href": "/allees/produits-laitiers-et-oeufs/yogourts/p/610",
         "price": 6.49, "price_per_100g": 0.87, "format": "750 g"},
        {"name": "Liberté Yogourt nature 2 % Grec", "id": "613", "sku": "613",
         "href": "/allees/produits-laitiers-et-oeufs/yogourts/p/613",
         "price": 6.97, "price_per_100g": 0.93, "format": "750 g"},
        {"name": "Liberté Yogourt grec nature 9 %", "id": "611", "sku": "611",
         "href": "/allees/produits-laitiers-et-oeufs/yogourts/p/611",
         "price": 6.99, "price_per_100g": 0.93, "format": "750 g"},
        {"name": "Oikos Yogourt grec vanille 0 %", "id": "612", "sku": "612",
         "href": "/allees/produits-laitiers-et-oeufs/yogourts/p/612",
         "price": 5.99, "price_per_100g": 0.80, "format": "750 g"},
    ]
    zero = best_product(cache, CATALOG_MAP["Yogourt grec nature 0%"])
    two = best_product(cache, CATALOG_MAP["Yogourt grec nature 2%"])
    entier = best_product(cache, CATALOG_MAP["Yogourt grec nature entier"])
    assert zero and zero["id"] == "610"
    assert two and two["id"] == "613"
    assert entier and entier["id"] == "611"


def test_yogourt_grec_entier_accepte_le_nature_quatre_pourcent():
    cache = [
        {"name": "Olympic Yogourt grec nature biologique 4 %", "id": "614",
         "sku": "614", "price": 6.99, "price_per_100g": 0.93,
         "format": "750 g"},
    ]
    product = best_product(cache, CATALOG_MAP["Yogourt grec nature entier"])
    assert product and product["id"] == "614"


def test_bacon_et_ananas_ne_matchent_pas_mayonnaise_ou_marinade():
    cache = [
        {"name": "Heinz Sauce style mayonnaise à saveur de bacon fumé",
         "id": "615", "sku": "615", "price": 2.0,
         "price_per_100g": 0.5, "format": "340 g"},
        {"name": "Selection Bacon", "id": "616", "sku": "616",
         "price": 6.0, "price_per_100g": 2.0, "format": "300 g"},
        {"name": "VH Marinade à l'ananas", "id": "617", "sku": "617",
         "price": 2.0, "price_per_100g": 0.5, "format": "341 mL"},
        {"name": "Ananas", "id": "618", "sku": "618", "price": 4.0,
         "price_per_100g": 0.8, "format": "500 g"},
    ]
    assert best_product(cache, CATALOG_MAP["Bacon"])["id"] == "616"
    assert best_product(cache, CATALOG_MAP["Ananas"])["id"] == "618"


def test_ail_et_amandes_ne_matchent_pas_plats_prepares_ou_granola():
    cache = [
        {"name": "McCain Bouchées de pommes de terre chili et ail surgelées",
         "id": "619", "sku": "619", "price": 2.0,
         "price_per_100g": 0.4, "format": "550 g",
         "href": "/allees/produits-surgeles/fruits-et-legumes/p/619"},
        {"name": "Ail", "id": "620", "sku": "620", "price": 1.0,
         "price_per_100g": 1.0, "format": "100 g",
         "href": "/allees/fruits-et-legumes/legumes/p/620"},
        {"name": "Mieux-Être Granola au miel et aux amandes", "id": "621",
         "sku": "621", "price": 3.0, "price_per_100g": 0.6,
         "format": "475 g"},
        {"name": "Irrésistible Olives farcies aux amandes", "id": "623",
         "sku": "623", "price": 3.0, "price_per_100g": 0.5,
         "format": "500 g"},
        {"name": "Selection Amandes naturelles", "id": "622", "sku": "622",
         "price": 6.0, "price_per_100g": 1.2, "format": "500 g"},
    ]
    assert best_product(cache, CATALOG_MAP["Ail"])["id"] == "620"
    assert best_product(cache, CATALOG_MAP["Amandes"])["id"] == "622"


def test_epinards_frais_ne_matchent_pas_une_saucisse_aux_epinards():
    cache = [
        {
            "name": "Mieux-Être Saucisses végétariennes au feta et épinards",
            "id": "620", "sku": "620", "price_per_100g": 1.70,
            "href": "/allees/fruits-et-legumes/vegetalien-et-vegetarien/p/620",
        },
        {
            "name": "Sac d'épinards", "id": "621", "sku": "621",
            "price_per_100g": 3.15,
            "href": "/allees/fruits-et-legumes/legumes-feuillus/epinards/p/621",
        },
    ]
    product = best_product(cache, CATALOG_MAP["Epinards"])
    assert product and product["id"] == "621"


def test_correspondances_superc_extras_restent_des_produits_purs():
    cache = [
        {"name": "Fry's Cacao première qualité", "id": "630", "sku": "630",
         "price_per_100g": 2.86},
        {"name": "Granola chocolat cacao", "id": "631", "sku": "631",
         "price_per_100g": 1.00},
        {"name": "Selection Cannelle moulue", "id": "632", "sku": "632",
         "price_per_100g": 2.65},
        {"name": "Quaker Gruau pomme cannelle", "id": "633", "sku": "633",
         "price_per_100g": 1.00},
        {"name": "Kraft Beurre d'arachide crémeux", "id": "634", "sku": "634",
         "price_per_100g": 0.57},
        {"name": "Kraft Beurre d'arachide naturel Juste des arachides",
         "id": "635", "sku": "635", "price_per_100g": 0.87},
    ]
    assert best_product(cache, CATALOG_MAP["Cacao non sucre en poudre"])["id"] == "630"
    assert best_product(cache, CATALOG_MAP["Cannelle moulue"])["id"] == "632"
    assert best_product(cache, CATALOG_MAP["Beurre d'arachide"])["id"] == "635"


def test_amandes_ne_matchent_pas_une_creme_glacee_aux_amandes():
    cache = [
        {
            "name": "Chapman's Crème glacée à la vanille, amandes et chocolat",
            "id": "ice-cream-almonds", "price": 4.0,
            "price_per_100g": 0.2, "format": "1 L",
        },
        {
            "name": "Selection Amandes naturelles",
            "id": "plain-almonds", "price": 6.0,
            "price_per_100g": 1.2, "format": "500 g",
        },
    ]

    product = best_product(cache, CATALOG_MAP["Amandes"])

    assert product and product["id"] == "plain-almonds"
    resolved = resolve_products(["Amandes"], cache)
    assert resolved["Amandes"]["id"] == "plain-almonds"


# Cache dédié "Fraises vs frappé" (rapport de raffinage 2026-07-24, bug
# remonté par un run utilisateur réel) : le nom du frappé contient "fraise"
# comme simple SAVEUR (ex. "Irrésistible Frappé à saveur de fraise-banane",
# style réellement observé dans le vrai superc.json) et était moins cher au
# 100 g que les vraies fraises -> sans l'exclusion "frappé"/"smoothie" dans
# PRODUCE_MAP, il gagnait (best_product retient le moins cher des matchés) et
# "Fraises" pointait vers une boisson glacée sucrée, pas des fraises.
FRAISES_VS_FRAPPE_CACHE: list[dict] = [
    {
        "name": "Fraises", "id": "701", "sku": "701",
        "href": "/allees/fruits-et-legumes/fruits/baies-et-cerises/fraises/p/701",
        "price": 3.99, "price_per_100g": 0.53, "unit_price": None, "unit": None,
        "original_price": None, "on_sale": False, "format": "750 mL",
    },
    {
        "name": "Irrésistible Frappé à saveur de fraise-banane", "id": "702", "sku": "702",
        "href": "/allees/boissons/jus-et-boissons/smoothies-et-nectars/frappe-a-saveur-de-fraise-banane/p/702",
        # Volontairement MOINS cher au 100 g que les vraies fraises : c'est
        # justement pourquoi ce faux match gagnait avant le correctif.
        "price": 4.99, "price_per_100g": 0.30, "unit_price": 3.0, "unit": "kg",
        "original_price": None, "on_sale": False, "format": "1,65 L",
    },
]


def test_fraises_never_matches_frappe_or_smoothie():
    prod = best_product(FRAISES_VS_FRAPPE_CACHE, CATALOG_MAP["Fraises"])
    assert prod is not None
    assert prod["id"] == "701"
    assert "frappé" not in (prod["name"] or "").lower()
    # L'overlay de prix doit chiffrer les VRAIES fraises (0.53), pas le
    # frappé moins cher (0.30) qu'il aurait fallu ignorer.
    overlay = build_price_overlay(FRAISES_VS_FRAPPE_CACHE, CATALOG_MAP)
    assert overlay["Fraises"] == 0.53


def test_no_stray_english_keywords_remain_in_catalog_map():
    # Garde-fou anti-régression : aucun mot-clé EN historique ne doit
    # survivre dans le catalogue (source des faux matchs corrigés ici).
    # Note : les suppléments (Inshape/ON/Costco) restent EN mais sont déjà
    # exclus de CATALOG_MAP (_is_supplement) -> jamais des clés ici.
    # N'inclut PAS les mots identiques FR/EN (cheddar, feta, brie, gouda,
    # parmesan, camembert, tahini, houmous/hummus, quinoa, basmati, bacon…),
    # ni "clementine"/"prune" (fallbacks ASCII/mots FR volontaires qui
    # s'écrivent pareil en anglais) : ce ne sont pas des mots-clés anglais
    # fautifs, juste des mots qui s'écrivent pareil dans les 2 langues.
    stray_en = {
        "egg", "banana", "avocado", "apple", "grape", "broccoli", "spinach",
        "carrot", "onion", "tomato", "cucumber", "zucchini", "eggplant",
        "chicken breast", "ground beef", "ground turkey", "salmon", "milk",
        "butter", "whole milk", "skim milk", "greek", "goat", "cranberr",
        "strawberr", "raspberr", "blueberr", "cherr", "pear", "peach",
        "mango", "plum", "pineapple", "grapefruit",
        "pomegranate", "sweet potato", "mushroom", "cauliflower", "celery",
        "asparagus", "arugula", "green bean", "green pea", "black olive",
        "bell pepper",
    }
    for aliment, spec in CATALOG_MAP.items():
        for kw in spec["kw"]:
            assert kw.lower() not in stray_en, f"{aliment!r} a encore le mot-clé EN {kw!r}"
