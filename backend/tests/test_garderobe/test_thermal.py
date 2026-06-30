"""Tests du calcul thermique : score d'un item, gap, cible."""

from app.services.garderobe.thermal import (
    calculate_thermal_gap,
    target_thermal,
    thermal_score,
)


def test_target_thermal_inversely_proportional_to_temp():
    # Quand il fait froid, la cible est élevée
    cold = target_thermal(-10)
    warm = target_thermal(25)
    assert cold > warm
    # Formule legacy : 50 - 1.5 × temp
    assert target_thermal(0) == 50.0
    assert target_thermal(20) == 20.0


def test_thermal_score_zero_for_no_temp_bounds():
    item = {"categorie": "Haut", "matiere": "Coton"}
    assert thermal_score(item) == 0.0


def test_thermal_score_zero_for_neutral_categories():
    # Lunettes, bijoux, montre, pendentif → 0
    for cat in ("Yeux", "Bijoux", "Poignet", "Cou"):
        item = {"categorie": cat, "temp_min": -10, "temp_max": 30, "matiere": "Cuir"}
        assert thermal_score(item) == 0.0


def test_thermal_score_higher_for_cold_items():
    cold = {"categorie": "Manteau", "matiere": "Laine", "temp_min": -10, "temp_max": 5}
    light = {"categorie": "Haut", "matiere": "Coton", "temp_min": 15, "temp_max": 30}
    assert thermal_score(cold) > thermal_score(light)


def test_thermal_score_chaleur_field_overrides():
    item = {"categorie": "Manteau", "matiere": "Coton", "chaleur": 7.7}
    assert thermal_score(item) == 7.7


def test_thermal_score_material_coefficient():
    # Même temp_min, matière différente → score différent
    base_args = {"categorie": "Manteau", "temp_min": 0, "temp_max": 10}
    laine = thermal_score({**base_args, "matiere": "Laine"})
    coton = thermal_score({**base_args, "matiere": "Coton"})
    # Laine (1.8) > Coton (1.0)
    assert laine > coton
    assert abs(laine / coton - 1.8) < 1e-6


def test_calculate_thermal_gap_basic():
    haut = {"categorie": "Haut", "matiere": "Coton", "temp_min": 15, "temp_max": 30}
    tenue = {"Haut": haut}
    total, target, gap = calculate_thermal_gap(tenue, mean_temp=15, use_body=False)
    assert target == target_thermal(15)
    assert gap == target - total


def test_calculate_thermal_gap_body_bonus():
    haut = {"categorie": "Haut", "matiere": "Coton", "temp_min": 15, "temp_max": 30}
    tenue = {"Haut": haut}
    without = calculate_thermal_gap(tenue, mean_temp=10, use_body=False)
    with_body = calculate_thermal_gap(tenue, mean_temp=10, use_body=True)
    # Le body ajoute exactement 1.5 au total thermique
    assert abs((with_body[0] - without[0]) - 1.5) < 1e-9


def test_thermal_score_temp_min_zero_not_treated_as_default():
    # Régression : temp_min=0 (manteau froid) ne doit PAS être traité comme 20
    # Le bug "or 20" transformait 0 (falsy) en 20, effaçant le score de 12.5 → 2.5
    coat_freezing = {"categorie": "Manteau", "matiere": "Coton", "temp_min": 0, "temp_max": 10}
    coat_mild = {"categorie": "Manteau", "matiere": "Coton", "temp_min": 20, "temp_max": 30}
    score_freezing = thermal_score(coat_freezing)
    score_mild = thermal_score(coat_mild)
    # temp_min=0 → base = (25-0)/2 = 12.5 ; temp_min=20 → base = (25-20)/2 = 2.5
    assert score_freezing > score_mild, (
        f"temp_min=0 doit scorer plus haut que temp_min=20, got {score_freezing} vs {score_mild}"
    )
    assert abs(score_freezing - 12.5) < 1e-9, f"Expected 12.5, got {score_freezing}"
    assert abs(score_mild - 2.5) < 1e-9, f"Expected 2.5, got {score_mild}"


def test_calculate_thermal_gap_layering_bonus():
    haut = {"categorie": "Haut", "matiere": "Coton", "temp_min": 15, "temp_max": 30}
    veste = {"categorie": "Veste", "matiere": "Coton", "temp_min": 10, "temp_max": 20}
    manteau = {"categorie": "Manteau", "matiere": "Laine", "temp_min": -10, "temp_max": 5}

    one_layer = calculate_thermal_gap({"Haut": haut}, mean_temp=0, use_body=False)
    two_layer = calculate_thermal_gap(
        {"Haut": haut, "Veste": veste}, mean_temp=0, use_body=False,
    )
    three_layer = calculate_thermal_gap(
        {"Haut": haut, "Veste": veste, "Manteau": manteau}, mean_temp=0, use_body=False,
    )

    # Sans bonus, la somme brute des couches devrait être < total avec bonus
    raw_two = thermal_score(haut) + thermal_score(veste)
    raw_three = thermal_score(haut) + thermal_score(veste) + thermal_score(manteau)

    # 2 couches → bonus de 10% sur la somme
    assert abs(two_layer[0] - raw_two * 1.10) < 1e-6
    # 3 couches → bonus de 20%
    assert abs(three_layer[0] - raw_three * 1.20) < 1e-6
    # Sanité : une seule couche = pas de bonus
    assert abs(one_layer[0] - thermal_score(haut)) < 1e-9
