"""TDD — outillage NON destructif de reconstruction d'aliments.csv sur Super C
(Phase 3 « Super C unique »). Logique pure : mapping, plan matché/retiré,
réécriture texte du CSV transposé. Aucune I/O, aucun écrasement du vrai CSV.
"""
from __future__ import annotations

from app.services.sante import superc_catalog_rebuild as scr


# ── CATALOG_MAP ───────────────────────────────────────────────────────────────

def test_catalog_map_covers_produce_and_non_produce():
    assert "Banane" in scr.CATALOG_MAP            # produce (PRODUCE_MAP)
    assert "Poitrine de poulet" in scr.CATALOG_MAP  # viande (NON_PRODUCE_KW)
    assert "Oeufs" in scr.CATALOG_MAP             # seed laitier/œufs


def test_catalog_map_excludes_supplements():
    # Suppléments / marques Costco : jamais mappés -> toujours retirés.
    assert "Whey protein (Inshape)" not in scr.CATALOG_MAP
    assert "Whey Leanfit vanille (Costco)" not in scr.CATALOG_MAP
    assert "Mass gainer Serious Mass banane (ON)" not in scr.CATALOG_MAP


def test_catalog_map_produce_keeps_edible_fraction():
    # PRODUCE_MAP prioritaire -> fraction comestible spécifique conservée.
    assert scr.CATALOG_MAP["Banane"]["edible"] == 0.64
    assert scr.CATALOG_MAP["Poitrine de poulet"]["edible"] == 1.0


def test_nuts_and_seeds_exclude_processed_bars_and_cereals():
    assert "barre" in scr.CATALOG_MAP["Arachides"]["not"]
    assert "céréale" in scr.CATALOG_MAP["Graines de tournesol"]["not"]


# ── plan_rebuild ──────────────────────────────────────────────────────────────

def test_plan_rebuild_classifies_matched_removed_and_kept():
    catalog = ["Banane", "Whey protein (Inshape)", "Poitrine de poulet", "Asperges"]
    overlay = {"Banane": 0.3, "Poitrine de poulet": 0.9}
    # "Whey..." hors mapping (supplément), "Asperges" mappé mais sans prix ce coup-ci.
    mappable = {"Banane", "Poitrine de poulet", "Asperges"}
    matched, removed, kept_no_price = scr.plan_rebuild(catalog, overlay, mappable)
    assert matched == {"Banane": 0.3, "Poitrine de poulet": 0.9}
    assert removed == ["Whey protein (Inshape)"]      # hors mapping -> retiré
    assert kept_no_price == ["Asperges"]              # vendu mais pas de prix -> conservé


# ── catalog_price_overlay ─────────────────────────────────────────────────────

def test_catalog_price_overlay_matches_meat_from_superc_items():
    items = [{"name": "Poitrine de poulet désossée sans peau", "price": 9.0, "format": "1 kg",
              "unit_price": None, "unit": None}]
    overlay = scr.catalog_price_overlay(items)
    assert overlay["Poitrine de poulet"] == 0.9   # 9$/kg /10 /1.0


def test_catalog_price_overlay_can_limit_work_to_plan_foods():
    items = [{"name": "Poitrine de poulet désossée sans peau", "price": 9.0,
              "format": "1 kg", "unit_price": None, "unit": None}]
    overlay = scr.catalog_price_overlay(items, target_names={"Poitrine de poulet"})
    assert overlay == {"Poitrine de poulet": 0.9}


def test_catalog_price_overlay_oeufs_never_matches_aubergine():
    # Bug historique (Instacart EN) : "egg" matchait "eggplant". Version FR :
    # les deux mots n'ont plus rien en commun, mais on verifie que le `not`
    # explicite (spec) tient bon et que seul l'item oeufs contribue au prix.
    items = [
        {"name": "Aubergine italienne bio", "price": 0.2, "price_per_100g": 0.2,
         "format": "1 un", "unit_price": None, "unit": None,
         "href": "/allees/fruits-et-legumes/p/1"},
        {"name": "Selection Gros œufs", "price": 4.17, "price_per_100g": 0.7,
         "format": "12 un", "unit_price": None, "unit": None,
         "href": "/allees/oeufs/p/2"},
    ]
    overlay = scr.catalog_price_overlay(items)
    assert overlay["Oeufs"] == 0.7          # l'item oeufs, pas l'aubergine (0.2)
    assert overlay["Aubergine"] == 0.2


# ── rewrite_catalog_csv ───────────────────────────────────────────────────────

def test_rewrite_drops_unmatched_columns_and_updates_prix_only():
    lines = [
        "Nutriments;Banane;Whey protein (Inshape);Poitrine de poulet",
        "Prix;0.26;5.87;1.76",
        "Proteines;1.06;77;20",
    ]
    matched = {"Banane": 0.30, "Poitrine de poulet": 0.90}
    removed = ["Whey protein (Inshape)"]
    out = scr.rewrite_catalog_csv(lines, matched, removed)
    assert out == [
        "Nutriments;Banane;Poitrine de poulet",
        "Prix;0.3;0.9",
        "Proteines;1.06;20",   # teneurs CIQUAL préservées, colonne Whey retirée
    ]


def test_rewrite_preserves_unmatched_kept_food_untouched():
    # Un aliment ni matché ni retiré (ex. prix Super C indisponible cette
    # semaine) : ici Poitrine n'est pas dans matched -> son prix reste tel quel.
    lines = [
        "Nutriments;Banane;Poitrine de poulet",
        "Prix;0.26;1.76",
    ]
    out = scr.rewrite_catalog_csv(lines, {"Banane": 0.3}, removed=[])
    assert out == ["Nutriments;Banane;Poitrine de poulet", "Prix;0.3;1.76"]
