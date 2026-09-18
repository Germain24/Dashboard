"""L'objectif vectorisé doit rendre EXACTEMENT le même score que la formule
naïve (boucle par nutriment) dont il est issu.

L'objectif est évalué ~60 000 fois par génération de fenêtre (différences finies
SLSQP) : la version boucle-Python coûtait ~60 s par fenêtre, au-delà du timeout
client. La vectorisation est une accélération pure — toute divergence numérique
ici signifierait un changement des plans produits.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.services.sante.optimizer import (
    _MAX_CSV_COLS,
    CORE_MACRO_COLS,
    COVERAGE_COMPLETION_WEIGHT,
    COVERAGE_WEIGHT,
    DIVERSITY_EPS,
    DIVERSITY_WEIGHT,
    MACRO_TAIL_MULTIPLIER,
    USE_COVERAGE,
    build_objective,
    diversity_penalty,
)


def _naive_objective(
    x, nutrient_targets, nutrient_arrays, mult_by_col, body_weight,
    price_weight, prix_arr, taste_arr,
):
    """Formule d'origine, conservée comme référence de non-régression."""
    error = 0.0
    for csv_col, target_val, weight in nutrient_targets:
        current = float(np.dot(x, nutrient_arrays[csv_col]))
        eff_target = max(0.0, target_val)
        if eff_target == 0.0:
            if current > 0:
                error += weight * (current ** 2)
            continue
        rel_error = (current - eff_target) / eff_target
        if csv_col in _MAX_CSV_COLS:
            if current > target_val:
                error += weight * 5.0 * (rel_error ** 2)
        elif csv_col in CORE_MACRO_COLS or not USE_COVERAGE:
            error += weight * (
                rel_error ** 2 + MACRO_TAIL_MULTIPLIER * rel_error ** 4
            )
        else:
            distance = abs(rel_error)
            cov_w = COVERAGE_WEIGHT * mult_by_col.get(csv_col, 1.0)
            error += cov_w * (distance ** 2)
            error += (
                COVERAGE_COMPLETION_WEIGHT
                * mult_by_col.get(csv_col, 1.0)
                * distance
            )

    total_grams = float(np.sum(x)) * 100.0
    threshold_grams = body_weight * 0.05 * 1000.0
    if total_grams > threshold_grams and threshold_grams > 0:
        excess_ratio = (total_grams - threshold_grams) / threshold_grams
        error += 5000.0 * (excess_ratio ** 2)

    error += price_weight * float(np.dot(x, prix_arr))
    error += DIVERSITY_WEIGHT * diversity_penalty(x, DIVERSITY_EPS)
    error += float(np.dot(x, taste_arr))
    return error


def _fixture(rng, num_foods=40):
    """Jeu de nutriments couvrant les 4 branches : cible nulle, "max", macro, couverture."""
    nutrient_targets = [
        ("Energie", 2200.0, 1000.0),      # macro
        ("Proteines", 130.0, 1000.0),     # macro
        ("Lipides", 70.0, 100.0),         # macro
        ("Glucides", 260.0, 100.0),       # macro
        ("Sodium", 2300.0, 500.0),        # max
        ("TotalSugars", 50.0, 500.0),     # max
        ("Fibres", 30.0, 25.0),           # couverture
        ("VitD", 15.0, 25.0),             # couverture (multiplicateur dette)
        ("Calcium", 1000.0, 25.0),        # couverture
        ("Fer", 0.0, 25.0),               # cible nulle -> branche eff_target == 0
    ]
    nutrient_arrays = {c: rng.uniform(0.0, 50.0, num_foods) for c, _, _ in nutrient_targets}
    return nutrient_targets, nutrient_arrays


def test_objectif_vectorise_identique_a_la_formule_naive():
    rng = np.random.default_rng(7)
    num_foods = 40
    nutrient_targets, nutrient_arrays = _fixture(rng, num_foods)
    mult_by_col = {"VitD": 2.5}
    prix_arr = rng.uniform(0.1, 3.0, num_foods)
    taste_arr = rng.uniform(0.0, 0.5, num_foods)
    body_weight, price_weight = 60.0, 0.08

    vect = build_objective(
        nutrient_targets=nutrient_targets, nutrient_arrays=nutrient_arrays,
        mult_by_col=mult_by_col, body_weight=body_weight, price_weight=price_weight,
        prix_arr=prix_arr, taste_arr=taste_arr,
    )

    # x variés : nul, faible, réaliste, énorme (déclenche la pénalité de poids)
    for scale in (0.0, 0.01, 0.4, 4.0):
        for _ in range(15):
            x = rng.uniform(0.0, scale, num_foods)
            attendu = _naive_objective(
                x, nutrient_targets, nutrient_arrays, mult_by_col, body_weight,
                price_weight, prix_arr, taste_arr,
            )
            assert vect(x) == pytest.approx(attendu, rel=1e-12, abs=1e-9), (
                f"divergence à scale={scale}"
            )


def test_objectif_vectorise_gere_cible_nulle_et_depassement_max():
    """Cible nulle : toute consommation est pénalisée ; sous un "max" : aucune pénalité."""
    nutrient_targets = [("Fer", 0.0, 25.0), ("Sodium", 100.0, 500.0)]
    nutrient_arrays = {"Fer": np.array([10.0, 0.0]), "Sodium": np.array([0.0, 10.0])}
    zeros = np.zeros(2)
    obj = build_objective(
        nutrient_targets=nutrient_targets, nutrient_arrays=nutrient_arrays,
        mult_by_col={}, body_weight=60.0, price_weight=0.0,
        prix_arr=zeros, taste_arr=zeros,
    )
    # Sodium bien sous son max, Fer à 0 -> seule la pénalité de diversité subsiste.
    sous_max = obj(np.array([0.0, 1.0]))
    # Le Fer (cible 0) devient non nul -> pénalité quadratique franche en plus.
    avec_fer = obj(np.array([1.0, 1.0]))
    assert avec_fer > sous_max + 1000.0


def test_objectif_uses_proportional_economic_price_not_package_checkout():
    zeros = np.zeros(1)
    obj = build_objective(
        nutrient_targets=[], nutrient_arrays={}, mult_by_col={}, body_weight=60.0,
        price_weight=1.0, prix_arr=np.array([0.1]), taste_arr=zeros,
        package_price_arr=np.array([8.0]),
        package_units_arr=np.array([10.0]),  # paquet de 1 kg
    )
    # The plan comparison uses $0.10 per 100 g proportionally. The actual pack
    # checkout amount is handled separately against the stock deficit.
    assert obj(np.array([0.2])) == pytest.approx(
        0.2 * 0.1 + DIVERSITY_WEIGHT * (0.2 / (0.2 + DIVERSITY_EPS))
    )
