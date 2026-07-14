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
    items = [{"name": "Chicken Breast Boneless", "price": 9.0, "format": "1 kg",
              "unit_price": None, "unit": None}]
    overlay = scr.catalog_price_overlay(items)
    assert overlay["Poitrine de poulet"] == 0.9   # 9$/kg /10 /1.0


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
