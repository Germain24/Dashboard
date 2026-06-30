"""Plafond de poids par ACTION (ETF exemptés) + malus cardinalité."""

import numpy as np


def test_cap_only_stocks_etf_absorbs_excess():
    from app.services.finance.buffett.optimizer import cap_stock_weights
    w = np.array([0.5, 0.3, 0.2])
    is_etf = np.array([False, True, False])   # idx0/2 actions, idx1 ETF
    out = cap_stock_weights(w, is_etf, 0.15)
    assert out[0] <= 0.15 + 1e-9              # action plafonnée
    assert out[2] <= 0.15 + 1e-9
    assert out[1] > 0.30                       # l'ETF (non plafonné) absorbe l'excédent
    assert abs(out.sum() - 1.0) < 1e-9         # somme préservée


def test_etf_can_exceed_cap():
    from app.services.finance.buffett.optimizer import cap_stock_weights
    w = np.array([0.7, 0.3])
    is_etf = np.array([True, False])           # idx0 ETF, idx1 action
    out = cap_stock_weights(w, is_etf, 0.15)
    assert out[1] <= 0.15 + 1e-9              # l'action est plafonnée
    assert out[0] > 0.15                       # l'ETF peut dépasser le plafond
    assert abs(out.sum() - 1.0) < 1e-9


def test_cardinality_penalty_zero_below_threshold():
    from app.services.finance.buffett.optimizer import cardinality_penalty
    w = np.array([0.2] * 5)                     # 5 lignes <= max 20
    assert cardinality_penalty(w, max_lines=20, beta=0.15, threshold=0.01) == 0.0


def test_cardinality_penalty_grows_above_threshold():
    from app.services.finance.buffett.optimizer import cardinality_penalty
    w = np.array([0.04] * 25)                   # 25 lignes >= seuil -> excès 5
    p = cardinality_penalty(w, max_lines=20, beta=0.15, threshold=0.01)
    assert abs(p - (np.exp(0.15 * 5) - 1.0)) < 1e-9
    # micro-lignes sous le seuil ne comptent pas
    w2 = np.array([0.2] * 3 + [0.0001] * 30)
    assert cardinality_penalty(w2, 20, 0.15, 0.01) == 0.0


def test_per_broker_cardinality_counts_each_broker_separately():
    from app.services.finance.buffett.optimizer import per_broker_cardinality_penalty
    # 25 titres pondérés, tous dispos chez 2 brokers -> chaque broker a 25 lignes,
    # excès 5 chacun -> pénalité = 2 × (exp(0.15·5) − 1).
    w = np.array([0.04] * 25)
    access = np.ones((25, 2), dtype=bool)
    p = per_broker_cardinality_penalty(w, access, max_per_broker=20, beta=0.15, threshold=0.01)
    assert abs(p - 2.0 * (np.exp(0.15 * 5) - 1.0)) < 1e-9


def test_per_broker_cardinality_zero_under_cap():
    from app.services.finance.buffett.optimizer import per_broker_cardinality_penalty
    # 30 titres mais répartis : 15 dispos chez A seulement, 15 chez B seulement
    # -> 15 lignes par broker, sous le cap de 20 -> aucune pénalité.
    w = np.array([0.03] * 30)
    access = np.zeros((30, 2), dtype=bool)
    access[:15, 0] = True
    access[15:, 1] = True
    p = per_broker_cardinality_penalty(w, access, max_per_broker=20, beta=0.15, threshold=0.01)
    assert p == 0.0


def test_per_broker_cardinality_ignores_sub_threshold():
    from app.services.finance.buffett.optimizer import per_broker_cardinality_penalty
    w = np.array([0.2] * 3 + [0.0001] * 40)         # micro-lignes ignorées
    access = np.ones((43, 1), dtype=bool)
    assert per_broker_cardinality_penalty(w, access, 20, 0.15, 0.01) == 0.0
