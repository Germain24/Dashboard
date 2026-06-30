"""Contraintes look-through : pénalité défensif (≥) et pays (≤)."""

import numpy as np


def test_defensive_penalty_zero_when_satisfied():
    from app.services.finance.buffett.optimizer import constraint_penalty
    w = np.array([0.5, 0.5])
    d = np.array([1.0, 0.0])              # titre0 = 100% défensif -> portefeuille 50%
    assert constraint_penalty(w, d, None, 0.30, 0.25, 50) == 0.0   # 50% ≥ 30%


def test_defensive_penalty_quadratic_shortfall():
    from app.services.finance.buffett.optimizer import constraint_penalty
    w = np.array([0.5, 0.5])
    d = np.array([1.0, 0.0])              # défensif = 0.5 ; seuil 0.60 -> manque 0.10
    p = constraint_penalty(w, d, None, 0.60, 0.25, 50)
    assert abs(p - 50 * 0.10 ** 2) < 1e-9


def test_defensive_ignored_when_no_defensive_assets():
    from app.services.finance.buffett.optimizer import constraint_penalty
    w = np.array([0.6, 0.4])             # aucun actif défensif dispo -> contrainte infaisable
    assert constraint_penalty(w, np.zeros(2), None, 0.30, 0.25, 50) == 0.0


def test_country_penalty_over_cap():
    from app.services.finance.buffett.optimizer import constraint_penalty
    w = np.array([0.6, 0.4])
    C = np.array([[1.0], [1.0]])         # 100% pays0 chacun -> expo 1.0, cap 0.25 -> excès 0.75
    p = constraint_penalty(w, np.zeros(2), C, 0.30, 0.25, 50)
    assert abs(p - 50 * 0.75 ** 2) < 1e-9


def test_country_penalty_zero_when_under_cap():
    from app.services.finance.buffett.optimizer import constraint_penalty
    w = np.array([0.5, 0.5])
    # pays0: 0.5*0.2+0.5*0.2 = 0.20 < 0.25 ; pays1: idem -> 0 pénalité
    C = np.array([[0.2, 0.2], [0.2, 0.2]])
    assert constraint_penalty(w, np.zeros(2), C, 0.30, 0.25, 50) == 0.0
