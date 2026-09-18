import numpy as np

from app.services.finance.buffett.sector_lookthrough import (
    defensive_from_sectors,
    sector_matrix,
    sectors_from_yahoo,
)


def test_sectors_from_yahoo_canonicalizes_and_normalizes():
    result = sectors_from_yahoo({
        "technology": 0.25,
        "financial_services": 0.15,
        "healthcare": 0.10,
    })

    assert result == {
        "Technologie": 0.5,
        "Finance": 0.3,
        "Sante": 0.2,
    }


def test_sector_matrix_uses_lookthrough_and_one_hot_fallback():
    matrix, sectors = sector_matrix(
        ["WORLD", "BANK"],
        {"WORLD": {"Technology": 0.6, "Healthcare": 0.4}},
        ["Actions diversifiees", "Financial Services"],
    )

    assert np.allclose(matrix.sum(axis=1), 1.0)
    assert matrix[0, sectors.index("Technologie")] == 0.6
    assert matrix[0, sectors.index("Sante")] == 0.4
    assert matrix[1, sectors.index("Finance")] == 1.0


def test_defensive_share_is_derived_from_same_sector_composition():
    value = defensive_from_sectors({
        "Healthcare": 0.12,
        "Utilities": 0.04,
        "Consumer Defensive": 0.09,
        "Technology": 0.75,
    })

    assert value == 0.25


def test_etf_theme_is_not_treated_as_an_economic_sector():
    matrix, sectors = sector_matrix(["AWAT.PA"], {}, ["Eau"])

    assert sectors == []
    assert matrix.shape == (1, 0)
