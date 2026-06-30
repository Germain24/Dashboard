"""Répartition du budget par broker + seuil dust → cash (pas de 100 % forcé)."""

import numpy as np


def test_full_deployment_when_no_threshold():
    from app.services.finance.buffett.optimizer import split_budget_to_brokers
    w = np.array([0.5, 0.45, 0.05])
    access = np.array([[True], [True], [True]])
    W = split_budget_to_brokers(w, access, np.array([1.0]), min_position=0.0)
    assert abs(W[:, 0].sum() - 1.0) < 1e-9          # 100 % déployé


def test_dust_below_threshold_dropped_but_budget_redeployed():
    from app.services.finance.buffett.optimizer import split_budget_to_brokers
    w = np.array([0.5, 0.45, 0.005, 0.045])         # idx2 = dust (0,5 %)
    access = np.array([[True], [True], [True], [True]])
    W = split_budget_to_brokers(w, access, np.array([1.0]), min_position=0.01)
    assert W[2, 0] == 0.0                            # micro-ligne non achetée
    # son budget est redéployé sur les gardés -> déploiement intégral (l'argent reste investi)
    assert abs(W[:, 0].sum() - 1.0) < 1e-9


def test_uneven_availability_no_idle_budget():
    """Dispo inégale : chaque broker déploie quand même son budget (pas de bug 64 %)."""
    from app.services.finance.buffett.optimizer import split_budget_to_brokers
    w = np.array([0.4, 0.35, 0.25])
    # T0 seulement broker A, T1 seulement broker B, T2 les deux
    access = np.array([[True, False], [False, True], [True, True]])
    b_ratios = np.array([0.6, 0.4])
    W = split_budget_to_brokers(w, access, b_ratios, min_position=0.0)
    assert abs(W[:, 0].sum() - 0.6) < 1e-9
    assert abs(W[:, 1].sum() - 0.4) < 1e-9
