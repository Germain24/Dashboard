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


def test_shelf_stable_food_date_is_best_before_not_expired():
    assert classify_expiry("2026-06-06", "2026-06-07", "Épicerie sèche") == "best_before_passed"
    assert classify_expiry("2026-06-09", "2026-06-07", "Conserves") == "best_before_soon"


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


def test_dashboard_mutation_archives_existing_pantry_to_nas_first(monkeypatch, tmp_path):
    import app.services.backup_storage as backup_storage
    import app.services.cuisine.pantry as pantry

    target = tmp_path / "cuisine_pantry.json"
    target.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(pantry, "_pantry_path", lambda: target)
    archived = []

    def capture(source, **kwargs):
        archived.append((Path(source).read_text(encoding="utf-8"), kwargs))
        return tmp_path / kwargs["filename"]

    monkeypatch.setattr(backup_storage, "backup_file", capture)
    pantry.add_item("Riz", 500, "g")

    assert archived[0][0] == "[]"
    assert archived[0][1]["category"] == "cuisine/pantry"
    assert target.exists()


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


def test_api_patch_can_clear_expiry_date(monkeypatch):
    from app.api.cuisine import pantry as pantry_api
    from app.api.cuisine.schemas import PantryItemPatch

    captured = {}

    def update(item_id, patch):
        captured.update(patch)
        return {"id": item_id, **patch}

    monkeypatch.setattr(pantry_api.pantry_svc, "update_item", update)
    pantry_api.update_pantry_item(3, PantryItemPatch(date_peremption=None))

    assert captured == {"date_peremption": None}


def test_update_nonexistent(store):
    result = update_item(999, {"quantite": 5}, path=store)
    assert result is None


def test_remove_item(store):
    item = add_item("Oeufs", 6, "unité", path=store)
    assert remove_item(item["id"], path=store) is True
    assert list_items(path=store) == []


def test_remove_nonexistent(store):
    assert remove_item(999, path=store) is False
