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


# ---------------------------------------------------------------------------
# Affectation titre->broker (assign_tickers_to_brokers) : chaque titre pondéré
# va chez UN SEUL broker (cantonnement strict, heuristique min-dérive).
# ---------------------------------------------------------------------------

def test_assign_exclusive_ticker_forced_to_its_broker():
    from app.services.finance.buffett.optimizer import assign_tickers_to_brokers
    w = np.array([0.5, 0.5])
    access = np.array([[True, False], [False, True]])   # T0->A seul, T1->B seul
    b_ratios = np.array([0.5, 0.5])
    a = assign_tickers_to_brokers(w, access, b_ratios, min_position=0.01)
    assert a[0] == 0 and a[1] == 1


def test_assign_shared_ticker_goes_to_single_broker():
    from app.services.finance.buffett.optimizer import assign_tickers_to_brokers
    w = np.array([0.6, 0.4])
    access = np.ones((2, 2), dtype=bool)                # les deux partagés
    b_ratios = np.array([0.5, 0.5])
    a = assign_tickers_to_brokers(w, access, b_ratios, min_position=0.01)
    assert a[0] != a[1]                                  # un seul broker chacun, répartis
    assert set(a.tolist()) == {0, 1}


def test_assign_min_drift_fills_brokers_toward_budget():
    from app.services.finance.buffett.optimizer import assign_tickers_to_brokers
    w = np.array([0.3, 0.3, 0.3, 0.1])                   # tous partagés
    access = np.ones((4, 2), dtype=bool)
    b_ratios = np.array([0.7, 0.3])
    a = assign_tickers_to_brokers(w, access, b_ratios, min_position=0.01)
    w0, w1 = w[a == 0].sum(), w[a == 1].sum()
    assert w0 > w1                                       # le gros budget reçoit plus de poids
    assert abs(w0 - 0.7) < 1e-9 and abs(w1 - 0.3) < 1e-9


def test_assign_ignores_sub_threshold():
    from app.services.finance.buffett.optimizer import assign_tickers_to_brokers
    w = np.array([0.2, 0.2, 0.0001])
    access = np.ones((3, 1), dtype=bool)
    b_ratios = np.array([1.0])
    a = assign_tickers_to_brokers(w, access, b_ratios, min_position=0.01)
    assert a[2] == -1                                    # micro-ligne non affectée
    assert a[0] == 0 and a[1] == 0


# ---------------------------------------------------------------------------
# Malus de cardinalité sur les lignes RÉELLEMENT déployées (0 % compte 0).
# ---------------------------------------------------------------------------

def test_per_broker_shared_tickers_not_double_counted():
    from app.services.finance.buffett.optimizer import per_broker_cardinality_penalty
    # 25 titres partagés sur 2 brokers de budget égal -> affectés strictement
    # (~13/12 par broker) -> sous le cap 20 -> plus de double comptage -> malus 0.
    w = np.array([0.04] * 25)
    access = np.ones((25, 2), dtype=bool)
    b_ratios = np.array([0.5, 0.5])
    p = per_broker_cardinality_penalty(w, access, b_ratios, max_per_broker=20,
                                       beta=0.15, threshold=0.01)
    assert p == 0.0


def test_per_broker_fires_when_a_broker_exceeds_cap():
    from app.services.finance.buffett.optimizer import per_broker_cardinality_penalty
    # 25 titres EXCLUSIFS au broker A -> 25 lignes forcées chez A -> excès 5.
    w = np.array([0.04] * 25)
    access = np.zeros((25, 2), dtype=bool)
    access[:, 0] = True
    b_ratios = np.array([0.5, 0.5])
    p = per_broker_cardinality_penalty(w, access, b_ratios, max_per_broker=20,
                                       beta=0.15, threshold=0.01)
    assert abs(p - (np.exp(0.15 * 5) - 1.0)) < 1e-9


def test_per_broker_zero_under_cap():
    from app.services.finance.buffett.optimizer import per_broker_cardinality_penalty
    # 15 exclusifs A + 15 exclusifs B -> 15 lignes par broker, sous le cap.
    w = np.array([1.0 / 30] * 30)
    access = np.zeros((30, 2), dtype=bool)
    access[:15, 0] = True
    access[15:, 1] = True
    b_ratios = np.array([0.5, 0.5])
    p = per_broker_cardinality_penalty(w, access, b_ratios, 20, 0.15, 0.01)
    assert p == 0.0


def test_per_broker_ignores_sub_threshold():
    from app.services.finance.buffett.optimizer import per_broker_cardinality_penalty
    w = np.array([0.2] * 3 + [0.0001] * 40)         # micro-lignes ignorées
    access = np.ones((43, 1), dtype=bool)
    b_ratios = np.array([1.0])
    assert per_broker_cardinality_penalty(w, access, b_ratios, 20, 0.15, 0.01) == 0.0
