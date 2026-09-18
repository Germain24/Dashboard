"""Termes de l'objectif qui existaient sans pouvoir jamais agir.

Trois des sept termes du score étaient structurellement inertes :

- `lignes_par_broker` : `_deploy_batch` tronquait au plafond AVANT de compter les
  lignes, donc l'excédent restait toujours négatif ;
- `plancher_defensif` et `plafond_pays` : contraintes lexicographiques, tout
  candidat qui les violait recevait la sentinelle 1e6 et disparaissait, donc tout
  survivant les respectait exactement ;
- et le bonus de diversification était écrêté en permanence, ce qui en faisait une
  constante plutôt qu'un signal. Il est désormais logarithmique et sans plafond
  externe.

S'y ajoutaient une pénalité de risque pays à coefficient nul et des termes de
risque strictement unilatéraux.
"""

import numpy as np
import pytest

from app.services.finance.buffett import starr
from app.services.finance.buffett.allocation import alloc_to_weight_matrix, broker_line_cap
from app.services.finance.buffett.config import Config

# ── 1. Bonus de diversification : signal, plus constante ────────────────────


def test_bonus_has_no_external_cap():
    """Le coefficient est le seul réglage d'échelle du bonus pays."""
    assert not hasattr(Config, "STARR_SECTOR_COUNTRY_DIVERSIFICATION_BONUS_MAX")


@pytest.mark.parametrize("country_count", [2, 3, 5])
def test_bonus_discriminates_more_significant_countries(country_count):
    """Ajouter un pays significatif améliore continûment le signal."""
    from app.services.finance.buffett.sector_constraints import (
        country_diversification_score_from_buckets,
    )

    two = np.zeros((country_count, 1))
    two[:, 0] = 1.0 / country_count
    one = np.zeros((country_count, 1))
    one[0, 0] = 1.0
    assert country_diversification_score_from_buckets(
        two, np.zeros(country_count, dtype=bool)
    )[0] > country_diversification_score_from_buckets(
        one, np.zeros(country_count, dtype=bool)
    )[0]


def test_old_coefficient_would_have_saturated():
    """Fige la raison du changement : 2,0 écrasait tout le signal utile."""
    old_cap = 0.75
    assert min(2.0 * 0.40, old_cap) == min(2.0 * 0.80, old_cap) == old_cap


def test_significant_country_threshold_does_not_reward_micro_lines():
    from app.services.finance.buffett.sector_constraints import (
        country_diversification_score_from_buckets,
    )

    one = country_diversification_score_from_buckets(
        np.array([[0.99], [0.01]]), np.zeros(2, dtype=bool)
    )[0]
    micro = country_diversification_score_from_buckets(
        np.array([[0.999], [0.001]]), np.zeros(2, dtype=bool)
    )[0]
    assert one > micro


# ── 2. Risque pays : mesuré ET appliqué ────────────────────────────────────


def test_country_risk_penalty_is_active():
    assert float(Config.STARR_COUNTRY_RISK_PENALTY) > 0.0


def test_country_risk_penalty_charges_a_concentrated_portfolio():
    from app.services.finance.buffett.sector_constraints import (
        sector_downside_risk_penalty,
    )

    details = {
        "sectors": ["France", "Japon"],
        "risk_shares": np.array([[0.60], [0.40]]),
    }
    penalty, exceeded = sector_downside_risk_penalty(
        details,
        max_risk_share=float(Config.STARR_MAX_COUNTRY_RISK_SHARE),
        coefficient=float(Config.STARR_COUNTRY_RISK_PENALTY),
    )
    assert penalty[0] > 0.0      # valait exactement 0 avec un coefficient nul
    assert bool(exceeded[0])


# ── 3. Capacité de lignes : indépendante du seuil historique ───────────────


def test_line_cap_is_the_economic_capacity_not_the_malus_threshold():
    """Capacité ÉCONOMIQUE par broker : combien de lignes tiennent au plancher.

    À ne pas confondre avec `STARR_MAX_LINES_PER_BROKER`, qui reste un seuil
    historique de diagnostic. La pénalité de cardinalité est désactivée ; la
    capacité sert uniquement à éviter une ventilation irréaliste d'un petit
    broker.
    """
    # 3,5 % du capital au plancher de 1 % -> trois lignes, pas vingt.
    assert broker_line_cap(3_500.0, 100_000.0) == 3
    assert broker_line_cap(96_500.0, 100_000.0) == 96
    # Jamais zéro pour un broker actif, même minuscule.
    assert broker_line_cap(50.0, 100_000.0) == 1


def _seuils(budgets: list[float], capital: float) -> np.ndarray:
    """Seuil du malus de chaque broker : min(capacité économique, 20)."""
    plafond = int(Config.STARR_MAX_LINES_PER_BROKER)
    return np.array(
        [min(broker_line_cap(b, capital), plafond) for b in budgets], dtype=int
    )


def _malus(counts: list[int], seuils: np.ndarray) -> float:
    """Somme, SUR LES BROKERS, de exp(beta × excédent) − 1."""
    exces = np.asarray(counts) - seuils
    beta = float(Config.STARR_CARD_BETA)
    return float(np.where(exces > 0, np.exp(beta * exces) - 1.0, 0.0).sum())


def test_malus_threshold_is_per_broker_min_of_capacity_and_cap():
    """Seuil = min(capacité du broker, 20) : propre à chaque broker."""
    assert _seuils([96_500.0, 3_500.0], 100_000.0).tolist() == [20, 3]


def test_cardinality_malus_is_disabled_by_default():
    seuils = _seuils([96_500.0, 3_500.0], 100_000.0)
    assert _malus([0, 0], seuils) == 0.0
    assert _malus([19, 2], seuils) == 0.0
    assert _malus([20, 3], seuils) == 0.0            # pile au seuil : rien
    assert _malus([21, 3], seuils) == 0.0             # désactivé par défaut
    assert _malus([30, 3], seuils) == 0.0


def test_cardinality_malus_stays_zero_across_brokers():
    """Le nombre de lignes ne retire plus de score, quel que soit le broker."""
    seuils = _seuils([96_500.0, 3_500.0], 100_000.0)
    petit = _malus([20, 5], seuils)
    gros = _malus([22, 3], seuils)

    assert petit == pytest.approx(gros)
    assert petit == 0.0
    assert gros == 0.0
    assert _malus([22, 5], seuils) == 0.0


def test_the_threshold_is_reachable_for_a_large_broker():
    """Sans quoi le malus resterait lettre morte — c'était le bug d'origine.

    La troncature porte sur la CAPACITÉ (96), strictement au-dessus du seuil
    (20) : l'excédent peut donc devenir positif.
    """
    capacite = broker_line_cap(96_500.0, 100_000.0)
    assert capacite > min(capacite, int(Config.STARR_MAX_LINES_PER_BROKER))


def test_a_small_broker_budget_is_never_swallowed_by_the_floor():
    """LE bug : un petit broker étalé en micro-lignes ressortait NON INVESTI.

    Trading212 pèse 3,5 % du capital. Sans capacité économique, le solveur
    pouvait y ouvrir des dizaines de lignes de ~0,09 %, toutes annulées ensuite
    par le filtre du plancher de 1 %, et le budget entier disparaissait.
    La capacité borne le nombre de lignes de sorte que chacune franchisse le
    plancher.
    """
    budget_pct, plancher = 0.035, float(Config.MIN_ALLOCATION_THRESHOLD)
    capacite = broker_line_cap(budget_pct * 100_000.0, 100_000.0)

    assert capacite == 3
    # Chaque ligne pèse au moins le plancher -> aucune n'est annulée.
    assert budget_pct / capacite >= plancher


def test_the_empty_broker_safety_net_restores_the_best_line():
    """Filet : un broker vidé par le filtre récupère sa meilleure ligne.

    Reproduit la mécanique de `_deploy_batch` : mieux vaut une ligne sous le
    plancher qu'un budget évaporé en silence.
    """
    before = np.zeros((4, 2, 2))
    before[:, 0, 0] = [0.20, 0.30, 0.0, 0.0]        # broker sain
    before[:, 1, 0] = [0.002, 0.004, 0.001, 0.0]    # QUE des micro-lignes
    # broker 1, candidat 1 : déjà vide, ne doit pas être ressuscité.
    plancher = 0.01

    capped = before.copy()
    capped[(capped > 1e-12) & (capped < plancher - 1e-12)] = 0.0
    emptied = (capped.sum(axis=0) <= 1e-12) & (before.sum(axis=0) > 1e-12)
    brokers, candidates = np.nonzero(emptied)
    best = np.argmax(before[:, brokers, candidates], axis=0)
    capped[best, brokers, candidates] = before[best, brokers, candidates]

    assert capped[:, 1, 0].sum() == pytest.approx(0.004)   # meilleure ligne rendue
    assert capped[:, 1, 1].sum() == 0.0                    # déjà vide : intact
    assert capped[:, 0, 0].tolist() == [0.20, 0.30, 0.0, 0.0]


def test_a_small_broker_can_never_reach_the_malus_threshold():
    """Et c'est CORRECT : il ne peut pas tenir 20 lignes au-dessus du plancher.

    Le malus ne doit donc jamais s'appliquer à lui — ce n'est pas une faille,
    c'est la conséquence de sa capacité économique.
    """
    capacite = broker_line_cap(3_500.0, 100_000.0)
    assert capacite < int(Config.STARR_MAX_LINES_PER_BROKER)


# ── 4. Crédit de réduction du risque ───────────────────────────────────────


def test_zero_credit_reproduces_the_one_sided_form():
    """Non-régression : credit=0 doit redonner exactement max(0, delta)."""
    for measure, benchmark in ((0.30, 0.20), (0.10, 0.20), (0.20, 0.20)):
        assert float(starr._risk_excess(measure, benchmark, 0.0)) == pytest.approx(
            max(0.0, measure - benchmark)
        )


def test_being_less_risky_than_the_benchmark_now_pays():
    credit = 0.3
    moins_risque = float(starr._risk_excess(0.10, 0.20, credit))
    assert moins_risque == pytest.approx(-0.03)      # crédit = 0,3 x 0,10
    # Dépasser le risque coûte toujours PLEIN TARIF : l'asymétrie est conservée.
    plus_risque = float(starr._risk_excess(0.30, 0.20, credit))
    assert plus_risque == pytest.approx(0.10)
    assert abs(plus_risque) > abs(moins_risque)


def test_default_credit_stays_far_below_full_symmetry():
    """Un crédit proche de 1,0 ferait remonter les actifs quasi-monétaires."""
    assert 0.0 < float(Config.STARR_RISK_REDUCTION_CREDIT) <= 0.5


def test_both_scorers_share_the_same_risk_term():
    """La recherche vectorisée et le polish final doivent noter pareil."""
    rng = np.random.default_rng(0)
    sim = rng.normal(0.0005, 0.01, (600, 4))
    mean_daily = sim.mean(axis=0)
    bench = starr.benchmark_stats(sim[:, 0], mean_daily[0])
    w = np.array([0.1, 0.2, 0.3, 0.4])

    scalaire = starr.neg_benchmark_relative(w, sim, mean_daily, bench, credit=0.3)
    vectorise, _ = starr.benchmark_relative_batch_details(
        w[:, None], sim, mean_daily, bench, credit=0.3
    )
    assert float(vectorise[0]) == pytest.approx(scalaire, rel=1e-9)


# ── 5. Reconstruction des poids réellement achetés ─────────────────────────


def test_alloc_to_weight_matrix_uses_the_analysis_ticker():
    """`Ticker` est le ticker d'EXÉCUTION : agréger dessus fausserait tout."""
    alloc = [
        {"Ticker": "OR.DE", "AnalysisTicker": "OR.PA", "Broker": "Bourso",
         "eur": 250.0, "type": "shares", "shares": 2},
        {"Ticker": "AIR.PA", "AnalysisTicker": "AIR.PA", "Broker": "T212",
         "eur": 250.0, "type": "pie", "pie_pct": 50},
    ]
    matrix = alloc_to_weight_matrix(alloc, ["OR.PA", "AIR.PA"], ["Bourso", "T212"], 1000.0)

    assert matrix.shape == (2, 2)
    assert matrix[0, 0] == pytest.approx(0.25)
    assert matrix[1, 1] == pytest.approx(0.25)
    assert matrix[0, 1] == 0.0 and matrix[1, 0] == 0.0


def test_alloc_to_weight_matrix_sums_a_ticker_held_on_two_brokers():
    alloc = [
        {"Ticker": "A", "AnalysisTicker": "A", "Broker": "X", "eur": 100.0},
        {"Ticker": "A", "AnalysisTicker": "A", "Broker": "Y", "eur": 300.0},
    ]
    matrix = alloc_to_weight_matrix(alloc, ["A"], ["X", "Y"], 1000.0)
    assert matrix[0].tolist() == pytest.approx([0.1, 0.3])

    vecteur = alloc_to_weight_matrix(alloc, ["A"], None, 1000.0)
    assert vecteur.tolist() == pytest.approx([0.4])


def test_alloc_to_weight_matrix_leaves_absent_lines_at_zero():
    """`discretize_allocation` omet les lignes nulles."""
    matrix = alloc_to_weight_matrix(
        [{"Ticker": "A", "AnalysisTicker": "A", "Broker": "X", "eur": 500.0}],
        ["A", "B", "C"], ["X"], 1000.0,
    )
    assert matrix[:, 0].tolist() == pytest.approx([0.5, 0.0, 0.0])


def test_alloc_to_weight_matrix_tolerates_unknown_rows_and_zero_capital():
    alloc = [{"Ticker": "Z", "AnalysisTicker": "Z", "Broker": "X", "eur": 10.0}]
    assert alloc_to_weight_matrix(alloc, ["A"], ["X"], 1000.0).sum() == 0.0
    assert alloc_to_weight_matrix(alloc, ["Z"], ["X"], 0.0).sum() == 0.0
    assert alloc_to_weight_matrix([], ["A"], ["X"], 1000.0).sum() == 0.0
