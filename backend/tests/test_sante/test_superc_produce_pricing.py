"""TDD — re-tarification des fruits & légumes au prix Super C (Phase 2 « Super C
unique »). Le cache Super C est du même schéma Instacart qu'Adonis, donc
`build_price_overlay` / la conversion CAD/100 g comestible sont réutilisés tels
quels ; seul le chargement du cache change.
"""
from __future__ import annotations

import json as _json

import pandas as pd

from app.services.sante import adonis_pricing


def test_apply_superc_produce_prices_overlays_from_superc_cache(monkeypatch):
    # Item schéma Instacart Super C : paquet 675 g à 6,29 $ -> 0,932 $/100 g.
    monkeypatch.setattr(adonis_pricing, "load_superc_cached_items", lambda: [
        {"name": "Broccoli", "price": 6.29, "format": "675 g", "unit_price": None, "unit": None},
    ])
    df = pd.DataFrame({"Prix": [2.0, 1.76]}, index=["Brocoli", "Poitrine de poulet"])
    out, changed = adonis_pricing.apply_superc_produce_prices(df)
    assert out.loc["Brocoli", "Prix"] == 0.932
    assert out.loc["Poitrine de poulet", "Prix"] == 1.76   # non produce -> inchangé
    assert changed == ["Brocoli"]


def test_apply_superc_produce_prices_neutral_when_cache_empty(monkeypatch):
    monkeypatch.setattr(adonis_pricing, "load_superc_cached_items", lambda: [])
    df = pd.DataFrame({"Prix": [2.0]}, index=["Brocoli"])
    out, changed = adonis_pricing.apply_superc_produce_prices(df)
    assert out.loc["Brocoli", "Prix"] == 2.0
    assert changed == []


def test_apply_superc_produce_prices_disabled_by_env(monkeypatch):
    monkeypatch.setenv("SUPERC_PRODUCE_PRICING", "0")
    monkeypatch.setattr(adonis_pricing, "load_superc_cached_items", lambda: [
        {"name": "Broccoli", "price": 6.29, "format": "675 g"},
    ])
    df = pd.DataFrame({"Prix": [2.0]}, index=["Brocoli"])
    out, changed = adonis_pricing.apply_superc_produce_prices(df)
    assert out.loc["Brocoli", "Prix"] == 2.0
    assert changed == []


def test_catalog_prices_include_regular_and_flyer(monkeypatch):
    import pandas as pd

    df = pd.DataFrame({"Prix": [1.50, 2.00]}, index=["Poitrine de poulet", "Brocoli"])
    regular = [{"name": "Chicken Breast", "price": 12.0, "format": "1 kg"}]
    flyer = [{"name": "Broccoli", "price": 4.0, "format": "1 kg", "on_sale": True}]

    from app.services.cuisine import store_pricing
    monkeypatch.setattr(
        store_pricing,
        "load_cached_items",
        lambda store: regular if store == "superc" else flyer,
    )
    out, changed = adonis_pricing.apply_superc_catalog_prices(df)
    assert out.loc["Poitrine de poulet", "Prix"] == 1.2
    assert out.loc["Brocoli", "Prix"] == 0.4
    assert set(changed) == {"Poitrine de poulet", "Brocoli"}


def test_load_superc_cached_items_reads_cache_file(monkeypatch, tmp_path):
    cuisine = tmp_path / "Cuisine"
    cuisine.mkdir(parents=True)
    (cuisine / "superc.json").write_text(
        _json.dumps({"items": [{"name": "Banana", "price": 1.0}]}), encoding="utf-8"
    )

    class _FakeSettings:
        imports_dir = tmp_path

    monkeypatch.setattr(adonis_pricing, "settings", _FakeSettings())
    assert adonis_pricing.load_superc_cached_items() == [{"name": "Banana", "price": 1.0}]
