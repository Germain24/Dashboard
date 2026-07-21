"""Calcul de l'impôt sur les plus-values (PFU vs barème progressif, #impots)."""

from __future__ import annotations

from app.services.finance.impots import (
    bareme_marginal_tax,
    bareme_tax_on_investment,
    bareme_tax_on_gain,
    compare_regimes,
    net_gain_after_carryforward,
    pfu_tax,
)


def test_pfu_tax_2025_rate_split():
    out = pfu_tax(1000.0, annee=2025)
    assert out["ir"] == 128.0
    assert out["social"] == 186.0
    assert out["total"] == 314.0
    assert out["taux_sociaux_pct"] == 18.6


def test_pfu_tax_pre_2025_keeps_legacy_social_rate():
    out = pfu_tax(1000.0, annee=2024)
    assert out["social"] == 172.0
    assert out["total"] == 300.0


def test_pfu_includes_dividends_even_when_capital_gain_is_a_loss():
    out = pfu_tax(-500.0, dividendes_bruts=100.0, annee=2025)
    assert out["base"] == 100.0
    assert out["total"] == 31.4


def test_pfu_includes_cash_interest():
    out = pfu_tax(0.0, interets_bruts=100.0, annee=2025)
    assert out["base"] == 100.0
    assert out["total"] == 31.4


def test_pfu_tax_zero_on_loss_or_zero_gain():
    assert pfu_tax(0.0)["total"] == 0.0
    assert pfu_tax(-500.0)["total"] == 0.0


def test_carryforward_full_offset():
    net, reste = net_gain_after_carryforward(1000.0, 300.0)
    assert net == 700.0
    assert reste == 0.0


def test_carryforward_partial_offset_gain_remains_negative_report():
    net, reste = net_gain_after_carryforward(200.0, 500.0)
    assert net == 0.0
    assert reste == 300.0


def test_carryforward_loss_year_adds_to_report():
    net, reste = net_gain_after_carryforward(-400.0, 100.0)
    assert net == 0.0
    assert reste == 500.0


def test_bareme_marginal_tax_multi_tranche():
    # 0% jusqu'à 11 600 ; 11% jusqu'à 29 579 ; 30% jusqu'à 84 577.
    # 40 000 € : 0 + 11%*(29579-11600) + 30%*(40000-29579)
    expected = round(0.11 * (29_579 - 11_600) + 0.30 * (40_000 - 29_579), 2)
    assert bareme_marginal_tax(40_000.0) == expected


def test_bareme_marginal_tax_zero_below_first_threshold():
    assert bareme_marginal_tax(10_000.0) == 0.0


def test_bareme_marginal_tax_splits_by_parts():
    # Même revenu PAR PART (40 000/1 part == 80 000/2 parts) -> même impôt
    # par part, mais l'impôt TOTAL du foyer à 2 parts est le double (x2 parts).
    single = bareme_marginal_tax(40_000.0, parts=1.0)
    double = bareme_marginal_tax(80_000.0, parts=2.0)
    assert double == round(2 * single, 2)


def test_bareme_tax_on_gain_entirely_within_one_bracket():
    # 30000..40000 tombe entièrement dans la tranche 30% -> IR sur le gain = 30% pile.
    out = bareme_tax_on_gain(30_000.0, 10_000.0, annee=2025)
    assert out["ir"] == 3_000.0
    assert out["social"] == 1_860.0
    assert out["total"] == 4_860.0


def test_bareme_tax_on_gain_zero_when_no_gain():
    assert bareme_tax_on_gain(30_000.0, 0.0)["total"] == 0.0


def test_bareme_applies_40_percent_dividend_allowance_to_ir_only():
    out = bareme_tax_on_investment(
        30_000.0,
        0.0,
        dividendes_bruts=1_000.0,
        annee=2025,
        dividendes_eligibles_abattement=True,
    )
    assert out["base_ir"] == 600.0
    assert out["abattement_dividendes"] == 400.0
    assert out["ir"] == 180.0
    assert out["social"] == 186.0


def test_bareme_does_not_apply_dividend_allowance_to_interest():
    out = bareme_tax_on_investment(
        30_000.0,
        0.0,
        interets_bruts=1_000.0,
        annee=2025,
    )
    assert out["base_ir"] == 1_000.0
    assert out["abattement_dividendes"] == 0.0
    assert out["ir"] == 300.0


def test_compare_regimes_favors_bareme_for_low_income():
    out = compare_regimes(autres_revenus_imposables=0.0, net_gain=5_000.0)
    assert out["recommande"] == "bareme"
    assert out["bareme"]["total"] < out["pfu"]["total"]


def test_compare_regimes_favors_pfu_for_high_income():
    out = compare_regimes(autres_revenus_imposables=200_000.0, net_gain=5_000.0)
    assert out["recommande"] == "pfu"
    assert out["pfu"]["total"] < out["bareme"]["total"]
