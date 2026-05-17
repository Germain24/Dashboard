"""Tests du module intensity (modificateurs + défaut par date)."""

import datetime as dt

from app.services.sante.intensity import (
    INTENSITY_LEVELS,
    default_intensity_for_date,
    intensity_modifiers,
)


def test_intensity_levels_match_brief():
    assert INTENSITY_LEVELS == ("none", "low", "medium", "high")


def test_medium_matches_legacy_sport_day():
    """`medium` doit reproduire le comportement jour sport du legacy.

    Legacy : cals = (maintenance + 500) * 1.2, prot = poids * 2.2, lip = poids * 1.2
    """
    mods = intensity_modifiers("medium", surplus_kcal_sport=500.0, rest_factor=1.1)
    assert mods["activity_factor"] == 1.2
    assert mods["surplus_kcal"] == 500.0
    assert mods["protein_per_kg"] == 2.2
    assert mods["lipid_per_kg"] == 1.2


def test_none_matches_legacy_rest_day():
    """`none` = jour de repos legacy : cals = maintenance * 1.1."""
    mods = intensity_modifiers("none", surplus_kcal_sport=500.0, rest_factor=1.1)
    assert mods["activity_factor"] == 1.1
    assert mods["surplus_kcal"] == 0.0
    assert mods["protein_per_kg"] == 1.6
    assert mods["lipid_per_kg"] == 1.0


def test_high_is_more_aggressive_than_medium():
    high = intensity_modifiers("high")
    medium = intensity_modifiers("medium")
    assert high["surplus_kcal"] > medium["surplus_kcal"]
    assert high["protein_per_kg"] >= medium["protein_per_kg"]


def test_low_is_between_none_and_medium():
    low = intensity_modifiers("low")
    none = intensity_modifiers("none")
    medium = intensity_modifiers("medium")
    assert none["surplus_kcal"] < low["surplus_kcal"] < medium["surplus_kcal"]


def test_unknown_intensity_falls_back_to_none():
    mods = intensity_modifiers("garbage")
    assert mods["activity_factor"] == 1.1  # rest_factor default


def test_default_for_date_uses_germain_sport_days():
    """Germain s'entraîne lun, mar, mer, ven, sam (ISO 0,1,2,4,5)."""
    monday = dt.date(2026, 5, 18)   # ISO weekday 0
    assert monday.weekday() == 0
    assert default_intensity_for_date(monday) == "medium"

    thursday = dt.date(2026, 5, 21)  # ISO weekday 3
    assert thursday.weekday() == 3
    assert default_intensity_for_date(thursday) == "none"

    sunday = dt.date(2026, 5, 24)  # ISO weekday 6
    assert sunday.weekday() == 6
    assert default_intensity_for_date(sunday) == "none"


def test_default_with_custom_sport_days():
    monday = dt.date(2026, 5, 18)
    # Si l'utilisateur ne s'entraîne que le dimanche
    assert default_intensity_for_date(monday, sport_days=[6]) == "none"
    sunday = dt.date(2026, 5, 24)
    assert default_intensity_for_date(sunday, sport_days=[6]) == "medium"
