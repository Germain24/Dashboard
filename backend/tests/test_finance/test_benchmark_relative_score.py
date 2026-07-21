"""Score relatif au benchmark : excédent de rendement moins l'EXCÈS de risque."""

import numpy as np


def _fixture():
    """3 actifs : 0 = clone du benchmark, 1 = plus risqué, 2 = moins risqué."""
    rng = np.random.default_rng(7)
    bench = rng.normal(0.0005, 0.01, 4000)
    sim = np.column_stack([bench, bench * 2.0, bench * 0.25])
    mean_daily = np.array([0.0005, 0.0010, 0.000125])
    return sim, mean_daily, bench


def test_portefeuille_identique_au_benchmark_score_zero():
    from app.services.finance.buffett.starr import benchmark_stats, neg_benchmark_relative
    sim, mean_daily, bench = _fixture()
    b = benchmark_stats(bench, 0.0005)
    score = -neg_benchmark_relative(np.array([1.0, 0.0, 0.0]), sim, mean_daily, b)
    assert abs(score) < 1e-6


def test_moins_risque_que_le_benchmark_ne_donne_aucun_bonus():
    """max(0, ...) : c'est ce qui empêche le retour du biais obligataire."""
    from app.services.finance.buffett.starr import benchmark_stats, neg_benchmark_relative
    sim, mean_daily, bench = _fixture()
    b = benchmark_stats(bench, 0.0005)
    score = -neg_benchmark_relative(np.array([0.0, 0.0, 1.0]), sim, mean_daily, b)
    # rendement 4x plus faible, risque 4x plus faible -> seul le deficit compte
    expected = (0.000125 - 0.0005) * 252.0 * 100.0
    assert abs(score - expected) < 1e-6


def test_exces_de_risque_est_soustrait_et_non_ajoute():
    """Garde-fou anti-inversion de signe : additionner l'excès récompenserait le risque."""
    from app.services.finance.buffett.starr import benchmark_stats, neg_benchmark_relative
    sim, mean_daily, bench = _fixture()
    b = benchmark_stats(bench, 0.0005)
    risque = -neg_benchmark_relative(np.array([0.0, 1.0, 0.0]), sim, mean_daily, b)
    exces_rendement = (0.0010 - 0.0005) * 252.0 * 100.0
    assert risque < exces_rendement    # l'exces de risque a bien ete retranche


def test_frais_reduisent_le_score():
    from app.services.finance.buffett.starr import benchmark_stats, neg_benchmark_relative
    sim, mean_daily, bench = _fixture()
    b = benchmark_stats(bench, 0.0005)
    w = np.array([1.0, 0.0, 0.0])
    sans = -neg_benchmark_relative(w, sim, mean_daily, b)
    avec = -neg_benchmark_relative(w, sim, mean_daily, b, annual_cost=0.01)
    assert abs((sans - avec) - 1.0) < 1e-6      # 1 % de frais = 1 point


def test_batch_coherent_avec_le_scalaire():
    from app.services.finance.buffett.starr import (
        benchmark_stats, neg_benchmark_relative, neg_benchmark_relative_batch,
    )
    sim, mean_daily, bench = _fixture()
    b = benchmark_stats(bench, 0.0005)
    W = np.array([[1.0, 0.0, 0.5], [0.0, 1.0, 0.5], [0.0, 0.0, 0.0]])
    lot = neg_benchmark_relative_batch(W, sim, mean_daily, b)
    for j in range(W.shape[1]):
        assert abs(lot[j] - neg_benchmark_relative(W[:, j], sim, mean_daily, b)) < 1e-6


def test_poids_nuls_renvoient_la_penalite_max():
    from app.services.finance.buffett.starr import benchmark_stats, neg_benchmark_relative
    sim, mean_daily, bench = _fixture()
    b = benchmark_stats(bench, 0.0005)
    assert neg_benchmark_relative(np.zeros(3), sim, mean_daily, b) == 1e6
