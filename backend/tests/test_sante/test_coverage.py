import pytest

from app.services.sante.coverage import MICRO_KEYS, coverage_score


def test_excess_recoit_un_malus_symetrique():
    targets = {k: 10.0 for k in MICRO_KEYS}
    totals = {k: 12.0 for k in MICRO_KEYS}  # tout dépassé
    out = coverage_score(totals, targets)
    assert out["coverage_mean"] == pytest.approx(1 / 1.2)
    assert out["pct_micros_atteints"] == pytest.approx(100 / 1.2)
    assert out["sous_couverts"] == []


def test_capped_and_shortfall():
    targets = {"VitC": 100.0, "Fer": 10.0}
    totals = {"VitC": 200.0, "Fer": 5.0}  # VitC capé à 1.0, Fer à 0.5
    out = coverage_score(totals, targets)
    assert out["coverage_mean"] == pytest.approx(0.5)
    assert out["pct_micros_atteints"] == pytest.approx(50.0)
    assert out["sous_couverts"] == ["Fer"]


def test_extreme_excess_cannot_compensate_another_micro():
    targets = {"VitC": 100.0, "Fer": 10.0}
    totals = {"VitC": 70000.0, "Fer": 0.0}
    out = coverage_score(totals, targets)
    assert out["pct_micros_atteints"] < 0.1


def test_micros_et_macros_pesent_chacun_moitie():
    targets = {"VitC": 100.0, "Calories": 2000.0, "Protéines": 100.0,
               "Lipides": 50.0, "Glucides": 250.0}
    totals = {"VitC": 100.0, "Calories": 2000.0, "Protéines": 100.0,
              "Lipides": 100.0, "Glucides": 125.0}
    out = coverage_score(totals, targets)
    assert out["coverage_mean"] == 1.0
    expected_macro = 2 ** (-1 / (2 ** 0.5))
    assert out["macro_balance_mean"] == pytest.approx(expected_macro)
    assert out["nutrition_balance_mean"] == pytest.approx((1 + expected_macro) / 2)


def test_un_gros_ecart_macro_ne_se_dilue_pas_dans_trois_cibles_parfaites():
    targets = {"VitC": 100.0, "Calories": 100.0, "Protéines": 100.0,
               "Lipides": 100.0, "Glucides": 100.0}
    totals = {**targets, "Lipides": 123.0}
    out = coverage_score(totals, targets)
    assert out["macro_balance_mean"] < 0.91


def test_missing_target_key_ignored():
    out = coverage_score({"VitC": 50.0}, {"VitC": 100.0})
    assert out["n_micros"] == 1
    assert out["coverage_mean"] == pytest.approx(0.5)
