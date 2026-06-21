"""TDD — re-tarification des fruits & légumes Adonis dans le catalogue nutrition.

Adonis (prix CAD au paquet / au kg) -> Prix aliments.csv (CAD/100 g comestible).
Seuls les fruits & légumes sont concernés ; le reste reste Costco.
"""

from __future__ import annotations

import pandas as pd

from app.services.sante.adonis_pricing import (
    adonis_price_per_100g_edible,
    build_price_overlay,
    apply_overlay_to_df,
)


# ── Conversion d'unité ────────────────────────────────────────────────────────

def test_price_from_per_kg_with_edible_fraction():
    # Banane 1,96 $/kg -> 0,196 $/100 g ; portion comestible 0,64 -> 0,306
    item = {"name": "Banana", "unit_price": 1.96, "unit": "kg", "price": 0.38,
            "price_unit": "each", "format": "About 0.19 kg each"}
    assert adonis_price_per_100g_edible(item, 0.64) == 0.306


def test_price_from_package_weight_grams():
    # Paquet 675 g à 6,29 $ -> 9,319 $/kg -> 0,932 $/100 g (comestible 1,0)
    item = {"name": "Arctic Gardens Frozen", "unit_price": None, "price": 6.29, "format": "675 g"}
    assert adonis_price_per_100g_edible(item, 1.0) == 0.932


def test_price_from_per_lb_converted_to_kg():
    # 2,00 $/lb -> 4,409 $/kg -> 0,441 $/100 g
    item = {"name": "X", "unit_price": 2.0, "unit": "lb", "price": None}
    assert adonis_price_per_100g_edible(item, 1.0) == 0.441


def test_price_none_when_no_weight_info():
    assert adonis_price_per_100g_edible({"name": "Berries", "price": 3.99, "format": ""}, 1.0) is None


# ── Matching FR <-> Adonis (mots entiers, pas de faux positifs) ───────────────

def test_apple_keyword_does_not_match_pineapple():
    adonis = [
        {"name": "Pineapple", "unit_price": 3.0, "unit": "kg", "price": 4.0, "format": ""},
        {"name": "Gala Apple", "unit_price": 4.39, "unit": "kg", "price": 1.0, "format": ""},
    ]
    overlay = build_price_overlay(adonis)
    assert "Pomme" in overlay                 # Gala Apple
    assert "Ananas" in overlay                # Pineapple
    assert overlay["Pomme"] != overlay["Ananas"]


def test_overlay_skips_non_produce():
    adonis = [{"name": "Chocolate Cookie", "price": 3.0, "format": "300 g"}]
    assert build_price_overlay(adonis) == {}


def test_overlay_picks_cheapest_match():
    adonis = [
        {"name": "Organic Banana", "unit_price": 3.50, "unit": "kg", "price": 0, "format": ""},
        {"name": "Banana", "unit_price": 1.96, "unit": "kg", "price": 0, "format": ""},
    ]
    overlay = build_price_overlay(adonis)
    # 1,96/kg /10 /0,64 = 0,306 (moins cher que la bio)
    assert overlay["Banane"] == 0.306


# ── Application au DataFrame du catalogue ─────────────────────────────────────

def test_apply_overlay_only_changes_matched_produce_prices():
    df = pd.DataFrame(
        {"Prix": [0.50, 1.76, 2.00]},
        index=["Banane", "Poitrine de poulet", "Brocoli"],
    )
    overlay = {"Banane": 0.306, "Brocoli": 0.44, "Inconnu": 9.9}
    out, changed = apply_overlay_to_df(df, overlay)
    assert out.loc["Banane", "Prix"] == 0.306
    assert out.loc["Brocoli", "Prix"] == 0.44
    assert out.loc["Poitrine de poulet", "Prix"] == 1.76   # inchangé (pas produce)
    assert set(changed) == {"Banane", "Brocoli"}            # "Inconnu" absent du df
