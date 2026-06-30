"""Tests pur Python — scoring MOAT sans DB, sans pandas, en < 1 s.

Couvre : exponential_weights, score_year, compute_moat_score,
         compute_buy_signal (logic from WarrenBuffetMensuel.py).
"""
from __future__ import annotations

import math
import pytest

from app.services.finance.buffett.scoring_pure import (
    exponential_weights,
    score_year,
    compute_moat_score,
    compute_buy_signal,
    robust_growth,
    select_growth,
    PEG_GROWTH_CAP,
    THRESHOLD_GPM,
    THRESHOLD_NIM,
    THRESHOLD_ROE,
    THRESHOLD_ROIC,
)


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


def test_weights_decreasing():
    w = exponential_weights(5)
    for i in range(len(w) - 1):
        assert w[i] >= w[i + 1]


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
