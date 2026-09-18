"""Filtres saison/couleur/occasion (#78)."""

from __future__ import annotations

from app.services.garderobe.filters import matches_filters, season_of


def test_season_classification():
    assert season_of(-10, 5) == "hiver"
    assert season_of(10, 20) == "mi-saison"
    assert season_of(18, 30) == "été"
    assert season_of(None, None) == "toutes"


def test_filter_couleur_insensitive():
    item = {"couleur": "Bleu Marine"}
    assert matches_filters(item, couleur="bleu marine")
    assert not matches_filters(item, couleur="Noir")


def test_filter_saison_overlap_toutes_passes():
    item = {"temp_min": None, "temp_max": None}
    assert matches_filters(item, saison="hiver")  # "toutes" passe partout


def test_filter_saison_mismatch():
    item = {"temp_min": 18, "temp_max": 30}  # été
    assert matches_filters(item, saison="été")
    assert not matches_filters(item, saison="hiver")


def test_filter_occasion_from_style_and_extra():
    assert matches_filters({"style": ["Casual", "Sport"]}, occasion="sport")
    assert matches_filters({"extra": {"occasion": "Mariage"}}, occasion="mariage")
    assert not matches_filters({"style": ["Casual"]}, occasion="formel")


def test_combined_filters():
    item = {"couleur": "Noir", "temp_min": -5, "temp_max": 8, "style": ["Formel"]}
    assert matches_filters(item, couleur="noir", saison="hiver", occasion="formel")
    assert not matches_filters(item, couleur="noir", saison="été", occasion="formel")
