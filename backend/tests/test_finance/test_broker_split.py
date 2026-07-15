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


def test_shared_ticker_cantoned_zero_percent_on_other_broker():
    """Cantonnement : un titre partagé est acheté chez UN seul broker (0 % ailleurs)."""
    from app.services.finance.buffett.optimizer import split_budget_to_brokers
    w = np.array([0.5, 0.5])
    access = np.ones((2, 2), dtype=bool)                # les deux partagés
    b_ratios = np.array([0.5, 0.5])
    W = split_budget_to_brokers(w, access, b_ratios, min_position=0.01)
    for i in range(2):                                   # chaque titre sur un seul broker
        assert len(np.flatnonzero(W[i] > 0)) == 1
    assert abs(W[:, 0].sum() - 0.5) < 1e-9               # budgets intégralement déployés
    assert abs(W[:, 1].sum() - 0.5) < 1e-9


def test_overflow_redeployed_within_broker():
    """Poids cible > budget du broker affecté -> plafonné et redéployé DANS ce broker,
    jamais sur un 2e broker."""
    from app.services.finance.buffett.optimizer import split_budget_to_brokers
    w = np.array([0.3, 0.3, 0.4])
    # T0,T1 exclusifs broker A (budget 0.4, cible cumulée 0.6) ; T2 exclusif B.
    access = np.array([[True, False], [True, False], [False, True]])
    b_ratios = np.array([0.4, 0.6])
    W = split_budget_to_brokers(w, access, b_ratios, min_position=0.01)
    assert abs(W[:, 0].sum() - 0.4) < 1e-9               # budget A plein, pas de débord vers B
    assert W[0, 1] == 0.0 and W[1, 1] == 0.0            # T0,T1 jamais chez B
    assert abs(W[0, 0] - 0.2) < 1e-9                     # 0.4*0.3/0.6 : redéployé/dérive


def test_empty_broker_falls_back_no_idle_cash():
    """Broker sans titre affecté mais avec budget + titres dispo -> fallback
    équipondéré (seule entorse au strict, anti-cash-oisif)."""
    from app.services.finance.buffett.optimizer import split_budget_to_brokers
    w = np.array([0.6, 0.4])
    access = np.array([[True, True], [True, False]])     # T0 partagé, T1 exclusif A
    b_ratios = np.array([0.5, 0.5])
    W = split_budget_to_brokers(w, access, b_ratios, min_position=0.01)
    assert abs(W[:, 1].sum() - 0.5) < 1e-9               # broker B déploie quand même


def test_starved_broker_no_weighted_dispo_is_capped():
    """RÉGRESSION run 39 : candidat DE concentré sur 1 titre dispo SEULEMENT chez
    T212 -> le broker Bourso n'a AUCUN titre dispo >= seuil -> l'ancien dernier
    recours pulvérisait équipondéré sur TOUT son univers (~2000 lignes '1 action').
    Le fallback doit être plafonné à fallback_max_lines, en préférant les poids."""
    from app.services.finance.buffett.optimizer import split_budget_to_brokers
    n = 200
    w = np.zeros(n)
    w[0] = 1.0                                           # mono-titre (seed DE)
    access = np.ones((n, 2), dtype=bool)
    access[0, 1] = False                                 # T0 indispo chez broker 1
    b_ratios = np.array([0.5, 0.5])
    W = split_budget_to_brokers(w, access, b_ratios, min_position=0.01,
                                fallback_max_lines=20)
    lines_b1 = np.flatnonzero(W[:, 1] > 0)
    assert len(lines_b1) <= 20                           # PAS 199 lignes pulvérisées
    assert abs(W[:, 1].sum() - 0.5) < 1e-9               # budget déployé quand même


def test_starved_broker_many_weighted_dispo_also_capped():
    """Même un fallback sur des titres >= seuil est plafonné (top-poids d'abord)."""
    from app.services.finance.buffett.optimizer import split_budget_to_brokers
    # 30 titres >= seuil, tous dispo chez les 2 brokers, budgets très inégaux :
    # le cantonnement min-dérive les affecte TOUS au gros broker (remaining
    # 0.9 -> 0.3, toujours > 0.1) -> broker 1 affamé avec 30 dispo >= seuil.
    w = np.array([0.02] * 30)
    access = np.ones((30, 2), dtype=bool)
    b_ratios = np.array([0.9, 0.1])
    W = split_budget_to_brokers(w, access, b_ratios, min_position=0.01,
                                fallback_max_lines=20)
    lines_b1 = np.flatnonzero(W[:, 1] > 0)
    assert 0 < len(lines_b1) <= 20                       # plafonné, pas 30
    assert abs(W[:, 1].sum() - 0.1) < 1e-9


def test_starved_broker_does_not_spray_junk():
    """RÉGRESSION : un broker "affamé" par le cantonnement min-dérive (tous les bons
    titres cantonnés au gros broker) NE DOIT PAS pulvériser son budget en centaines
    de micro-lignes sur tout l'univers. Il déploie sur ses BONS titres disponibles
    (>= seuil), peu de lignes."""
    from app.services.finance.buffett.optimizer import split_budget_to_brokers
    # 3 bons titres (>=1%) dispo chez les 2 brokers + 50 "junk" (<1%) dispo chez les 2.
    # Budget très inégal -> min-dérive cantonne les 3 bons sur le broker 0, le broker 1
    # se retrouve sans titre affecté.
    w = np.array([0.2, 0.2, 0.2] + [0.008] * 50)
    access = np.ones((53, 2), dtype=bool)
    b_ratios = np.array([0.9, 0.1])
    W = split_budget_to_brokers(w, access, b_ratios, min_position=0.01)
    lines_b1 = np.flatnonzero(W[:, 1] > 0)
    assert len(lines_b1) <= 3                            # PAS 53 lignes junk pulvérisées
    assert set(lines_b1.tolist()) <= {0, 1, 2}          # uniquement les bons titres
    assert abs(W[:, 1].sum() - 0.1) < 1e-9               # budget déployé (pas de cash oisif)
