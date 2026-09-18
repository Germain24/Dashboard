"""Score relatif au benchmark : excédent de rendement moins l'EXCÈS de risque."""

import numpy as np
import pytest


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


def test_credit_nul_ne_donne_aucun_bonus():
    """NON-RÉGRESSION : à `credit=0` on retrouve exactement la forme unilatérale.

    C'est `max(0, ...)` qui empêchait le retour du biais obligataire. Le crédit
    est désormais réglable (`STARR_RISK_REDUCTION_CREDIT`) ; ce test fige le
    comportement d'origine, indépendamment de la valeur par défaut.
    """
    from app.services.finance.buffett.starr import benchmark_stats, neg_benchmark_relative
    sim, mean_daily, bench = _fixture()
    b = benchmark_stats(bench, 0.0005)
    score = -neg_benchmark_relative(
        np.array([0.0, 0.0, 1.0]), sim, mean_daily, b, credit=0.0
    )
    # rendement 4x plus faible, risque 4x plus faible -> seul le deficit compte
    expected = (0.000125 - 0.0005) * 252.0 * 100.0
    assert abs(score - expected) < 1e-6


def test_le_credit_est_puissant_et_doit_rester_petit():
    """Fige l'ordre de grandeur du crédit : il est bien plus fort qu'il n'y paraît.

    Le crédit vaut `credit × écart de risque ANNUALISÉ`, en points de %. Sur cet
    actif à un quart du risque du benchmark, un crédit de 0,3 rapporte ~9 points
    — davantage que le score total d'un portefeuille optimisé réel (~8 points).
    Il suffit donc à faire passer un actif à faible risque et faible rendement de
    « clairement moins bon » à « équivalent ». C'est exactement la pathologie de
    l'ETF monétaire que la forme soustractive avait corrigée : ce test existe
    pour qu'une hausse du crédit ne passe jamais inaperçue.
    """
    from app.services.finance.buffett.starr import benchmark_stats, neg_benchmark_relative
    sim, mean_daily, bench = _fixture()
    b = benchmark_stats(bench, 0.0005)
    w = np.array([0.0, 0.0, 1.0])
    sans = -neg_benchmark_relative(w, sim, mean_daily, b, credit=0.0)
    avec = -neg_benchmark_relative(w, sim, mean_daily, b, credit=0.3)

    assert avec > sans                      # être moins risqué rapporte enfin
    assert (avec - sans) > 5.0              # ... et beaucoup : ordre de grandeur
    # Le crédit est proportionnel : la moitié du coefficient, la moitié du gain.
    moitie = -neg_benchmark_relative(w, sim, mean_daily, b, credit=0.15)
    np.testing.assert_allclose(moitie - sans, (avec - sans) / 2.0, rtol=1e-9)


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


def test_benchmark_clone_with_many_flat_days_scores_zero_in_scalar_and_batch():
    from app.services.finance.buffett.starr import (
        benchmark_stats, neg_benchmark_relative, neg_benchmark_relative_batch,
    )

    returns = np.array([-0.20] + [0.0] * 99)
    sim = returns[:, None]
    means = np.array([0.001])
    bench = benchmark_stats(returns, means[0])
    assert neg_benchmark_relative(np.ones(1), sim, means, bench) == pytest.approx(0.0)
    assert neg_benchmark_relative_batch(np.ones((1, 1)), sim, means, bench)[0] == pytest.approx(0.0)


@pytest.mark.parametrize("invested", [0.0, 0.25, 1.0])
def test_actual_weights_keep_cash_uninvested_and_costs_on_total_capital(invested):
    from app.services.finance.buffett.starr import (
        benchmark_relative_batch_details, neg_benchmark_relative,
    )

    sim = np.array([-0.02] * 5 + [0.001] * 95)[:, None]
    means = np.array([0.001])
    bench = {"annual_return": 0.10, "cvar": 0.50, "downside_deviation": 0.20}
    weights = np.array([invested])
    kwargs = {"credit": 0.0, "normalize_weights": False}
    scalar = neg_benchmark_relative(
        weights, sim, means, bench, annual_cost=0.01, **kwargs
    )
    batch, context = benchmark_relative_batch_details(
        weights[:, None], sim, means, bench, annual_costs=0.01, **kwargs
    )

    expected = -(invested * 0.001 * 252 - 0.01 - 0.10) * 100
    assert scalar == pytest.approx(expected)
    assert batch[0] == pytest.approx(expected)
    assert context["weights"][0, 0] == pytest.approx(invested)
    np.testing.assert_allclose(context["portfolio_returns"], sim * invested)
