"""Tests du score de style + palette couleurs."""

from app.services.garderobe.style import (
    colors_compat,
    get_color_category,
    style_score,
)


def test_color_category_lookup_case_insensitive():
    assert get_color_category("Noir") == "Neutre"
    assert get_color_category("noir") == "Neutre"
    assert get_color_category("Bordeaux") == "Secondaire"
    assert get_color_category("Or") == "Accent"
    assert get_color_category(None) == "Accent"


def test_colors_compat_neutres_match_everything():
    assert colors_compat("Noir", "Or") is True
    assert colors_compat("Bleu marine", "Bordeaux") is True


def test_colors_compat_explicit_match():
    # Marron + Bleu ciel sont dans MATCHING_COLORS
    assert colors_compat("Marron", "Bleu ciel") is True


def test_style_score_zero_for_empty():
    assert style_score([]) == 0.0
    assert style_score([None]) == 0.0


def test_style_score_high_for_consistent_style():
    items = [
        {"style": ["Old Money"], "couleur": "Noir", "categorie": "Haut"},
        {"style": ["Old Money"], "couleur": "Bleu marine", "categorie": "Pantalon"},
    ]
    s = style_score(items)
    assert s > 60.0  # cohérence style 100%, ratio neutres bon, etc.


def test_style_score_lower_for_mixed_styles():
    items_consistent = [
        {"style": ["Old Money"], "couleur": "Bleu marine", "categorie": "Haut"},
        {"style": ["Old Money"], "couleur": "Bleu marine", "categorie": "Pantalon"},
    ]
    items_mixed = [
        {"style": ["Old Money"], "couleur": "Bleu marine", "categorie": "Haut"},
        {"style": ["Streetwear"], "couleur": "Orange", "categorie": "Pantalon"},
    ]
    assert style_score(items_consistent) > style_score(items_mixed)
