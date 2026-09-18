"""Tests favoris + notes par recette — #128."""

from app.services.cuisine.recipe_meta import (
    get_favorites,
    toggle_favorite,
    get_note,
    set_note,
)


def test_favorites_empty(tmp_path):
    p = tmp_path / "meta.json"
    assert get_favorites(path=p) == {"favorites": []}


def test_toggle_favorite_add(tmp_path):
    p = tmp_path / "meta.json"
    result = toggle_favorite(1, path=p)
    assert result["is_favorite"] is True
    assert 1 in result["favorites"]


def test_toggle_favorite_remove(tmp_path):
    p = tmp_path / "meta.json"
    toggle_favorite(1, path=p)
    result = toggle_favorite(1, path=p)
    assert result["is_favorite"] is False
    assert 1 not in result["favorites"]


def test_toggle_multiple(tmp_path):
    p = tmp_path / "meta.json"
    toggle_favorite(1, path=p)
    toggle_favorite(3, path=p)
    result = get_favorites(path=p)
    assert set(result["favorites"]) == {1, 3}


def test_note_empty(tmp_path):
    p = tmp_path / "meta.json"
    assert get_note(99, path=p) == ""


def test_set_and_get_note(tmp_path):
    p = tmp_path / "meta.json"
    set_note(5, "Délicieux, moins de sel.", path=p)
    assert get_note(5, path=p) == "Délicieux, moins de sel."


def test_set_note_update(tmp_path):
    p = tmp_path / "meta.json"
    set_note(5, "Version 1", path=p)
    set_note(5, "Version 2", path=p)
    assert get_note(5, path=p) == "Version 2"


def test_note_persists_alongside_favorite(tmp_path):
    p = tmp_path / "meta.json"
    toggle_favorite(7, path=p)
    set_note(7, "Super recette", path=p)
    assert get_note(7, path=p) == "Super recette"
    assert 7 in get_favorites(path=p)["favorites"]
