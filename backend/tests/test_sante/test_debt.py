import pytest
from app.services.sante.debt import ESCALATION, MAX_MULT, carryover


def test_deficit_reports_and_escalates():
    prev_t = {"VitD": 30.0}
    prev_c = {"VitD": 10.0}                 # déficit 20
    add, mult, series = carryover(prev_t, prev_c, {"VitD": 2})
    assert add["VitD"] > 0
    assert series["VitD"] == 3              # 2 → 3
    assert mult["VitD"] == pytest.approx(min(ESCALATION ** 3, MAX_MULT))


def test_surplus_resets_series_no_credit():
    add, mult, series = carryover({"VitC": 100.0}, {"VitC": 150.0}, {"VitC": 4})
    assert series["VitC"] == 0
    assert "VitC" not in add                # pas de crédit
    assert mult.get("VitC", 1.0) == 1.0


def test_report_is_bounded():
    # déficit énorme : le report ne dépasse pas 50 % de la cible
    add, _, _ = carryover({"Fer": 10.0}, {"Fer": 0.0}, None)
    assert add["Fer"] == pytest.approx(5.0)


def test_ignores_non_micro_keys():
    add, mult, series = carryover({"Calories": 3000.0}, {"Calories": 1000.0}, None)
    assert "Calories" not in add and "Calories" not in mult and "Calories" not in series
