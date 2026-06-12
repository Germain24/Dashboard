"""Tests TDD pour le module courses auto (#208)."""
import pytest
import json
import tempfile
from pathlib import Path


# ─── Fonctions pures ─────────────────────────────────────────────────────────

from app.services.automatisations.courses import (
    check_pantry_low_stock,
    items_below_threshold,
)


def _tmp_pantry(items: list[dict]) -> Path:
    f = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8")
    json.dump(items, f)
    f.close()
    return Path(f.name)


class TestItemsBelowThreshold:
    def test_item_below_seuil(self):
        items = [{"id": 1, "ingredient": "Riz", "quantite": 0.3, "unite": "kg", "seuil_min": 0.5}]
        result = items_below_threshold(items)
        assert len(result) == 1
        assert result[0]["ingredient"] == "Riz"

    def test_item_above_seuil_excluded(self):
        items = [{"id": 1, "ingredient": "Riz", "quantite": 1.0, "unite": "kg", "seuil_min": 0.5}]
        assert items_below_threshold(items) == []

    def test_no_seuil_excluded(self):
        items = [{"id": 1, "ingredient": "Sel", "quantite": 0.0, "unite": "g"}]
        assert items_below_threshold(items) == []

    def test_zero_quantity_with_seuil(self):
        items = [{"id": 1, "ingredient": "Lait", "quantite": 0.0, "unite": "L", "seuil_min": 0.5}]
        result = items_below_threshold(items)
        assert len(result) == 1

    def test_multiple_items(self):
        items = [
            {"id": 1, "ingredient": "Riz", "quantite": 0.2, "unite": "kg", "seuil_min": 0.5},
            {"id": 2, "ingredient": "Pates", "quantite": 0.8, "unite": "kg", "seuil_min": 0.5},
            {"id": 3, "ingredient": "Huile", "quantite": 0.1, "unite": "L", "seuil_min": 0.25},
        ]
        result = items_below_threshold(items)
        names = [r["ingredient"] for r in result]
        assert "Riz" in names
        assert "Huile" in names
        assert "Pates" not in names


class TestCheckPantryLowStock:
    def test_reads_from_path_and_returns_low_items(self):
        items = [
            {"id": 1, "ingredient": "Riz", "quantite": 0.1, "unite": "kg", "seuil_min": 0.5},
        ]
        path = _tmp_pantry(items)
        result = check_pantry_low_stock(path=path)
        assert len(result) == 1
        assert result[0]["ingredient"] == "Riz"

    def test_empty_pantry_returns_empty(self):
        path = _tmp_pantry([])
        assert check_pantry_low_stock(path=path) == []

    def test_missing_file_returns_empty(self):
        path = Path("/tmp/nonexistent_pantry_xyz.json")
        assert check_pantry_low_stock(path=path) == []


# ─── Intégration DB (notification) ───────────────────────────────────────────

import datetime as dt
from tests.conftest import mem_session  # noqa: F401
from app.services.automatisations.courses import run_courses_check
from app.models.scheduler import Notification
from sqlmodel import select


def test_run_courses_check_creates_notification(mem_session):
    items = [{"id": 1, "ingredient": "Riz", "quantite": 0.1, "unite": "kg", "seuil_min": 0.5}]
    path = _tmp_pantry(items)
    run_courses_check(mem_session, path=path)
    notifs = list(mem_session.exec(select(Notification)).all())
    assert any("Riz" in n.message or "Riz" in n.titre for n in notifs)


def test_run_courses_check_no_low_items_no_notification(mem_session):
    items = [{"id": 1, "ingredient": "Riz", "quantite": 2.0, "unite": "kg", "seuil_min": 0.5}]
    path = _tmp_pantry(items)
    run_courses_check(mem_session, path=path)
    notifs = list(mem_session.exec(select(Notification)).all())
    assert notifs == []
