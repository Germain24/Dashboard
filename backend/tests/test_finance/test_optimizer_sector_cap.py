from __future__ import annotations

import numpy as np
import pytest

from app.services.finance.buffett.allocation import (
    allocation_sector_diagnostics,
    enforce_discrete_sector_cap,
)
from app.services.finance.buffett.optimizer import (
    cap_sector_weights_cube,
    cap_stock_weights_cube,
    country_exposure_matrix,
    redeploy_uninvested_cube,
)
from app.services.finance.buffett.sector_constraints import constrained_sector_labels


def test_continuous_sector_cap_leaves_cash():
    cube = np.array([
        [[0.25]],
        [[0.20]],
        [[0.30]],
        [[0.25]],
    ])
    capped = cap_sector_weights_cube(
        cube,
        ["Sante", "Sante", "Finance", None],
        0.20,
    )
    assert capped[:2].sum() == pytest.approx(0.20)
    assert capped[2].sum() == pytest.approx(0.20)
    assert capped[3].sum() == pytest.approx(0.25)
    assert capped.sum() == pytest.approx(0.65)


def test_sector_cap_uses_etf_fractional_sector_exposure():
    cube = np.array([[[0.80]], [[0.20]]], dtype=float)
    matrix = np.array([
        [0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10],
        [1.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00],
    ])

    capped = cap_sector_weights_cube(
        cube,
        ["Actions diversifiees", "Technologie"],
        0.30,
        sector_matrix=matrix,
    )

    exposures = matrix.T @ capped.sum(axis=1)
    assert exposures.max() <= 0.30 + 1e-9
    assert capped[0].sum() > 0.70


def test_country_matrix_ignores_non_geographic_bucket_without_key_error():
    countries, matrix = country_exposure_matrix(
        ["GLDM", "WORLD"],
        {
            "GLDM": {"Sans pays": 1.0},
            "WORLD": {"United States": 0.7, "Japan": 0.3},
        },
        excluded_buckets={"Sans pays"},
    )

    assert countries == ["Japan", "United States"]
    assert matrix[0].sum() == 0.0
    assert matrix[1].sum() == pytest.approx(1.0)


def test_cash_freed_by_sector_cap_is_redeployed():
    """Le capital ecrete par le plafond sectoriel repart sur les lignes qui ont
    encore de la marge : le budget du broker est entierement investi."""
    cube = np.array([
        [[0.30]],
        [[0.30]],
        [[0.40]],
    ])
    result = redeploy_uninvested_cube(
        cube,
        np.array([False, False, True]),
        0.50,
        ["Sante", "Sante", None],
        0.20,
        [1.0],
        iterations=10,
    )
    assert result[:2].sum() == pytest.approx(0.20)   # plafond secteur respecte
    assert result[2].sum() == pytest.approx(0.80)    # l'ETF absorbe le reliquat
    assert result.sum() == pytest.approx(1.0)        # zero cash


def test_redeployment_never_breaks_a_cap():
    """Quand AUCUNE ligne n'a de marge, le cash reste : le redeploiement ne doit
    jamais franchir un plafond pour atteindre 100 %."""
    cube = np.array([
        [[0.50]],
        [[0.50]],
    ])
    result = redeploy_uninvested_cube(
        cube,
        np.array([False, False]),
        0.50,
        ["Sante", "Sante"],
        0.20,
        [1.0],
        iterations=10,
    )
    assert result.sum() == pytest.approx(0.20)


def test_small_broker_can_open_another_sector_when_its_only_line_is_capped():
    """Régression run 55 : T212 n'avait que NOVN (Santé), puis restait à 55 %
    quand le secteur Santé atteignait 20 % au niveau du portefeuille global."""
    cube = np.array([
        [[0.18], [0.035]],  # Santé, présente chez les deux brokers
        [[0.10], [0.000]],  # Finance, alternative T212 encore fermée
        [[0.685], [0.000]],  # ETF diversifié
    ])
    fallback = np.array([
        [[0.18], [0.050]],
        [[0.10], [0.050]],
        [[0.685], [0.000]],
    ])
    result = redeploy_uninvested_cube(
        cube,
        np.array([False, False, True]),
        0.50,
        ["Sante", "Finance", None],
        0.20,
        [0.965, 0.035],
        iterations=10,
        fallback_basis=fallback,
        max_lines=20,
    )

    assert result[0].sum() <= 0.20 + 1e-9
    assert result[:, 1].sum() == pytest.approx(0.035)
    assert result[1, 1, 0] > 0  # T212 ouvre une ligne hors Santé


def test_continuous_stock_cap_is_reapplied_after_broker_split():
    cube = np.array([
        [[0.03], [0.15]],
        [[0.02], [0.10]],
        [[0.00], [0.70]],
    ])
    capped = cap_stock_weights_cube(
        cube,
        np.array([False, False, True]),
        0.15,
    )
    assert capped[0].sum() == pytest.approx(0.15)
    assert capped[1].sum() == pytest.approx(0.12)
    assert capped[2].sum() == pytest.approx(0.70)
    assert capped.sum() == pytest.approx(0.97)


def test_diversified_and_sector_etfs_both_receive_a_risk_bucket(monkeypatch):
    monkeypatch.setattr(
        "app.services.finance.buffett.sector_constraints.load_classification",
        lambda: (
            {},
            {
                "WORLD": "Actions diversifiees",
                "XLU": "Services aux collectivites",
            },
        ),
    )
    assert constrained_sector_labels(
        ["WORLD", "XLU"],
        is_etf=[True, True],
    ) == ["Actions diversifiees", "Services aux collectivites"]


def test_discrete_whole_shares_cannot_exceed_sector_cap(monkeypatch):
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "MAX_POSITION_PCT", 0.15)
    monkeypatch.setattr(
        "app.services.finance.buffett.sector_constraints.load_classification",
        lambda: ({}, {"WORLD": "Actions diversifiees"}),
    )
    allocation = [
        {
            "Ticker": "HEALTH_A",
            "Broker": "BoursDirect2",
            "shares": 3,
            "eur": 240.0,
            "prix": 80.0,
            "type": "shares",
            "pie_pct": None,
            "Poids total (%)": 24.0,
        },
        {
            "Ticker": "WORLD",
            "Broker": "BoursDirect2",
            "shares": 5,
            "eur": 500.0,
            "prix": 100.0,
            "type": "shares",
            "pie_pct": None,
            "Poids total (%)": 50.0,
        },
    ]
    result = enforce_discrete_sector_cap(
        allocation,
        total_cap=1000.0,
        sector_by_ticker={"HEALTH_A": "Healthcare", "WORLD": "Technology"},
        is_etf_tickers={"WORLD"},
        max_sector_pct=0.20,
    )
    health = next(item for item in result if item["Ticker"] == "HEALTH_A")
    # Le plafond individuel de 15 % est plus strict ici que le plafond
    # sectoriel de 20 % : avec des actions à 80 €, une seule part reste.
    assert health["shares"] == 1
    assert health["eur"] == 80.0
    diagnostics = allocation_sector_diagnostics(
        result,
        total_cap=1000.0,
        sector_by_ticker={"HEALTH_A": "Healthcare", "WORLD": "Technology"},
        is_etf_tickers={"WORLD"},
    )
    assert diagnostics["compliant"] is True
    assert diagnostics["exposures"]["Sante"] == pytest.approx(0.08)
    # L'ETF reçoit lui aussi un compartiment de risque : il ne peut plus absorber
    # sans limite le budget libéré par l'écrêtage de l'action.
    world = next(item for item in result if item["Ticker"] == "WORLD")
    assert world["shares"] == 2
    assert diagnostics["cash_weight"] == pytest.approx(0.72)


def test_discrete_whole_shares_cannot_exceed_single_stock_cap(monkeypatch):
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "MAX_POSITION_PCT", 0.15)
    monkeypatch.setattr(
        "app.services.finance.buffett.sector_constraints.load_classification",
        lambda: ({}, {}),
    )
    allocation = [
        {
            "Ticker": "STOCK",
            "Broker": "BoursDirect2",
            "shares": 9,
            "eur": 180.0,
            "prix": 20.0,
            "type": "shares",
            "pie_pct": None,
            "Poids total (%)": 18.0,
        },
        {
            "Ticker": "WORLD",
            "Broker": "BoursDirect2",
            "shares": 8,
            "eur": 800.0,
            "prix": 100.0,
            "type": "shares",
            "pie_pct": None,
            "Poids total (%)": 80.0,
        },
    ]
    result = enforce_discrete_sector_cap(
        allocation,
        total_cap=1000.0,
        sector_by_ticker={"STOCK": "Industrials"},
        is_etf_tickers={"WORLD"},
    )
    stock = next(item for item in result if item["Ticker"] == "STOCK")
    assert stock["shares"] == 7
    assert stock["eur"] == 140.0
