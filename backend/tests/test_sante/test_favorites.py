"""Favoris d'aliments (#64)."""

from __future__ import annotations

import pytest

from app.services.sante import favorites

CATALOG = ["Poulet", "Riz", "Brocoli"]


def test_add_and_list(tmp_path):
    p = tmp_path / "fav.json"
    favorites.add_favorite("Poulet", path=p, valid_names=CATALOG)
    favorites.add_favorite("Riz", path=p, valid_names=CATALOG)
    assert favorites.list_favorites(path=p, valid_names=CATALOG) == ["Poulet", "Riz"]


def test_add_idempotent(tmp_path):
    p = tmp_path / "fav.json"
    favorites.add_favorite("Riz", path=p, valid_names=CATALOG)
    favorites.add_favorite("Riz", path=p, valid_names=CATALOG)
    assert favorites.list_favorites(path=p, valid_names=CATALOG) == ["Riz"]


def test_add_unknown_rejected(tmp_path):
    with pytest.raises(ValueError):
        favorites.add_favorite("Licorne", path=tmp_path / "fav.json", valid_names=CATALOG)


def test_remove(tmp_path):
    p = tmp_path / "fav.json"
    favorites.add_favorite("Poulet", path=p, valid_names=CATALOG)
    favorites.add_favorite("Riz", path=p, valid_names=CATALOG)
    favorites.remove_favorite("Poulet", path=p, valid_names=CATALOG)
    assert favorites.list_favorites(path=p, valid_names=CATALOG) == ["Riz"]


def test_list_filters_out_catalog_absent(tmp_path):
    p = tmp_path / "fav.json"
    favorites.add_favorite("Riz", path=p, valid_names=CATALOG)
    # le catalogue change : Riz n'existe plus
    assert favorites.list_favorites(path=p, valid_names=["Poulet"]) == []
