"""TDD — l'overlay prix prefere price_per_100g direct (superc.ca) a la derivation.

Le nouveau scraper superc.ca (Task 1) fournit price_per_100g directement dans
chaque item (CAD/100 g brut). adonis_price_per_100g_edible doit l'utiliser en
priorite, et ne retomber sur la derivation (unit_price/format) que si absent.
"""

from __future__ import annotations

from app.services.sante.adonis_pricing import adonis_price_per_100g_edible


def test_uses_price_per_100g_directly():
    item = {"price_per_100g": 0.50, "price": 6.99, "format": "1,4 kg"}
    assert adonis_price_per_100g_edible(item, 1.0) == 0.50
    # fraction comestible : le prix/100 g comestible monte
    assert adonis_price_per_100g_edible(item, 0.9) == round(0.50 / 0.9, 3)


def test_falls_back_when_no_price_per_100g():
    # sans price_per_100g -> derivation existante (unit_price $/kg)
    item = {"unit_price": 4.0, "unit": "kg"}
    assert adonis_price_per_100g_edible(item, 1.0) == 0.40
