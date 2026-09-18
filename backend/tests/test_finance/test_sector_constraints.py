from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def _health_country_fixture():
    labels = ["Sante", "Sante", "Sante", None]
    countries = ["France", "Etats-Unis", "Japon"]
    country_matrix = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
        [0.0, 0.0, 0.0],
    ])
    return labels, country_matrix, countries


def test_sector_country_diversification_score_rewards_continuous_spreading():
    """A exposition Sante egale, le bonus croit avec le nombre de pays."""
    from app.services.finance.buffett.sector_constraints import (
        sector_country_diversification_score,
    )

    labels, country_matrix, _ = _health_country_fixture()
    one_country = np.array([0.15, 0.00, 0.00, 0.85])
    two_countries = np.array([0.075, 0.075, 0.00, 0.85])
    three_countries = np.array([0.05, 0.05, 0.05, 0.85])

    one_country_score = sector_country_diversification_score(
        one_country,
        labels,
        country_matrix,
    )
    two_country_score = sector_country_diversification_score(
        two_countries,
        labels,
        country_matrix,
    )
    three_country_score = sector_country_diversification_score(
        three_countries,
        labels,
        country_matrix,
    )

    assert one_country_score == pytest.approx(0.0, abs=1e-12)
    assert two_country_score == pytest.approx(0.15 * 1.25 * np.log(2.0))
    assert three_country_score == pytest.approx(0.15 * 1.25 * np.log(3.0))
    assert three_country_score > two_country_score > one_country_score


def test_sector_country_exposures_aggregate_positions_in_the_same_cell():
    """L'exposition d'une cellule additionne toutes les lignes correspondantes."""
    from app.services.finance.buffett.sector_constraints import (
        sector_country_exposures,
    )

    labels = ["Sante", "Sante", "Sante", None]
    countries = ["France", "Etats-Unis"]
    country_matrix = np.array([
        [1.0, 0.0],
        [1.0, 0.0],
        [0.0, 1.0],
        [0.0, 0.0],
    ])
    exposures = sector_country_exposures(
        np.array([0.08, 0.07, 0.05, 0.80]),
        labels,
        country_matrix,
        countries,
    )

    assert exposures["Sante"]["France"] == pytest.approx(0.15)
    assert exposures["Sante"]["Etats-Unis"] == pytest.approx(0.05)


def test_exact_joint_matrix_does_not_invent_sector_country_pairs():
    from app.services.finance.buffett.sector_constraints import (
        sector_country_exposures,
    )

    weights = np.array([1.0])
    countries = ["Etats-Unis", "Japon"]
    country_matrix = np.array([[0.5, 0.5]])
    sector_matrix = np.array([[0.5, 0.5]])
    joint = np.zeros((1, 2, 2))
    joint[0, 0, 0] = 0.5  # Technologie uniquement aux Etats-Unis.
    joint[0, 1, 1] = 0.5  # Industrie uniquement au Japon.

    exposures = sector_country_exposures(
        weights,
        [None],
        country_matrix,
        countries,
        sector_matrix=sector_matrix,
        sector_names=["Technologie", "Industrie"],
        joint_matrix=joint,
    )

    assert exposures == {
        "Technologie": {"Etats-Unis": pytest.approx(0.5)},
        "Industrie": {"Japon": pytest.approx(0.5)},
    }


def test_sector_risk_penalty_accepts_stricter_budget_for_technology():
    from app.services.finance.buffett.sector_constraints import (
        sector_downside_risk_penalty,
    )

    details = {"risk_shares": np.array([[0.15], [0.15]])}
    penalty, exceeded = sector_downside_risk_penalty(
        details,
        max_risk_share=np.array([0.10, 0.20]),
        coefficient=np.array([100.0, 25.0]),
    )

    assert penalty[0] == pytest.approx(100.0 * 0.05**2)
    assert exceeded.tolist() == [True]


def test_action_position_cap_is_disabled_by_default_but_remains_configurable():
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.optimizer import cap_stock_weights_cube

    assert Config.MAX_POSITION_PCT == pytest.approx(1.0)
    cube = np.array([
        [[0.30]],
        [[0.05]],
        [[0.80]],
    ])
    capped = cap_stock_weights_cube(
        cube,
        np.array([False, False, True]),
        Config.MAX_POSITION_PCT,
    )

    assert capped[0].sum() == pytest.approx(0.30)
    assert capped[1].sum() == pytest.approx(0.05)
    assert capped[2].sum() == pytest.approx(0.80)

    capped_at_five_percent = cap_stock_weights_cube(
        cube,
        np.array([False, False, True]),
        0.05,
    )
    assert capped_at_five_percent[0].sum() == pytest.approx(0.05)
    assert capped_at_five_percent[1].sum() == pytest.approx(0.05)


def test_global_position_cap_allows_a_small_broker_to_use_one_company_only():
    from app.services.finance.buffett.optimizer import cap_stock_weights_cube

    # La seconde colonne représente T212 : son budget de 8 % du capital peut
    # rester à 100 % sur cette action tant que l'exposition globale vaut 10 %.
    cube = np.array([[[0.02], [0.08]]])
    capped = cap_stock_weights_cube(cube, np.array([False]), 0.10)

    assert capped == pytest.approx(cube)
    assert capped.sum() == pytest.approx(0.10)


def test_sector_downside_risk_uses_tail_risk_not_only_nominal_weight():
    from app.services.finance.buffett.sector_constraints import (
        sector_downside_risk_from_context,
    )
    from app.services.finance.buffett.starr import benchmark_relative_batch_details

    simulated = np.array([
        [-0.10, -0.02],
        [-0.08, -0.01],
        [0.02, 0.01],
        [0.03, 0.02],
    ])
    weights = np.array([[0.50], [0.50]])
    _, context = benchmark_relative_batch_details(
        weights,
        simulated,
        np.zeros(2),
        {"annual_return": 0.0, "cvar": 0.0, "downside_deviation": 0.0},
        alpha=0.50,
        downside_weight=1.0,
    )
    details = sector_downside_risk_from_context(
        simulated,
        ["Technologie", "Sante"],
        context,
        downside_weight=1.0,
    )
    shares = dict(zip(details["sectors"], details["risk_shares"][:, 0], strict=True))

    assert shares["Technologie"] > shares["Sante"]
    assert sum(shares.values()) == pytest.approx(1.0)


def test_sector_risk_penalty_starts_above_soft_budget():
    from app.services.finance.buffett.sector_constraints import (
        sector_downside_risk_penalty,
    )

    penalty, exceeded = sector_downside_risk_penalty(
        {"risk_shares": np.array([[0.15, 0.30], [0.10, 0.10]])},
        max_risk_share=0.20,
        coefficient=25.0,
    )

    assert penalty[0] == pytest.approx(0.0)
    assert not exceeded[0]
    assert penalty[1] == pytest.approx(0.25)
    assert exceeded[1]


def test_risk_categories_are_resolved_before_market_data_download():
    from app.services.finance.buffett.sector_constraints import resolve_risk_categories

    broker_table = pd.DataFrame([
        {
            "Ticker Yahoo Finance": "GLDM",
            "Secteur 1": "ETF",
            "Secteur 2": "Matières premières",
            "Secteur 3": "Métaux précieux",
            "Secteur 4": "Or",
            "Secteur 5": "Physique",
        },
        {
            "Ticker Yahoo Finance": "WORLD",
            "Secteur 1": "ETF",
            "Secteur 2": "Actions",
            "Secteur 3": "Diversifié",
            "Secteur 4": "",
            "Secteur 5": "Monde",
        },
        {
            "Ticker Yahoo Finance": "BAD",
            "Secteur 1": "ETF",
            "Secteur 2": "Actions",
            "Secteur 3": "Sectoriel",
            "Secteur 4": "",
            "Secteur 5": "ESG",
        },
    ])
    categories, diagnostics = resolve_risk_categories(
        {
            "NVS": "Healthcare",
            "GLDM": "ETF",
            "WORLD": "ETF",
            "BAD": "ETF",
        },
        broker_table=broker_table,
    )

    assert categories == {
        "NVS": "Sante",
        "GLDM": "Or",
        "WORLD": "Monde",
    }
    assert diagnostics["excluded_tickers"] == ["BAD"]
    assert diagnostics["sources"] == {
        "yahoo": 1,
        "secteur_4": 1,
        "secteur_5": 1,
    }


def test_risk_category_uses_secondary_broker_quote_metadata(monkeypatch):
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.sector_constraints import resolve_risk_categories

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"BoursDirect2": 1000.0})
    broker_table = pd.DataFrame([
        {
            "Ticker Yahoo Finance": "WORLD.DE",
            "Fundamentals Symbol": "WORLD.DE",
            "Bourse Direct 2": False,
            "Secteur 1": "ETF",
            "Secteur 4": "",
        },
        {
            "Ticker Yahoo Finance": "WORLD.PA",
            "Fundamentals Symbol": "WORLD.DE",
            "Bourse Direct 2": True,
            "Secteur 1": "ETF",
            "Secteur 4": "Monde",
        },
    ])

    categories, diagnostics = resolve_risk_categories(
        {"WORLD.DE": "ETF"},
        broker_table=broker_table,
    )

    assert categories == {"WORLD.DE": "Monde"}
    assert diagnostics["excluded"] == 0
