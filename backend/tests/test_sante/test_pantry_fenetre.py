from datetime import date

import pytest

from app.services.sante.pantry_fenetre import (
    _valid_grams,
    apply_pantry_deduction,
    load_pantry_grams,
    load_pantry_stock,
    pantry_stock_grams,
)


def test_load_pantry_grams_units():
    items = [{"ingredient": "Riz", "quantite": 1, "unite": "kg"},
             {"ingredient": "Oeufs", "quantite": 300, "unite": "g"},
             {"ingredient": "Riz", "quantite": 200, "unite": "g"}]
    g = load_pantry_grams(items)
    assert g["Riz"] == pytest.approx(1200.0)   # 1 kg + 200 g
    assert g["Oeufs"] == pytest.approx(300.0)


def test_deduction_partial_and_full():
    sl = [{"aliment": "Riz", "quantite_g": 900.0, "prix": 1.80, "promo": False},
          {"aliment": "Oeufs", "quantite_g": 200.0, "prix": 1.00, "promo": False}]
    out, cout = apply_pantry_deduction(sl, {"Riz": 200.0, "Oeufs": 500.0})
    riz = next(i for i in out if i["aliment"] == "Riz")
    assert riz["dispo_g"] == pytest.approx(200.0)
    assert riz["a_acheter_g"] == pytest.approx(700.0)
    assert riz["prix"] == pytest.approx(1.80 * 700 / 900)     # prorata
    assert all(i["aliment"] != "Oeufs" for i in out)          # tout en stock -> retiré
    assert cout == pytest.approx(1.80 * 700 / 900)


def test_no_pantry_keeps_list_and_sums_full_cost():
    sl = [{"aliment": "Riz", "quantite_g": 900.0, "prix": 1.80, "promo": False}]
    out, cout = apply_pantry_deduction(sl, {})
    assert out[0]["a_acheter_g"] == pytest.approx(900.0)
    assert cout == pytest.approx(1.80)


def test_liquids_and_tablets_use_documented_inventory_approximations():
    assert _valid_grams({"quantite": 2, "unite": "L", "ingredient": "Soupe"}) == 2000
    assert _valid_grams({"quantite": 2, "unite": "L", "ingredient": "Huile d'olive"}) == pytest.approx(1840)
    assert _valid_grams({"quantite": 89.6, "unite": "tablettes"}) == 90


def test_expired_stock_is_ignored_and_fresh_stock_gets_zero_cost_factor():
    items = [
        {"ingredient": "Tomate fraiche", "quantite": 500, "unite": "g", "rayon": "Fruits & légumes"},
        {"ingredient": "Tomate fraiche", "quantite": 200, "unite": "g", "rayon": "Autre"},
        {"ingredient": "Riz basmati", "quantite": 1, "unite": "kg", "rayon": "Épicerie sèche", "date_peremption": "2026-09-12"},
        {"ingredient": "Lait", "quantite": 1, "unite": "L", "rayon": "Produits laitiers", "date_peremption": "2026-09-12"},
        {"ingredient": "Sauce", "quantite": 1, "unite": "kg", "rayon": "Conserves", "date_peremption": "2026-09-16"},
    ]
    stock = load_pantry_stock(items, today=date(2026, 9, 13))
    assert stock["Tomate fraiche"] == [
        {"available_g": 500.0, "cost_factor": 0.0},
        {"available_g": 200.0, "cost_factor": 0.0},
    ]
    assert stock["Riz basmati"] == [{"available_g": 1000.0, "cost_factor": 0.5}]
    assert "Lait" not in stock
    assert stock["Sauce"][0]["cost_factor"] == 0.5  # best-before isn't a use-by date
    assert pantry_stock_grams(stock)["Sauce"] == 1000.0


def test_supplement_tablets_are_inventory_only_not_food_stock():
    items = [{
        "ingredient": "Multi Vitamin and mineral advanced", "quantite": 90,
        "unite": "tablettes", "rayon": "Autre", "type_aliment": "supplement",
    }, {
        "ingredient": "Complément sans classification", "quantite": 30,
        "unite": "tablettes", "rayon": "Compléments",
    }]
    assert load_pantry_stock(items, today=date(2026, 9, 13)) == {}
