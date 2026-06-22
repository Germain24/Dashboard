"""Score de forme quotidien (type Garmin) : sommeil + sport + nutrition."""

from __future__ import annotations

from app.services.sante.score import (
    day_score,
    nutrition_score,
    sommeil_score,
    sport_score,
)


def test_sommeil_score_peaks_at_target():
    assert sommeil_score(8.0) == 100.0
    assert sommeil_score(6.0) == 75.0      # -2h → -25
    assert sommeil_score(None) is None


def test_nutrition_score_on_calorie_adherence():
    assert nutrition_score(2000, 2000) == 100.0
    assert nutrition_score(1500, 2000) == 75.0   # 25 % d'écart
    assert nutrition_score(1000, 2000) == 50.0   # 50 % d'écart
    assert nutrition_score(0, 2000) is None       # 0 kcal = rien loggé → pas de donnée
    assert nutrition_score(2000, None) is None


def test_sport_score_vs_weekly_target():
    assert sport_score(4) == 100.0     # 4 séances/sem = cible
    assert sport_score(2) == 50.0
    assert sport_score(8) == 100.0     # plafonné
    assert sport_score(None) is None


def test_day_score_averages_available_components():
    out = day_score(sommeil=100.0, sport=50.0, nutrition=None)
    assert out["score"] == 75.0                          # moyenne des dispo (100, 50)
    assert out["composantes"] == {"sommeil": 100.0, "sport": 50.0, "nutrition": None}


def test_day_score_none_when_no_data():
    out = day_score(sommeil=None, sport=None, nutrition=None)
    assert out["score"] is None
