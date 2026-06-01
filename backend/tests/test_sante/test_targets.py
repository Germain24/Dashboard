"""Tests des cibles journalières.

Garantit la rétrocompatibilité avec le legacy : pour `intensity="medium"` /
jour sport, les valeurs doivent matcher la formule (maintenance + 500) × 1.2.
"""

import datetime as dt

import pytest

from app.services.sante.targets import calculate_daily_targets


@pytest.fixture
def germain_weight():
    return 51.0


def test_targets_medium_matches_legacy_sport_day(germain_weight):
    base, comp = calculate_daily_targets(
        weight=germain_weight,
        date=dt.date(2026, 5, 18),  # lundi → medium par défaut
        intensity="medium",
    )
    maintenance = germain_weight * 32.0
    expected_cals = (maintenance + 500.0) * 1.2
    expected_prot = germain_weight * 2.2
    expected_lip = germain_weight * 1.2
    expected_gluc = (expected_cals - expected_prot * 4.0 - expected_lip * 9.0) / 4.0

    assert base["Calories"] == pytest.approx(expected_cals)
    assert base["Protéines"] == pytest.approx(expected_prot)
    assert base["Lipides"] == pytest.approx(expected_lip)
    assert base["Glucides"] == pytest.approx(expected_gluc)
    # Sans historique, comp == base
    assert comp == base


def test_targets_none_matches_legacy_rest_day(germain_weight):
    base, _ = calculate_daily_targets(
        weight=germain_weight,
        date=dt.date(2026, 5, 24),  # dimanche
        intensity="none",
    )
    maintenance = germain_weight * 32.0
    assert base["Calories"] == pytest.approx(maintenance * 1.1)
    assert base["Protéines"] == pytest.approx(germain_weight * 1.6)
    assert base["Lipides"] == pytest.approx(germain_weight * 1.0)


def test_targets_includes_micronutrients(germain_weight):
    base, _ = calculate_daily_targets(weight=germain_weight, date=dt.date(2026, 5, 18))
    # Quelques RDA piochés au hasard
    assert base["Fibres"] == 35.0
    assert base["Calcium"] == 1000.0
    assert base["VitC"] == 100.0
    assert base["Poids_Corps"] == germain_weight


def test_default_intensity_when_none_provided(germain_weight):
    """Si intensity=None, le défaut date-based s'applique."""
    base_monday, _ = calculate_daily_targets(
        weight=germain_weight,
        date=dt.date(2026, 5, 18),  # lundi → medium
        sport_days=[0, 1, 2, 4, 5],
    )
    base_thursday, _ = calculate_daily_targets(
        weight=germain_weight,
        date=dt.date(2026, 5, 21),  # jeudi → none
        sport_days=[0, 1, 2, 4, 5],
    )
    # Lundi (sport) doit avoir plus de calories que jeudi (repos)
    assert base_monday["Calories"] > base_thursday["Calories"]


def test_compensation_j_minus_1(germain_weight):
    """Si J-1 a sous-consommé, J doit avoir des targets plus hauts."""
    today = dt.date(2026, 5, 18)
    yesterday = today - dt.timedelta(days=1)
    # Hier on a visé 2500 kcal et consommé 2000 → gap 500
    history = [{
        "date": yesterday.isoformat(),
        "targets": {"Calories": 2500.0, "Protéines": 100.0, "Fibres": 35.0},
        "consumed": {"Calories": 2000.0, "Protéines": 80.0, "Fibres": 20.0},
    }]
    base, comp = calculate_daily_targets(
        weight=germain_weight, date=today, history=history, intensity="medium",
    )
    assert comp["Calories"] == pytest.approx(base["Calories"] + 500.0)
    assert comp["Protéines"] == pytest.approx(base["Protéines"] + 20.0)
    assert comp["Fibres"] == pytest.approx(base["Fibres"] + 15.0)


def test_compensation_ignores_excluded_keys(germain_weight):
    today = dt.date(2026, 5, 18)
    yesterday = today - dt.timedelta(days=1)
    history = [{
        "date": yesterday.isoformat(),
        "targets": {"Calories": 2500.0, "Prix_Max": 18.0, "Poids_Corps": 50.0},
        "consumed": {"Calories": 2500.0, "Prix_Max": 5.0, "Poids_Corps": 50.0},
    }]
    base, comp = calculate_daily_targets(
        weight=germain_weight, date=today, history=history, intensity="medium",
    )
    # Prix_Max et Poids_Corps ne doivent pas être affectés
    assert comp["Prix_Max"] == base["Prix_Max"]
    assert comp["Poids_Corps"] == base["Poids_Corps"]


def test_weekly_legacy_compensation_divided_by_7(germain_weight):
    """Cas legacy : targets > 10000 kcal = ancien système hebdo → gap /= 7."""
    today = dt.date(2026, 5, 18)
    yesterday = today - dt.timedelta(days=1)
    history = [{
        "date": yesterday.isoformat(),
        "targets": {"Calories": 17500.0, "Fibres": 245.0},  # hebdo
        "consumed": {"Calories": 14000.0, "Fibres": 175.0},  # gap 3500 et 70
    }]
    base, comp = calculate_daily_targets(
        weight=germain_weight, date=today, history=history, intensity="medium",
    )
    assert comp["Calories"] == pytest.approx(base["Calories"] + 3500.0 / 7.0)
    assert comp["Fibres"] == pytest.approx(base["Fibres"] + 70.0 / 7.0)


def test_custom_surplus_and_rest_factor(germain_weight):
    """Les paramètres du NutritionGoal sont bien pris en compte."""
    base, _ = calculate_daily_targets(
        weight=germain_weight,
        date=dt.date(2026, 5, 18),
        intensity="medium",
        surplus_kcal_sport=750.0,  # +50% vs défaut
    )
    maintenance = germain_weight * 32.0
    assert base["Calories"] == pytest.approx((maintenance + 750.0) * 1.2)
