"""Bonus de diversification secteur × pays : les ETF doivent y figurer.

Un ETF est composé de plusieurs secteurs ET de plusieurs pays. Le bonus mesure,
pour chaque secteur, la diversité PAYS de l'exposition — pondérée par le poids de
ce secteur dans le portefeuille.

Défaut corrigé ici : un ETF dont la composition sectorielle est inconnue avait
une ligne ENTIÈREMENT NULLE dans la matrice des secteurs (comportement voulu :
on n'invente pas un pseudo-secteur portant un nom de pays). Cette ligne nulle le
faisait disparaître de TOUS les termes de la somme — son poids s'évaporait du
calcul et il n'obtenait aucun bonus, alors que ses pays étaient parfaitement
connus. L'instrument le plus diversifié du portefeuille était donc traité comme
le moins diversifié, et l'optimiseur lui préférait mécaniquement des actions.

Mesuré avant correction : 0,0 au lieu de 0,5 pour un ETF réparti sur deux pays.
"""

import numpy as np
import pytest

from app.services.finance.buffett.sector_constraints import (
    UNASSIGNED_SECTOR,
    geographic_diversification_factors,
    sector_country_deficit_penalty,
    sector_country_diversification_components,
    sector_country_diversification_score,
    sector_country_exposures,
    with_unassigned_sector,
)


def test_geographic_bonus_multiplies_country_equality_region_equality_and_count():
    balanced = geographic_diversification_factors(
        np.array([[1 / 3], [1 / 3], [1 / 3]]),
        np.array([[0.5], [0.5]]),
        country_names=["France", "Chine", "Japon"],
        region_names=["Europe", "Asie"],
        country_std_exponent=20.0,
        region_std_exponent=20.0,
    )
    uneven = geographic_diversification_factors(
        np.array([[0.8], [0.1], [0.1]]),
        np.array([[0.9], [0.1]]),
        country_names=["France", "Chine", "Japon"],
        region_names=["Europe", "Asie"],
        country_std_exponent=20.0,
        region_std_exponent=20.0,
    )

    assert balanced["country_std"][0] == pytest.approx(0.0)
    assert balanced["region_std"][0] == pytest.approx(0.0)
    assert balanced["country_count"][0] == pytest.approx(3.0)
    assert balanced["combined"][0] > uneven["combined"][0]


def test_geographic_bonus_rewards_more_significant_countries():
    two = geographic_diversification_factors(
        np.array([[0.5], [0.5], [0.0]]),
        np.array([[1.0]]),
        country_names=["France", "Chine", "Japon"],
        region_names=["Europe"],
    )
    three = geographic_diversification_factors(
        np.array([[1 / 3], [1 / 3], [1 / 3]]),
        np.array([[1.0]]),
        country_names=["France", "Chine", "Japon"],
        region_names=["Europe"],
    )

    assert three["country_count_bonus"][0] > two["country_count_bonus"][0]
    assert three["combined"][0] > two["combined"][0]


def test_geographic_bonus_does_not_reward_unknown_exposure():
    factors = geographic_diversification_factors(
        np.array([[0.8], [0.2]]),
        np.array([[0.8], [0.2]]),
        country_names=["Inconnu", "France"],
        region_names=["Inconnu", "Europe"],
    )

    assert factors["country_coverage"][0] == pytest.approx(0.2)
    assert factors["region_coverage"][0] == pytest.approx(0.2)
    assert factors["combined"][0] < 0.05

# ── La colonne « part non attribuée » ───────────────────────────────────────


def test_a_fully_described_line_gets_no_residue():
    """Une action de secteur connu somme déjà à 1 : rien à rattraper."""
    complete = with_unassigned_sector(np.array([[1.0, 0.0]]))
    assert complete.shape == (1, 3)
    assert complete[0, 2] == pytest.approx(0.0)


def test_an_undescribed_line_is_entirely_residue():
    """Un ETF sans composition sectorielle : tout son poids est du résidu."""
    complete = with_unassigned_sector(np.array([[0.0, 0.0]]))
    assert complete[0, 2] == pytest.approx(1.0)


def test_a_partially_described_line_keeps_the_remainder():
    complete = with_unassigned_sector(np.array([[0.3, 0.2]]))
    assert complete[0, 2] == pytest.approx(0.5)


def test_every_line_sums_to_one_afterwards():
    """Aucun poids ne doit s'évaporer du calcul — c'était tout le défaut."""
    brut = np.array([[1.0, 0.0], [0.0, 0.0], [0.4, 0.1]])
    complete = with_unassigned_sector(brut)
    assert np.allclose(complete.sum(axis=1), 1.0)


def test_the_source_matrix_is_left_untouched():
    """La matrice d'origine alimente AUSSI les contraintes de risque sectoriel :
    le résidu ne doit jamais y apparaître, sous peine de créer un faux secteur
    soumis aux plafonds."""
    brut = np.array([[0.0, 0.0]])
    avant = brut.copy()
    with_unassigned_sector(brut)
    assert np.array_equal(brut, avant)
    assert brut.shape == (1, 2)


def test_an_overfull_line_is_not_given_a_negative_residue():
    """Robustesse aux arrondis : jamais de part négative."""
    complete = with_unassigned_sector(np.array([[0.7, 0.4]]))
    assert complete[0, 2] >= 0.0


# ── Le score de diversification ─────────────────────────────────────────────


def test_an_etf_without_sectors_now_scores():
    """Le cœur de la régression : pays connus, secteurs inconnus -> bonus > 0."""
    poids = np.array([1.0])
    pays = np.array([[0.5, 0.5]])          # 50 % Suisse / 50 % Italie
    secteurs_inconnus = np.zeros((1, 2))

    score = sector_country_diversification_score(
        poids, [None], pays, sector_matrix=secteurs_inconnus
    )
    assert score > 0.0
    # Deux pays à parts égales : log(2) + 0,25 × log(2).
    assert score == pytest.approx(1.25 * np.log(2.0))


def test_a_single_country_etf_still_scores_zero():
    """Le bonus récompense la diversité, pas l'ignorance."""
    score = sector_country_diversification_score(
        np.array([1.0]), [None], np.array([[1.0, 0.0]]),
        sector_matrix=np.zeros((1, 2)),
    )
    assert score == pytest.approx(0.0)


def test_more_countries_beats_fewer_even_without_sectors():
    commun = dict(sector_matrix=np.zeros((1, 2)))
    large = sector_country_diversification_score(
        np.array([1.0]), [None], np.array([[0.34, 0.33, 0.33]]), **commun
    )
    etroit = sector_country_diversification_score(
        np.array([1.0]), [None], np.array([[0.5, 0.5, 0.0]]), **commun
    )
    assert large > etroit


def test_a_plain_stock_keeps_its_previous_score():
    """Non-régression stricte : une action de secteur connu et de pays unique
    valait zéro, et doit continuer de valoir zéro."""
    score = sector_country_diversification_score(
        np.array([1.0]), ["Finance"], np.array([[1.0, 0.0]]),
        sector_matrix=np.array([[1.0, 0.0]]),
    )
    assert score == pytest.approx(0.0)


def test_a_multi_country_stock_is_unaffected_by_the_residue():
    """Une ligne déjà complète ne gagne rien au passage : son résidu est nul."""
    score = sector_country_diversification_score(
        np.array([1.0]), ["Finance"], np.array([[0.5, 0.5]]),
        sector_matrix=np.array([[1.0, 0.0]]),
    )
    assert score == pytest.approx(1.25 * np.log(2.0))


def test_the_whole_invested_weight_is_accounted_for():
    """Moitié action décrite, moitié ETF non décrit : les deux comptent."""
    poids = np.array([0.5, 0.5])
    pays = np.array([[0.5, 0.5], [0.5, 0.5]])
    secteurs = np.array([[1.0, 0.0], [0.0, 0.0]])   # 2e ligne = ETF sans secteur
    score = sector_country_diversification_score(
        poids, ["Finance", None], pays, sector_matrix=secteurs
    )
    # Chaque moitié est répartie 50/50 : contribution moitié du score à 1.
    assert score == pytest.approx(1.25 * np.log(2.0))


def test_components_allow_disabling_only_one_sector_bonus():
    weights = np.array([0.5, 0.5])
    countries = np.array([[0.5, 0.5], [0.5, 0.5]])
    sectors = np.array([[1.0, 0.0], [0.0, 1.0]])
    components = sector_country_diversification_components(
        weights, countries, sectors
    )
    expected = 0.5 * 1.25 * np.log(2.0)
    assert components[:2].tolist() == pytest.approx([expected, expected])
    assert components[2] == pytest.approx(0.0)
    # Neutraliser le premier secteur laisse bien le second contribuer.
    components[0] = 0.0
    assert components.sum() == pytest.approx(expected)


def test_deficit_penalty_targets_two_then_three_effective_countries():
    sectors = np.ones((3, 1))
    one_country = np.array([[1.0, 0.0, 0.0]] * 3)
    three_countries = np.eye(3)
    medium_weights = np.array([0.06, 0.0, 0.0])
    large_weights = np.array([0.04, 0.04, 0.04])
    assert sector_country_deficit_penalty(
        medium_weights, one_country, sectors, coefficient=1.0
    ) > 0.0
    assert sector_country_deficit_penalty(
        large_weights, three_countries, sectors, coefficient=1.0
    ) == pytest.approx(0.0)


def test_deficit_penalty_ignores_small_sectors():
    assert sector_country_deficit_penalty(
        np.array([0.049]),
        np.array([[1.0, 0.0]]),
        np.array([[1.0]]),
        coefficient=1.0,
    ) == pytest.approx(0.0)


# ── Diagnostic : le compartiment doit être nommé, pas caché ─────────────────


def test_the_unassigned_share_is_visible_in_the_breakdown():
    expositions = sector_country_exposures(
        np.array([1.0]),
        [None],
        np.array([[0.5, 0.5]]),
        ["Suisse", "Italie"],
        sector_matrix=np.zeros((1, 2)),
        sector_names=["Finance", "Technologie"],
    )
    assert UNASSIGNED_SECTOR in expositions
    assert expositions[UNASSIGNED_SECTOR]["Suisse"] == pytest.approx(0.5)
    assert expositions[UNASSIGNED_SECTOR]["Italie"] == pytest.approx(0.5)


def test_a_described_portfolio_shows_no_unassigned_bucket():
    expositions = sector_country_exposures(
        np.array([1.0]),
        ["Finance"],
        np.array([[1.0]]),
        ["Suisse"],
        sector_matrix=np.array([[1.0]]),
        sector_names=["Finance"],
    )
    assert UNASSIGNED_SECTOR not in expositions
    assert expositions["Finance"]["Suisse"] == pytest.approx(1.0)
