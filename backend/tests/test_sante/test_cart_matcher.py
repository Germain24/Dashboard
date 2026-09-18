"""TDD — cart_matcher sur le schema produits superc.ca (repoint 2026-07-23).

Le cache produits vient desormais de superc.ca (cf.
orchestration/a-faire/2026-07-23-superc-ca-repoint-plan.md, Task 4) : noms FR,
id/sku = UPC, href = "/allees/.../p/<UPC>", price_per_100g direct fourni par
le site. cart_matcher reutilise _matches / adonis_price_per_100g_edible /
_format_weight_kg (deja passes en FR et price_per_100g-first par les taches
2-3) : ce fichier fige best_product/cart_plan contre des fixtures au format
reel (valeurs tirees de task-1-report.md / du vrai superc.json peuple en
tache 3) plutot que l'ancien schema Instacart (noms EN, id numerique court,
href = slug produit).
"""
from app.services.sante.cart_matcher import best_product, cart_plan, resolve_products

# Cache realiste : "555 Riz basmati" est l'exemple flagship du vrai scrape
# superc.ca (task-1-report.md / task-3-report.md), format "4,54 kg" (virgule
# decimale FR) inclus tel quel — c'est le format REEL le plus courant sur le
# site, pas un cas synthetique.
CACHE = [
    {
        "name": "555 Riz basmati", "id": "062356540586", "sku": "062356540586",
        "href": "/allees/format-economique/marche-frais/riz-basmati/p/062356540586",
        "price": 14.99, "price_per_100g": 0.33, "unit_price": 3.3, "unit": "kg",
        "original_price": 16.79, "on_sale": True, "format": "4,54 kg",
    },
    {
        "name": "Riz basmati sac", "id": "060383800150", "sku": "060383800150",
        "href": "/allees/epicerie/riz-et-cereales/riz/p/060383800150",
        "price": 4.69, "price_per_100g": 0.469, "unit_price": None, "unit": None,
        "original_price": None, "on_sale": False, "format": "1 kg",
    },
]


def test_best_product_cheapest_per_100g_via_price_per_100g():
    # 0,33 $/100g (555, format economique) < 0,469 $/100g (sac 1 kg) : le
    # produit au prix AFFICHE le plus haut (14,99 $ > 4,69 $) gagne quand meme
    # car il est moins cher au 100 g.
    p = best_product(CACHE, {"kw": ["riz basmati"], "match": "any"})
    assert p["id"] == "062356540586"


def test_resolve_products_keeps_cheapest_per_kilo_not_cheapest_package(monkeypatch):
    monkeypatch.setattr(
        "app.services.sante.aliments.load_reservoir_product_refs", lambda: {},
    )
    monkeypatch.setitem(
        __import__("app.services.sante.cart_matcher", fromlist=["CATALOG_MAP"]).CATALOG_MAP,
        "Riz test", {"kw": ["riz basmati"], "match": "any"},
    )
    result = resolve_products(["Riz test"], CACHE)
    assert result["Riz test"]["id"] == "062356540586"


def test_best_product_prefers_price_per_100g_over_naive_price_format():
    # Preuve causale que best_product suit price_per_100g (fourni par le
    # site) et NON une derivation naive prix/format : ici la derivation
    # naive prix/format classerait les 2 produits dans l'ordre INVERSE de
    # price_per_100g (bloc A : 10$/1kg = 1,00$/100g naif, mais
    # price_per_100g SITE = 0,80 ; bloc B : 5$/1kg = 0,50$/100g naif, mais
    # price_per_100g SITE = 0,90). best_product doit suivre le
    # price_per_100g SITE (le bloc A gagne), pas la derivation naive (qui
    # donnerait le bloc B) — sinon le court-circuit price_per_100g de la
    # tache 2 ne serait pas reellement exerce ici.
    cache = [
        {"name": "Cheddar fort bloc A", "id": "100000000001", "sku": "100000000001",
         "href": "/allees/fromages/cheddar/p/100000000001",
         "price": 10.00, "price_per_100g": 0.80, "unit_price": None, "unit": None,
         "original_price": None, "on_sale": False, "format": "1 kg"},
        {"name": "Cheddar fort bloc B", "id": "100000000002", "sku": "100000000002",
         "href": "/allees/fromages/cheddar/p/100000000002",
         "price": 5.00, "price_per_100g": 0.90, "unit_price": None, "unit": None,
         "original_price": None, "on_sale": False, "format": "1 kg"},
    ]
    p = best_product(cache, {"kw": ["cheddar"], "match": "any"})
    assert p["id"] == "100000000001"


def test_cart_plan_returns_upc_id_and_superc_href():
    sl = [{"aliment": "Riz", "a_acheter_g": 500.0}]
    plan = cart_plan(sl, CACHE, item_map={"Riz": {"kw": ["riz basmati"], "match": "any"}})
    it = plan[0]
    assert it["product_id"] == "062356540586"   # id du produit matche = UPC
    assert it["href"] == "/allees/format-economique/marche-frais/riz-basmati/p/062356540586"
    assert it["format"] == "4,54 kg"


def test_cart_plan_qty_ceil_handles_french_decimal_comma_format():
    # Regression : "4,54 kg" (virgule decimale FR, format REEL superc.ca) doit
    # se lire comme 4,54 kg et non 54 kg. Bug trouve dans _format_weight_kg
    # (adonis_pricing.py, reutilise par cart_plan pour le calcul de qty) :
    # l'ancienne regex ([\d.]+) ne reconnaissait que le point comme separateur
    # decimal -> tronquait "4,54" a "4", echouait a matcher l'unite juste
    # apres (a cause de la virgule), puis retrouvait plus loin dans la chaine
    # un match parasite sur "54 kg" seul. Consequence reelle : qty largement
    # sous-estime pour la majorite des formats a poids fractionnaire du vrai
    # catalogue (177/1547 items avec virgule dans `format`, verifie contre
    # data/imports/Cuisine/superc.json).
    sl = [{"aliment": "Riz", "a_acheter_g": 9000.0}]
    plan = cart_plan(sl, CACHE, item_map={"Riz": {"kw": ["riz basmati"], "match": "any"}})
    it = plan[0]
    assert it["qty"] == 2      # ceil(9000 / 4540) == 2 (et NON ceil(9000/54000) == 1)
    assert it["a_verifier"] is False


def test_cart_plan_unmatched_flagged():
    plan = cart_plan([{"aliment": "Licorne", "a_acheter_g": 100.0}], CACHE,
                     item_map={"Licorne": {"kw": ["licorne"], "match": "any"}})
    assert plan[0]["a_verifier"] is True and plan[0].get("product_id") is None


def test_cart_plan_no_format_flags_verify():
    cache = [{
        "name": "Riz en vrac", "id": "999999999999", "sku": "999999999999",
        "href": "/allees/epicerie/riz-et-cereales/riz/p/999999999999",
        "price": 3.0, "price_per_100g": None, "unit_price": None, "unit": None,
        "original_price": None, "on_sale": False, "format": "",
    }]
    plan = cart_plan([{"aliment": "Riz", "a_acheter_g": 500.0}], cache,
                     item_map={"Riz": {"kw": ["riz"], "match": "any"}})
    assert plan[0]["product_id"] == "999999999999"
    assert plan[0]["qty"] == 1 and plan[0]["a_verifier"] is True


def test_carton_eggs_is_priced_from_unit_count():
    eggs = [{
        "name": "Selection Gros œufs", "id": "eggs-12", "sku": "eggs-12",
        "href": "/allees/oeufs/p/eggs-12", "price": 4.17,
        "price_per_100g": None, "unit_price": None, "unit": None,
        "format": "12 un",
    }]
    product = best_product(eggs, {"kw": ["œuf"], "match": "any"})
    assert product is not None
    plan = cart_plan(
        [{"aliment": "Oeufs", "quantite_g": 700}], eggs,
        item_map={"Oeufs": {"kw": ["œuf"], "match": "any"}},
    )
    assert plan[0]["qty"] == 2
    assert plan[0]["a_verifier"] is False


def test_variable_weight_produce_uses_real_average_unit_count_and_price():
    peaches = [{
        "name": "Grosse pêche", "id": "4038", "href": "/p/4038",
        "price": 1.42, "price_per_100g": 0.77,
        "unit_price": 7.70, "unit": "kg", "format": "",
    }]
    plan = cart_plan(
        [{"aliment": "Peche", "quantite_g": 300}], peaches,
        item_map={"Peche": {"kw": ["pêche"], "match": "any"}},
    )
    assert plan[0]["a_verifier"] is False
    # 1,42 $ / 7,70 $/kg = ~184 g par pêche : 300 g demandés nécessitent
    # deux fruits réellement ajoutés au panier, et non une ligne fictive de 300 g.
    assert plan[0]["qty"] == 2
    assert plan[0]["prix_estime"] == 1.42


def test_plantain_does_not_treat_one_unit_as_more_than_one_kilogram():
    plantains = [{
        "name": "Banane plantain", "id": "4235", "href": "/p/4235",
        "price": 0.84, "price_per_100g": 0.37,
        "unit_price": 3.70, "unit": "kg", "format": "",
    }]
    plan = cart_plan(
        [{"aliment": "Banane plantain", "quantite_g": 1174}], plantains,
        item_map={"Banane plantain": {"kw": ["banane plantain"]}},
    )
    assert plan[0]["qty"] == 6
    assert plan[0]["prix_estime"] == 0.84
    assert plan[0]["a_verifier"] is False
