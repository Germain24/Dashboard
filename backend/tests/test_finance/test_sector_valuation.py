"""Profils de valorisation sectoriels : formules, sens, et garde-fous."""

import pytest

from app.services.finance.buffett.sector_valuation import (
    STANDARD,
    compute_ffo,
    dividend_adjusted_peg,
    dividend_yield_pct,
    normalized_per,
    price_to_book_over_roe,
    price_to_ffo,
    profile_for_sector,
)


# ── Profils ──────────────────────────────────────────────────────────────
def test_each_sector_gets_its_profile_and_unknown_falls_back_to_standard():
    assert profile_for_sector("Immobilier").value_axis.key == "p_ffo"
    assert profile_for_sector("Energie").value_axis.key == "per_normalise"
    assert profile_for_sector("Materiaux").value_axis.key == "per_normalise"
    assert profile_for_sector("Industrie").value_axis.key == "per_normalise"
    assert profile_for_sector("Conso. de base").quality_axis.key == "peg_dividende"
    assert profile_for_sector("Services aux collectivites").quality_axis.key == "peg_dividende"
    assert profile_for_sector("Finance").value_axis.key == "pb_over_roe"
    assert profile_for_sector("Technologie") is STANDARD
    assert profile_for_sector("Inconnu") is STANDARD
    assert profile_for_sector("") is STANDARD


def test_profiles_can_be_disabled_entirely_or_per_sector():
    assert profile_for_sector("Immobilier", enabled=False) is STANDARD
    assert profile_for_sector(
        "Immobilier", overrides={"Immobilier": "standard"}
    ) is STANDARD


# ── Rendement du dividende ───────────────────────────────────────────────
def test_dividend_yield_is_read_as_a_percentage_without_rescaling():
    """Yahoo renvoie déjà un pourcentage : 0,95 reste 0,95 %, pas 95 %."""
    assert dividend_yield_pct(2.84) == pytest.approx(2.84)
    assert dividend_yield_pct(0.95) == pytest.approx(0.95)
    assert dividend_yield_pct(0.0095) == pytest.approx(0.0095)


def test_absurd_dividend_yield_is_rejected_not_clamped():
    assert dividend_yield_pct(286.08) is None
    assert dividend_yield_pct(20.0, max_pct=15.0) is None
    assert dividend_yield_pct(0) is None
    assert dividend_yield_pct(None) is None
    assert dividend_yield_pct("n/a") is None


# ── PEG ajusté du dividende (Lynch) ──────────────────────────────────────
def test_dividend_adjusted_peg_improves_when_the_dividend_grows():
    """Sens crucial : PER / (g + rendement) ⇒ plus petit = mieux."""
    payer = dividend_adjusted_peg(
        20.0, 0.05, 4.0, growth_reliable=True, peg_growth_cap=0.25
    )
    non_payer = dividend_adjusted_peg(
        20.0, 0.05, 0.0, growth_reliable=True, peg_growth_cap=0.25
    )
    assert payer < non_payer
    assert payer == pytest.approx(20.0 / (5.0 + 4.0))
    assert non_payer == pytest.approx(20.0 / 5.0)


def test_dividend_adjusted_peg_without_dividend_is_ranked_not_excluded():
    """Une valeur mature sans dividende reste comparable, juste moins bien placée."""
    assert dividend_adjusted_peg(
        20.0, 0.05, None, growth_reliable=True, peg_growth_cap=0.25
    ) == pytest.approx(4.0)


def test_dividend_adjusted_peg_requires_reliable_positive_growth():
    assert dividend_adjusted_peg(
        20.0, 0.05, 3.0, growth_reliable=False, peg_growth_cap=0.25
    ) is None
    assert dividend_adjusted_peg(
        20.0, -0.02, 3.0, growth_reliable=True, peg_growth_cap=0.25
    ) is None
    assert dividend_adjusted_peg(
        0.0, 0.05, 3.0, growth_reliable=True, peg_growth_cap=0.25
    ) is None


# ── FFO / P/FFO (immobilier) ─────────────────────────────────────────────
def test_ffo_adds_depreciation_and_subtracts_disposal_gains():
    """Convention vérifiée sur le cache : le gain de cession est POSITIF."""
    assert compute_ffo(1_704_000_000, 300_000_000, 59_000_000) == pytest.approx(
        1_704_000_000 + 300_000_000 - 59_000_000
    )


def test_ffo_tolerates_missing_lines():
    assert compute_ffo(100.0, None, None) == pytest.approx(100.0)
    assert compute_ffo(100.0, 20.0, None) == pytest.approx(120.0)
    assert compute_ffo(None, 20.0, 5.0) is None


def test_price_to_ffo_needs_a_positive_ffo():
    assert price_to_ffo(1_000.0, 100.0) == pytest.approx(10.0)
    assert price_to_ffo(1_000.0, 0.0) is None
    assert price_to_ffo(1_000.0, -50.0) is None
    assert price_to_ffo(None, 100.0) is None


# ── PER normalisé (cycliques) ────────────────────────────────────────────
def test_normalized_per_uses_the_average_of_recent_earnings():
    value, years = normalized_per(1_000.0, [50.0, 100.0, 150.0, 100.0, 100.0])
    assert years == 5
    assert value == pytest.approx(1_000.0 / 100.0)


def test_cyclical_at_the_peak_looks_expensive_once_normalized():
    """Bénéfices au sommet : PER courant bas, PER normalisé nettement plus élevé."""
    peak_per = 1_000.0 / 200.0                      # PER courant = 5
    normalized, _ = normalized_per(1_000.0, [40.0, 50.0, 60.0, 80.0, 200.0])
    assert peak_per == pytest.approx(5.0)
    # Bénéfice moyen 86 contre 200 au pic : le titre est 2,3× plus cher qu'il
    # n'en avait l'air, ce que le PER courant seul ne montrait pas.
    assert normalized == pytest.approx(1_000.0 / 86.0)
    assert normalized > 2 * peak_per


def test_normalized_per_requires_enough_years_and_positive_average():
    assert normalized_per(1_000.0, [100.0, 100.0], min_years=3)[0] is None
    assert normalized_per(1_000.0, [-50.0, -60.0, -70.0])[0] is None
    assert normalized_per(None, [100.0, 100.0, 100.0])[0] is None


def test_normalized_per_only_keeps_the_most_recent_years():
    value, years = normalized_per(
        900.0, [1.0, 1.0, 100.0, 100.0, 100.0, 100.0, 100.0], max_years=5
    )
    assert years == 5
    assert value == pytest.approx(9.0)


# ── Finance : P/B ÷ ROE ──────────────────────────────────────────────────
def test_price_to_book_over_roe_prefers_profitable_banks():
    """P/B 1,5 avec ROE 15 % bat P/B 1,2 avec ROE 6 %."""
    profitable = price_to_book_over_roe(1.5, 0.15)
    cheap_but_weak = price_to_book_over_roe(1.2, 0.06)
    assert profitable < cheap_but_weak
    assert profitable == pytest.approx(0.10)
    assert cheap_but_weak == pytest.approx(0.20)


def test_bank_at_a_loss_is_excluded_rather_than_ranked_first():
    assert price_to_book_over_roe(1.2, -0.05) is None
    assert price_to_book_over_roe(1.2, 0.0) is None
    assert price_to_book_over_roe(-1.0, 0.12) is None
