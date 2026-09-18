"""Tests pur Python — scoring MOAT sans DB, sans pandas, en < 1 s.

Couvre : exponential_weights, score_year, compute_moat_score,
         compute_buy_signal (logic from WarrenBuffetMensuel.py).
"""
from __future__ import annotations

import pytest

from app.services.finance.buffett.scoring_pure import (
    PEG_GROWTH_CAP,
    compute_buffett_score_v2,
    compute_buy_signal,
    compute_moat_score,
    exponential_weights,
    robust_growth,
    score_year,
    select_growth,
)


def _v2_year(growth: float = 0.12) -> dict:
    return {
        **_perfect_year(),
        "pretax_growth_rate": growth,
        "net_income_growth_rate": growth,
        "eps_growth_rate": growth,
        "cash_growth_rate": growth,
        "fcf_per_share_growth_rate": growth,
        "share_count_growth": -0.01,
        "fcf_to_net_income": 1.0,
        "fcf_margin": 0.22,
    }


def test_v2_separates_observed_quality_confidence_and_ranking():
    four_years = compute_buffett_score_v2([_v2_year()] * 4)
    eight_years = compute_buffett_score_v2([_v2_year()] * 8)

    assert four_years["buffett_quality_score"] == eight_years["buffett_quality_score"]
    assert four_years["confidence_pct"] < eight_years["confidence_pct"]
    assert four_years["ranking_score"] < four_years["buffett_quality_score"]


def test_v3_quality_excludes_moat_proxy_and_uses_shrinkage():
    result = compute_buffett_score_v2([_v2_year()] * 4)
    expected_quality = (
        0.60 * result["financial_quality_score"]
        + 0.30 * result["durability_score"]
        + 0.10 * result["dilution_discipline_score"]
    )
    expected_ranking = 60.0 + (result["confidence_pct"] / 100.0) * (
        result["buffett_quality_score"] - 60.0
    )
    assert result["model_version"] == 3
    assert result["buffett_quality_score"] == pytest.approx(expected_quality, abs=0.03)
    assert result["ranking_score"] == pytest.approx(expected_ranking, abs=0.03)
    assert result["financial_moat_proxy_score"] > 0


def test_v3_partial_bank_is_explicitly_not_comparable():
    result = compute_buffett_score_v2(
        [_v2_year()] * 8, "Financial Services", "Banks - Regional"
    )
    assert result["business_model"] == "bank_partial"
    assert result["comparable_to_standard"] is False
    assert result["confidence_pct"] < 65.0


def test_v2_first_year_growth_is_not_awarded_artificially():
    first = _v2_year()
    first.update({key: None for key in (
        "pretax_growth_rate", "net_income_growth_rate", "eps_growth_rate",
        "cash_growth_rate", "fcf_per_share_growth_rate",
    )})
    without_legacy_bonus = compute_buffett_score_v2([first, _v2_year()] * 4)
    first.update({
        "pretax_growth": True,
        "net_income_growth": True,
        "eps_growth": True,
        "cash_growth": True,
        "retained_growth": True,
    })
    with_legacy_booleans = compute_buffett_score_v2([first, _v2_year()] * 4)

    assert without_legacy_bonus == with_legacy_booleans


def test_v2_debt_uses_repayment_years_not_twenty_five_percent():
    acceptable = [_v2_year() | {"lt_debt_ratio": 3.0} for _ in range(8)]
    excessive = [_v2_year() | {"lt_debt_ratio": 7.0} for _ in range(8)]

    acceptable_score = compute_buffett_score_v2(acceptable)
    excessive_score = compute_buffett_score_v2(excessive)

    assert acceptable_score["family_scores"]["balance_sheet"]["score"] > 50
    assert (
        acceptable_score["financial_quality_score"]
        > excessive_score["financial_quality_score"]
    )


def test_v2_financial_subtypes_only_specialize_banks_and_insurers():
    bank = compute_buffett_score_v2(
        [_v2_year()] * 8,
        "Financial Services",
        "Banks - Regional",
    )
    exchange = compute_buffett_score_v2(
        [_v2_year()] * 8,
        "Financial Services",
        "Financial Data & Stock Exchanges",
    )

    assert bank["business_model"] == "bank_partial"
    assert exchange["business_model"] == "exchange"
    assert "balance_sheet" not in bank["family_scores"]
    assert "balance_sheet" in exchange["family_scores"]
    assert bank["confidence_pct"] < exchange["confidence_pct"]


def test_v2_financial_subtypes_recognize_french_labels():
    from app.services.finance.buffett.scoring_pure import financial_business_model

    assert financial_business_model("Services financiers", "Banques régionales") == "bank_partial"
    assert financial_business_model("Services financiers", "Bourse et données") == "exchange"


def test_v3_pending_models_are_flagged_without_becoming_partial_models():
    commodity = compute_buffett_score_v2(
        [_v2_year()] * 8, "Basic Materials", "Copper Mining"
    )
    broker = compute_buffett_score_v2(
        [_v2_year()] * 8, "Financial Services", "Capital Markets Brokerage"
    )

    assert commodity["business_model"] == "commodity_generic_pending"
    assert broker["business_model"] == "broker_trading_generic_pending"
    assert commodity["model_status"] == "generic_pending"
    assert commodity["model_fit"] == 0.85
    assert commodity["model_complete"] is False
    assert commodity["comparable_to_standard"] is True
    assert commodity["confidence_pct"] == pytest.approx(
        commodity["confidence_before_fit_pct"] * 0.85, abs=0.02
    )
    assert commodity["quality_score_version"] == "V3.0"
    assert commodity["moat_proxy_version"] == "GENERIC_PENDING_V1"


@pytest.mark.parametrize(("ticker", "name", "expected", "complete"), [
    ("V", "Visa Inc.", "payment_network", True),
    ("MA", "Mastercard Incorporated", "payment_network", True),
    ("GTT.PA", "Gaztransport & Technigaz SA", "ip_licensing_engineering", True),
    ("MCO", "Moody's Corporation", "credit_ratings_data", True),
    ("AUTO.L", "Auto Trader Group plc", "marketplace_network", True),
    ("HEMNF", "Hemnet Group AB", "marketplace_network", True),
    ("AJB.L", "AJ Bell plc", "investment_platform_generic_pending", False),
    ("SEIC", "SEI Investments Company", "financial_platform_hybrid_generic_pending", False),
])
def test_v3_entity_router_is_explicit(ticker, name, expected, complete):
    result = compute_buffett_score_v2(
        [_v2_year()] * 8,
        "Financial Services",
        "Capital Markets",
        ticker=ticker,
        company_name=name,
    )
    assert result["business_model"] == expected
    assert result["model_complete"] is complete
    assert result["comparison_group"]


def test_v3_unknown_financial_model_is_never_blank_or_purchasable():
    result = compute_buffett_score_v2(
        [_v2_year()] * 8, "Financial Services", "Unclassified Activity"
    )
    assert result["business_model"] == "unknown_model"
    assert result["model_complete"] is False
    assert result["comparable_to_standard"] is False
    assert result["confidence_pct"] == 0.0


# ── exponential_weights ─────────────────────────────────────────────────────

def test_weights_empty():
    assert exponential_weights(0) == []


def test_weights_single():
    assert exponential_weights(1) == [1.0]


def test_weights_sum_to_one():
    for n in [2, 5, 10]:
        w = exponential_weights(n)
        assert abs(sum(w) - 1.0) < 1e-9
        assert len(w) == n


def test_weights_increase_from_oldest_to_most_recent():
    w = exponential_weights(5)
    for i in range(len(w) - 1):
        assert w[i] <= w[i + 1]


# ── score_year ──────────────────────────────────────────────────────────────

def _perfect_year() -> dict:
    """Ratios d'une entreprise MOAT parfaite."""
    return {
        "gpm": 0.80,        # > 60%
        "sga": 0.10,        # < 80%
        "rd": 0.05,         # < 30%
        "depr": 0.05,       # < 15%
        "interest_exp": 0.02,
        "pretax_growth": True,
        "net_income_growth": True,
        "net_income_positive": True,
        "nim": 0.35,        # > 20%
        "eps_growth": True,
        "cash_growth": True,
        "debt_ratio": 0.20,
        "liab_ratio": 0.80,
        "lt_debt_ratio": 0.05,
        "debt_eq": 0.30,    # < 80%
        "retained_growth": True,
        "cap_stock_var": True,
        "roe": 0.30,        # > 20%
        "roic": 0.20,       # > 10%
        "capex": 0.10,      # < 25%
        "buybacks": True,
        "first_year": False,
    }


def test_score_year_perfect_is_high():
    s = score_year(_perfect_year())
    assert s > 0.85, f"Perfect year should score > 0.85, got {s:.3f}"


def test_score_year_zero_on_empty():
    s = score_year({})
    assert s == 0.0


def test_score_year_first_year_skips_growth():
    """first_year=True devrait donner 1.0 pour tous les critères de croissance."""
    ratios = {**_perfect_year(), "first_year": True,
              "pretax_growth": False, "net_income_growth": False}
    s_first = score_year(ratios)
    ratios2 = {**ratios, "first_year": False}
    s_not_first = score_year(ratios2)
    assert s_first >= s_not_first


def test_score_year_bad_ratios_is_low():
    bad = {
        "gpm": 0.10, "sga": 1.50, "rd": 0.80, "nim": 0.02,
        "roe": 0.01, "roic": 0.01, "capex": 1.00, "debt_eq": 2.00,
        "net_income_positive": False, "first_year": False,
    }
    s = score_year(bad)
    assert s < 0.30, f"Bad ratios should score < 0.30, got {s:.3f}"


def test_score_year_bounded():
    """Le score doit toujours être dans [0, 1]."""
    import random
    rng = random.Random(42)
    for _ in range(50):
        r = {k: rng.random() for k in ["gpm", "sga", "nim", "roe", "capex"]}
        s = score_year(r)
        assert 0.0 <= s <= 1.0


# ── compute_moat_score ──────────────────────────────────────────────────────

def test_moat_score_empty():
    assert compute_moat_score([]) == 0.0


def test_moat_score_single_perfect():
    s = compute_moat_score([_perfect_year()])
    assert s > 85.0


def test_moat_score_range():
    years = [_perfect_year() for _ in range(5)]
    s = compute_moat_score(years)
    assert 0.0 <= s <= 100.0


def test_moat_score_all_perfect_beats_all_bad():
    """Un historique parfait doit battre un historique mediocre."""
    # 4 ratios financiers mauvais, explicitement faux pour growth aussi
    bad = {
        "gpm": 0.05, "nim": 0.01, "roe": 0.01, "roic": 0.01,
        "capex": 1.0, "debt_eq": 3.0, "sga": 2.0,
        "net_income_positive": False,
        "pretax_growth": False, "net_income_growth": False,
        "eps_growth": False, "cash_growth": False, "retained_growth": False,
    }
    perfect = _perfect_year()

    score_all_good = compute_moat_score([perfect] * 4)
    score_all_bad = compute_moat_score([bad] * 4)
    assert score_all_good > score_all_bad
    assert score_all_good > 70.0
    assert score_all_bad < 30.0


def test_moat_score_returns_float():
    s = compute_moat_score([_perfect_year()])
    assert isinstance(s, float)


def test_most_recent_year_has_more_influence():
    good = _perfect_year()
    bad = {**good, "gpm": 0.0}
    improving = compute_moat_score([bad, good])
    deteriorating = compute_moat_score([good, bad])
    assert improving > deteriorating


def test_missing_data_reduces_confidence_without_becoming_fake_zero_ratios():
    complete = score_year(_perfect_year())
    sparse = score_year({"gpm": 0.80})
    assert 0 < sparse < complete


def test_financial_profile_ignores_industrial_gross_margin():
    relevant = {
        "net_income_growth": True,
        "net_income_positive": True,
        "nim": 0.30,
        "eps_growth": True,
        "cash_growth": True,
        "retained_growth": True,
        "cap_stock_var": True,
        "roe": 0.25,
        "buybacks": True,
    }
    low_margin = score_year({**relevant, "gpm": 0.01}, "Financial Services")
    high_margin = score_year({**relevant, "gpm": 0.90}, "Financial Services")
    assert low_margin == high_margin


# ── compute_buy_signal ──────────────────────────────────────────────────────

TAUX = {"FR": 0.03, "US": 0.04, "DE": 0.025}

def test_buy_signal_etf_always_buy():
    ok, peg = compute_buy_signal(
        secteur="ETF Monde", pays="FR", prix=100.0, eps=5.0,
        per=20.0, growth=0.10, taux_obligataires=TAUX,
        taux_defaut=0.05, per_max=30.0, peg_max=1.5,
    )
    assert ok is True
    assert peg is None


def test_buy_signal_per_too_high():
    ok, _ = compute_buy_signal(
        secteur="Tech", pays="US", prix=100.0, eps=1.0,
        per=50.0, growth=0.10, taux_obligataires=TAUX,
        taux_defaut=0.05, per_max=30.0, peg_max=1.5,
    )
    assert ok is False


def test_buy_signal_peg_computed():
    _, peg = compute_buy_signal(
        secteur="Tech", pays="US", prix=50.0, eps=5.0,
        per=15.0, growth=0.15, taux_obligataires=TAUX,
        taux_defaut=0.05, per_max=30.0, peg_max=2.0,
    )
    assert peg is not None
    assert abs(peg - 15.0 / (0.15 * 100)) < 1e-9


def test_buy_signal_no_growth_peg_none():
    _, peg = compute_buy_signal(
        secteur="Tech", pays="US", prix=50.0, eps=5.0,
        per=15.0, growth=None, taux_obligataires=TAUX,
        taux_defaut=0.05, per_max=30.0, peg_max=2.0,
    )
    assert peg is None


def test_buy_signal_unknown_pays_no_buy():
    ok, _ = compute_buy_signal(
        secteur="Finance", pays="Inconnu", prix=50.0, eps=5.0,
        per=10.0, growth=0.10, taux_obligataires=TAUX,
        taux_defaut=0.05, per_max=30.0, peg_max=2.0,
    )
    assert ok is False


# ── robust_growth ────────────────────────────────────────────────────────────

def test_robust_growth_constant_rate_recovered():
    # +10 %/an : la régression log-linéaire retrouve 10 %
    assert abs(robust_growth([100, 110, 121, 133.1]) - 0.10) < 1e-6


def test_robust_growth_resists_low_base_year():
    # année de base déprimée : le CAGR par extrémités exploserait, pas la régression
    vals = [1.0, 90.0, 100.0, 110.0]
    g_robust = robust_growth(vals)
    g_endpoint = (vals[-1] / vals[0]) ** (1 / (len(vals) - 1)) - 1
    assert g_robust < g_endpoint
    assert g_robust < 1.5


def test_robust_growth_two_points_is_cagr():
    assert abs(robust_growth([100, 121]) - 0.21) < 1e-9


def test_robust_growth_none_when_base_nonpositive():
    assert robust_growth([0.0, 50.0]) is None
    assert robust_growth([5.0]) is None
    assert robust_growth([]) is None


# ── select_growth ────────────────────────────────────────────────────────────

def test_select_growth_prefers_forward():
    g, rel = select_growth(forward=0.12, growth_rev=0.05, growth_eps=3.0)
    assert abs(g - 0.12) < 1e-9 and rel is True


def test_select_growth_historical_is_conservative_min():
    # min (pas max) -> neutralise l'EPS aberrant à +375 %
    g, rel = select_growth(forward=None, growth_rev=0.08, growth_eps=3.75)
    assert abs(g - 0.08) < 1e-9 and rel is True


def test_select_growth_flags_extreme_unreliable():
    g, rel = select_growth(forward=None, growth_rev=2.0, growth_eps=3.0)
    assert rel is False


def test_select_growth_no_data_is_neutral():
    g, rel = select_growth(None, None, None)
    assert g is None and rel is True


def test_select_growth_decline_is_unreliable():
    g, rel = select_growth(None, -0.10, None)
    assert g is None and rel is False


# ── compute_buy_signal : bornage + fiabilité (#3, #4) ────────────────────────

def test_buy_signal_clamps_extreme_growth_peg():
    # croissance 375 % -> PEG borné (30 %), ne s'effondre PAS vers 0
    _, peg = compute_buy_signal(
        secteur="Tech", pays="US", prix=50.0, eps=5.0,
        per=15.0, growth=3.75, taux_obligataires=TAUX,
        taux_defaut=0.05, per_max=30.0, peg_max=2.0, growth_reliable=False,
    )
    assert peg is not None
    assert abs(peg - 15.0 / (PEG_GROWTH_CAP * 100)) < 1e-9
    assert peg > 0.4


def test_buy_signal_unreliable_no_growth_blocks():
    # PEG None : laissez-passer seulement si la croissance est fiable (#4)
    kw = dict(secteur="Tech", pays="US", prix=50.0, eps=100.0, per=10.0,
              taux_obligataires=TAUX, taux_defaut=0.05, per_max=30.0, peg_max=2.0)
    ok_unrel, _ = compute_buy_signal(growth=None, growth_reliable=False, **kw)
    ok_rel, _ = compute_buy_signal(growth=None, growth_reliable=True, **kw)
    assert ok_unrel is False
    assert ok_rel is True


def test_forward_growth_is_discounted_but_history_is_not():
    """La décote ne vise que la prévision d'analystes, pas les séries réalisées."""
    g_fwd, reliable = select_growth(0.20, 0.05, 0.06, forward_haircut=0.85)
    assert g_fwd == pytest.approx(0.17)
    assert reliable is True

    # Repli historique : `min` des séries positives, sans décote.
    g_hist, _ = select_growth(None, 0.05, 0.06, forward_haircut=0.85)
    assert g_hist == pytest.approx(0.05)


def test_reliability_is_judged_before_the_haircut():
    """Sinon la décote transformerait un rebond suspect en croissance « fiable ».

    0,55 dépasse GROWTH_EXTREME ; décoté à 0,4675 il passerait sous le seuil et
    la décote assouplirait le filtre au lieu de le durcir.
    """
    growth, reliable = select_growth(0.55, None, None, forward_haircut=0.85)
    assert reliable is False
    assert growth == pytest.approx(0.55 * 0.85)


def test_no_growth_floor_declining_company_still_excluded():
    """Garde-fou : aucun plancher ne doit repêcher une société en déclin."""
    from app.services.finance.buffett.scoring_pure import compute_comparable_peg

    growth, reliable = select_growth(None, -0.10, -0.05, forward_haircut=0.85)
    assert growth is None
    assert reliable is False
    assert compute_comparable_peg(12.0, growth, growth_reliable=reliable) is None


def test_haircut_defaults_to_neutral():
    """Sans réglage explicite, le comportement historique est préservé."""
    assert select_growth(0.20, None, None)[0] == pytest.approx(0.20)
