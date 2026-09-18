from app.services.finance.buffett.region_lookthrough import aggregate_regions, country_region
from app.services.finance.buffett.optimizer import exposure_cap_feasible


def test_country_region_supports_english_and_french_labels():
    assert country_region("United States") == "Amerique du Nord"
    assert country_region("États-Unis") == "Amerique du Nord"
    assert country_region("Greece") == "Europe"
    assert country_region("Chine") == "Asie emergente"


def test_aggregate_regions_preserves_each_ticker_weight():
    result = aggregate_regions({
        "WORLD": {"United States": 0.7, "France": 0.2, "Japan": 0.1},
    })
    assert result["WORLD"] == {
        "Amerique du Nord": 0.7,
        "Europe": 0.2,
        "Asie developpee": 0.1,
    }


def test_region_weight_cap_rejects_seventy_percent_in_one_region():
    # Lignes : ETF Europe, ETF Europe, ETF Asie. Colonnes : Europe, Asie.
    matrix = [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]]
    portfolios = [[0.40, 0.25], [0.31, 0.25], [0.29, 0.50]]

    feasible = exposure_cap_feasible(matrix, portfolios, 0.50)

    assert feasible.tolist() == [False, True]
