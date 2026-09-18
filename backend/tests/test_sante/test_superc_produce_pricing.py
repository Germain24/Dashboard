"""TDD — re-tarification des fruits & légumes au prix Super C (Phase 2 « Super C
unique »). Le cache Super C est du même schéma Instacart qu'Adonis, donc
`build_price_overlay` / la conversion CAD/100 g comestible sont réutilisés tels
quels ; seul le chargement du cache change.
"""
from __future__ import annotations

import json as _json

import pandas as pd
import pytest

from app.services.sante import adonis_pricing


def test_apply_superc_produce_prices_overlays_from_superc_cache(monkeypatch):
    # Item schéma superc.ca (FR) : paquet 675 g à 6,29 $ -> 0,932 $/100 g.
    monkeypatch.setattr(adonis_pricing, "load_superc_cached_items", lambda: [
        {"name": "Brocoli", "price": 6.29, "format": "675 g", "unit_price": None, "unit": None},
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
    regular = [{"name": "Poitrine de poulet", "price": 12.0, "format": "1 kg"}]
    flyer = [{"name": "Brocoli", "price": 4.0, "format": "1 kg", "on_sale": True}]

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


def _patch_catalog_cache(monkeypatch):
    """Cache Super C minimal : un prix courant, un prix circulaire (déjà soldé)."""
    from app.services.cuisine import store_pricing
    regular = [{"name": "Poitrine de poulet", "price": 12.0, "format": "1 kg"}]
    flyer = [{"name": "Brocoli", "price": 4.0, "format": "1 kg", "on_sale": True}]
    monkeypatch.setattr(
        store_pricing, "load_cached_items",
        lambda store: regular if store == "superc" else flyer,
    )


def test_catalog_prices_apply_student_discount_on_shopping_day(monkeypatch):
    """Achat un mercredi (jour de courses de la fenêtre jeu-dim) : -10 % sur tout,
    y compris l'article DÉJÀ en circulaire (choix user : rabais sur le total)."""
    import datetime as dt

    import pandas as pd

    _patch_catalog_cache(monkeypatch)
    df = pd.DataFrame({"Prix": [1.50, 2.00]}, index=["Poitrine de poulet", "Brocoli"])
    out, _ = adonis_pricing.apply_superc_catalog_prices(df, dt.date(2026, 7, 22))
    assert out.loc["Poitrine de poulet", "Prix"] == pytest.approx(1.2 * 0.9)
    assert out.loc["Brocoli", "Prix"] == pytest.approx(0.4 * 0.9)


def test_catalog_prices_unchanged_when_bought_outside_discount_window(monkeypatch):
    import datetime as dt

    import pandas as pd

    _patch_catalog_cache(monkeypatch)
    df = pd.DataFrame({"Prix": [1.50, 2.00]}, index=["Poitrine de poulet", "Brocoli"])
    out, _ = adonis_pricing.apply_superc_catalog_prices(df, dt.date(2026, 7, 23))  # jeudi
    assert out.loc["Poitrine de poulet", "Prix"] == pytest.approx(1.2)


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
