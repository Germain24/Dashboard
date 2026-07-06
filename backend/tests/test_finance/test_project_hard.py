"""Projection dure des contraintes look-through (défensif ≥, pays ≤, plafond action)."""

import numpy as np


def test_defensive_floor_enforced_exactly_when_feasible():
    from app.services.finance.buffett.optimizer import project_lookthrough_hard
    # DE renvoie 10% défensif (ETF défensif = titre2), plancher exigé 30% -> faisable
    # car titre2 est un ETF (non plafonné).
    w0 = np.array([0.6, 0.3, 0.1])
    d = np.array([0.0, 0.0, 1.0])
    is_etf = np.array([True, True, True])
    w = project_lookthrough_hard(w0, d, None, 0.30, 0.25, is_etf, 0.15)
    assert w @ d >= 0.30 - 1e-6
    assert abs(w.sum() - 1.0) < 1e-9


def test_country_cap_enforced_exactly_when_feasible():
    from app.services.finance.buffett.optimizer import project_lookthrough_hard
    # Titres 0 et 2 = 100% pays A (dominant), titre1 = pays B -> rediversification requise.
    w0 = np.array([0.6, 0.1, 0.3])
    C = np.array([[1.0], [0.0], [1.0]])
    is_etf = np.array([True, True, True])
    w = project_lookthrough_hard(w0, None, C, 0.30, 0.25, is_etf, 0.15)
    assert (w @ C[:, 0]) <= 0.25 + 1e-6
    assert abs(w.sum() - 1.0) < 1e-9


def test_per_stock_cap_still_respected():
    from app.services.finance.buffett.optimizer import project_lookthrough_hard
    w0 = np.array([0.7, 0.3])
    is_etf = np.array([False, True])   # idx0 action plafonnée, idx1 ETF
    w = project_lookthrough_hard(w0, None, None, 0.30, 0.25, is_etf, 0.15)
    assert w[0] <= 0.15 + 1e-9
    assert abs(w.sum() - 1.0) < 1e-9


def test_falls_back_gracefully_when_genuinely_infeasible():
    from app.services.finance.buffett.optimizer import project_lookthrough_hard
    # Seul titre défensif dispo est une ACTION plafonnée à 15% : impossible
    # d'atteindre le plancher de 30% en respectant ce plafond -> repli sans
    # casser le reste (comportement identique à l'ancien code : contrainte
    # infaisable -> ignorée).
    w0 = np.array([0.6, 0.3, 0.1])
    d = np.array([0.0, 0.0, 1.0])
    is_etf = np.array([True, True, False])
    w = project_lookthrough_hard(w0, d, None, 0.30, 0.25, is_etf, 0.15)
    assert w[2] <= 0.15 + 1e-9
    assert abs(w.sum() - 1.0) < 1e-9


def test_no_lookthrough_data_falls_back_to_cap_only():
    from app.services.finance.buffett.optimizer import project_lookthrough_hard
    w0 = np.array([0.5, 0.3, 0.2])
    is_etf = np.array([False, True, False])
    w = project_lookthrough_hard(w0, np.zeros(3), None, 0.30, 0.25, is_etf, 0.15)
    assert w[0] <= 0.15 + 1e-9
    assert w[2] <= 0.15 + 1e-9
    assert abs(w.sum() - 1.0) < 1e-9
