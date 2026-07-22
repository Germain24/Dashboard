"""Calibration Buffett relative au secteur et à la région (pur Python)."""

from __future__ import annotations

import pytest

from app.services.finance.buffett.scoring_pure import (
    RELATIVE_MIN_PEERS,
    calibrate_relative_selection,
    is_selection_eligible,
    region_for_country,
    selection_score,
)


def _stock(
    score: float,
    sector: str,
    country: str,
    per: float,
    peg: float | None = 0.8,
    *,
    base: bool = True,
) -> tuple[float, dict]:
    return score, {
        "Secteur": sector,
        "Pays": country,
        "PER": per,
        "PEG": peg,
        "growth_reliable": base,
        "valuation_base_eligible": base,
        "Achat": base,
    }


def test_regions_cover_the_added_asian_markets_and_common_aliases():
    assert region_for_country("China") == "asia_pacific"
    assert region_for_country("Japan") == "asia_pacific"
    assert region_for_country("South Korea") == "asia_pacific"
    assert region_for_country("US") == "north_america"
    assert region_for_country("FR") == "europe"
    assert region_for_country("Inconnu") is None


def test_same_high_per_can_pass_in_tech_and_fail_in_financials():
    results = {
        **{
            f"TECH{i}": _stock(80, "Technology", "United States", per, peg)
            for i, (per, peg) in enumerate(
                [(40, 1.2), (45, 1.4), (50, 1.6), (55, 1.8), (60, 2.0)]
            )
        },
        **{
            f"BANK{i}": _stock(80, "Financial Services", "United States", per, peg)
            for i, (per, peg) in enumerate(
                [(8, 0.4), (10, 0.5), (12, 0.6), (14, 0.7), (16, 0.8)]
            )
        },
        "TECH_TARGET": _stock(80, "Technology", "United States", 45, 1.4),
        "BANK_TARGET": _stock(80, "Financial Services", "United States", 45, 1.4),
    }

    calibrated = calibrate_relative_selection(results)

    assert calibrated["TECH_TARGET"][1]["Achat"] is True
    assert calibrated["BANK_TARGET"][1]["Achat"] is False
    assert calibrated["TECH_TARGET"][1]["valuation_relative"]["per_peer_scope"] == "sector_region"
    assert calibrated["BANK_TARGET"][1]["valuation_relative"]["per_relative"] > 1


def test_regression_per_26_tech_vs_13_finance_without_global_cap_25():
    """Cas observé : chaque titre est jugé contre SON secteur, pas contre 25."""
    results = {
        "TECH_TARGET": _stock(80, "Technology", "United States", 26, 1.0),
        "TECH_0": _stock(80, "Technology", "United States", 25, 1.0),
        "TECH_1": _stock(80, "Technology", "United States", 27, 1.0),
        "TECH_2": _stock(80, "Technology", "United States", 28, 1.0),
        "TECH_3": _stock(80, "Technology", "United States", 29, 1.0),
        "BANK_0": _stock(80, "Financial Services", "United States", 10, 1.0),
        "BANK_1": _stock(80, "Financial Services", "United States", 12, 1.0),
        "BANK_2": _stock(80, "Financial Services", "United States", 12.5, 1.0),
        "BANK_TARGET": _stock(80, "Financial Services", "United States", 13, 1.0),
        "BANK_3": _stock(80, "Financial Services", "United States", 14, 1.0),
    }

    calibrated = calibrate_relative_selection(results)

    tech = calibrated["TECH_TARGET"][1]
    bank = calibrated["BANK_TARGET"][1]
    assert tech["valuation_relative"]["per_reference"] == 27
    assert tech["Achat"] is True  # PER 26 > ancien plafond 25, mais < pairs tech 27
    assert bank["valuation_relative"]["per_reference"] == 12.5
    assert bank["Achat"] is False  # PER 13 pourtant bas en absolu, mais > pairs 12,5


def test_region_is_used_only_when_the_sector_region_group_is_large_enough():
    assert RELATIVE_MIN_PEERS == 5
    results = {
        **{
            f"EU{i}": _stock(70, "Technology", "France", per, 0.8)
            for i, per in enumerate([20, 22, 24, 26, 28])
        },
        # Singleton asiatique : il ne doit surtout pas devenir sa propre médiane.
        "ASIA_ONLY": _stock(70, "Technology", "Japan", 100, 0.8),
    }

    calibrated = calibrate_relative_selection(results)
    metrics = calibrated["ASIA_ONLY"][1]

    assert metrics["valuation_relative"]["per_peer_scope"] == "sector"
    assert metrics["valuation_relative"]["per_peer_count"] == 6
    assert metrics["valuation_relative"]["per_relative"] > 1
    assert metrics["Achat"] is False


def test_small_sector_falls_back_to_global_instead_of_self_reference():
    results = {
        **{
            f"TECH{i}": _stock(70, "Technology", "France", per, 0.8)
            for i, per in enumerate([20, 22, 24, 26, 28])
        },
        "RARE": _stock(70, "Space", "Japan", 100, 0.8),
    }

    metrics = calibrate_relative_selection(results)["RARE"][1]

    assert metrics["valuation_relative"]["per_peer_scope"] == "global"
    assert metrics["valuation_relative"]["per_relative"] > 1
    assert metrics["Achat"] is False


def test_quality_score_is_recentered_so_sector_criteria_counts_are_comparable():
    results = {
        **{
            f"BANK{i}": _stock(score, "Financial Services", "United States", 10, 0.5)
            for i, score in enumerate([88, 89, 90, 91, 92])
        },
        **{
            f"TECH{i}": _stock(score, "Technology", "United States", 30, 1.5)
            for i, score in enumerate([58, 59, 60, 61, 62])
        },
    }

    calibrated = calibrate_relative_selection(results)

    assert selection_score(*calibrated["BANK2"]) == pytest.approx(75.0)
    assert selection_score(*calibrated["TECH2"]) == pytest.approx(75.0)


def test_missing_peg_is_neutral_but_unreliable_growth_still_blocks():
    results = {
        f"PEER{i}": _stock(80, "Technology", "France", per, None)
        for i, per in enumerate([10, 12, 14, 16, 18])
    }
    results["NO_PEG"] = _stock(80, "Technology", "France", 12, None)
    results["UNRELIABLE"] = _stock(
        80, "Technology", "France", 12, None, base=False,
    )

    calibrated = calibrate_relative_selection(results)

    assert calibrated["NO_PEG"][1]["Achat"] is True
    assert calibrated["UNRELIABLE"][1]["Achat"] is False


def test_fewer_than_five_total_peers_cannot_validate_a_relative_valuation():
    results = {
        f"T{i}": _stock(80, "Technology", "France", 10 + i, 0.8)
        for i in range(4)
    }

    calibrated = calibrate_relative_selection(results)

    assert all(not metrics["Achat"] for _, metrics in calibrated.values())
    assert {
        metrics["valuation_relative"]["per_peer_scope"]
        for _, metrics in calibrated.values()
    } == {"insufficient"}


def test_final_selection_requires_both_relative_quality_and_relative_value():
    assert is_selection_eligible(95, {"ScoreSelection": 85, "Achat": True}, 80)
    assert not is_selection_eligible(95, {"ScoreSelection": 85, "Achat": False}, 80)
    assert not is_selection_eligible(95, {"ScoreSelection": 75, "Achat": True}, 80)


@pytest.mark.parametrize("exception", ["is_etf", "is_forced", "is_held"])
def test_etf_forced_and_held_bypass_the_two_selection_gates(exception):
    kwargs = {exception: True}
    assert is_selection_eligible(
        10,
        {"ScoreSelection": 10, "Achat": False},
        80,
        **kwargs,
    )


def test_input_is_not_mutated_and_etf_and_forced_tickers_are_preserved():
    source_metrics = {
        "Secteur": "Technology",
        "Pays": "France",
        "PER": 20,
        "PEG": 1.0,
        "Achat": False,
    }
    original = dict(source_metrics)
    results = {
        **{
            f"PEER{i}": _stock(70, "Technology", "France", 18 + i, 1.0)
            for i in range(5)
        },
        "SOURCE": (70, source_metrics),
        "ETF": (200, {"Secteur": "ETF", "Achat": False}),
        "FORCED": (0, {"Secteur": "Inconnu", "Achat": False}),
    }

    calibrated = calibrate_relative_selection(results, always_buy={"FORCED"})

    assert source_metrics == original
    assert calibrated["ETF"][1]["Achat"] is True
    assert calibrated["FORCED"][1]["Achat"] is True


def test_second_pass_persists_relative_score_without_losing_existing_extra(mem_session):
    import datetime as dt

    from app.models.finance import BuffettRun, BuffettRunResult
    from app.services.finance.buffett.reporting import update_relative_selections

    run = BuffettRun(run_date=dt.date(2026, 7, 22))
    mem_session.add(run)
    mem_session.commit()
    mem_session.refresh(run)
    row = BuffettRunResult(
        run_id=run.id,
        ticker="AAPL",
        achat=False,
        secteurs_extra={"allocations": [{"broker": "Trading212"}]},
    )
    mem_session.add(row)
    mem_session.commit()

    metrics = {
        "Achat": True,
        "growth_reliable": True,
        "valuation_base_eligible": True,
        "valuation_relative": {
            "model": "sector_region_median_v1",
            "score_selection": 84.5,
            "per_relative": 0.9,
        },
    }
    update_relative_selections(mem_session, run.id, {"AAPL": (81.0, metrics)})

    mem_session.refresh(row)
    assert row.achat is True
    assert row.secteurs_extra["valuation_relative"]["score_selection"] == 84.5
    assert row.secteurs_extra["scoring_inputs"]["valuation_base_eligible"] is True
    assert row.secteurs_extra["allocations"] == [{"broker": "Trading212"}]


def test_cache_second_pass_preserves_full_metrics_and_financial_data_age(tmp_path):
    from app.services.finance.buffett.cache_manager import CacheManager
    from app.services.finance.buffett.currency import ensure_volume_eur

    cache = CacheManager(str(tmp_path / "cache.json"))
    original_metrics = {
        "Achat": False,
        "Volume": 1_234_567.89,
        "VolumeDevise": "EUR",
        "Prix": 42.0,
        "Industrie": "Consumer Electronics",
        "ratios_recents": {"roe": 0.31, "debt_to_equity": 1.2},
    }
    cache.update("AAPL", 2025, 81.0, original_metrics)
    before = dict(cache.cache["AAPL"])

    cache.replace_cached_metrics(
        "AAPL",
        81.0,
        {
            "Achat": True,
            "ScoreSelection": 84.5,
            "valuation_relative": {"per_relative": 0.9},
        },
    )

    after = cache.cache["AAPL"]
    assert after["latest_year"] == before["latest_year"]
    assert after["last_update"] == before["last_update"]
    assert after["metrics"]["Achat"] is True
    assert after["metrics"]["ScoreSelection"] == 84.5
    assert after["metrics"]["VolumeDevise"] == "EUR"
    assert after["metrics"]["Industrie"] == "Consumer Electronics"
    assert after["metrics"]["ratios_recents"] == original_metrics["ratios_recents"]

    # Le marqueur EUR conservé empêche ensure_volume_eur de multiplier une
    # seconde fois le volume déjà monétaire par le prix.
    normalized = ensure_volume_eur(after["metrics"], "AAPL")
    assert normalized["Volume"] == original_metrics["Volume"]
