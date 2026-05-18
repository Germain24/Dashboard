"""Tests de la formule Epley + best_1rm_from_sets."""

from __future__ import annotations

import math

from app.services.entrainement.one_rm import best_1rm_from_sets, epley_1rm


def test_epley_1rep_returns_weight():
    assert epley_1rm(100, 1) == 100.0
    assert epley_1rm(60, 1) == 60.0


def test_epley_10_reps_at_100kg():
    """100 kg × 10 reps → 1RM ≈ 133.33 kg (formule Epley canonique)."""
    assert math.isclose(epley_1rm(100, 10), 133.333, rel_tol=1e-3)


def test_epley_zero_or_negative_returns_zero():
    assert epley_1rm(0, 5) == 0.0
    assert epley_1rm(-5, 5) == 0.0
    assert epley_1rm(50, 0) == 0.0


def test_epley_monotonic_in_weight():
    """À reps constantes, plus de poids → plus de 1RM."""
    assert epley_1rm(80, 5) < epley_1rm(100, 5) < epley_1rm(120, 5)


def test_epley_monotonic_in_reps():
    """À poids constant, plus de reps → plus de 1RM estimé (la formule
    suppose qu'on aurait pu pousser plus lourd sur 1 rep si on en fait 10)."""
    assert epley_1rm(100, 1) < epley_1rm(100, 5) < epley_1rm(100, 10)


def test_best_1rm_from_sets_picks_max():
    sets = [
        {"reps": 5, "poids_kg": 80},
        {"reps": 10, "poids_kg": 70},
        {"reps": 3, "poids_kg": 90},
    ]
    # Epley(80,5)≈93.3, Epley(70,10)≈93.3, Epley(90,3)≈99.0
    best = best_1rm_from_sets(sets)
    assert math.isclose(best, epley_1rm(90, 3))


def test_best_1rm_from_sets_handles_empty():
    assert best_1rm_from_sets([]) == 0.0


def test_best_1rm_from_sets_handles_nones():
    sets = [{"reps": None, "poids_kg": None}, {"reps": 5, "poids_kg": 80}]
    best = best_1rm_from_sets(sets)
    assert math.isclose(best, epley_1rm(80, 5))
