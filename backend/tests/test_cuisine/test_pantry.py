"""Tests garde-manger (stock d'ingrédients + péremption) — #127."""

import json
from pathlib import Path

import pytest

from app.services.cuisine.pantry import (
    classify_expiry,
    list_items,
    add_item,
    update_item,
    remove_item,
)


# ── Fonctions pures ──────────────────────────────────────────────────────────

def test_classify_no_date():
    assert classify_expiry(None, "2026-06-07") == "no_date"


def test_classify_expired():
    assert classify_expiry("2026-06-06", "2026-06-07") == "expired"


def test_classify_warning_same_day():
    assert classify_expiry("2026-06-07", "2026-06-07") == "warning"


def test_classify_warning_within_3_days():
    assert classify_expiry("2026-06-09", "2026-06-07") == "warning"


def test_classify_ok():
    assert classify_expiry("2026-06-20", "2026-06-07") == "ok"


# ── Fonctions avec store JSON ────────────────────────────────────────────────

@pytest.fixture()
def store(tmp_path):
    return tmp_path / "pantry.json"


def test_list_empty(store):
    assert list_items(path=store) == []


def test_add_item(store):
    item = add_item("Lait", 1.0, "L", path=store)
    assert item["ingredient"] == "Lait"
    assert item["quantite"] == 1.0
    assert item["unite"] == "L"
    assert item["date_peremption"] is None
    assert item["rayon"] == "Autre"
    assert item["id"] >= 1


def test_add_item_with_expiry(store):
    item = add_item("Yaourt", 6, "unité", date_peremption="2026-06-10", rayon="Produits laitiers", path=store)
    assert item["date_peremption"] == "2026-06-10"
    assert item["rayon"] == "Produits laitiers"


def test_list_persists(store):
    add_item("Pain", 1, "unité", path=store)
    add_item("Beurre", 250, "g", path=store)
    items = list_items(path=store)
    assert len(items) == 2
    assert {i["ingredient"] for i in items} == {"Pain", "Beurre"}


def test_update_item(store):
    item = add_item("Lait", 1.0, "L", path=store)
    updated = update_item(item["id"], {"quantite": 2.0, "unite": "L"}, path=store)
    assert updated is not None
    assert updated["quantite"] == 2.0
    assert updated["ingredient"] == "Lait"


def test_update_nonexistent(store):
    result = update_item(999, {"quantite": 5}, path=store)
    assert result is None


def test_remove_item(store):
    item = add_item("Oeufs", 6, "unité", path=store)
    assert remove_item(item["id"], path=store) is True
    assert list_items(path=store) == []


def test_remove_nonexistent(store):
    assert remove_item(999, path=store) is False
