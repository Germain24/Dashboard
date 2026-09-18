import datetime as dt
import pytest

from app.services.sante import fenetre


def test_anchor_for_monday_window():
    # mar 2026-07-21 → ancre lundi 2026-07-20
    assert fenetre.anchor_for(dt.date(2026, 7, 21)) == dt.date(2026, 7, 20)


def test_anchor_for_thursday_window():
    # dim 2026-07-26 → ancre jeudi 2026-07-23
    assert fenetre.anchor_for(dt.date(2026, 7, 26)) == dt.date(2026, 7, 23)


def test_window_days_lengths():
    assert fenetre.window_days(dt.date(2026, 7, 20)) == [
        dt.date(2026, 7, 20), dt.date(2026, 7, 21), dt.date(2026, 7, 22)]
    assert fenetre.window_days(dt.date(2026, 7, 23)) == [
        dt.date(2026, 7, 23), dt.date(2026, 7, 24),
        dt.date(2026, 7, 25), dt.date(2026, 7, 26)]


def test_window_days_rejects_non_anchor():
    with pytest.raises(ValueError):
        fenetre.window_days(dt.date(2026, 7, 21))  # mardi


def test_shopping_day_monday_window_is_the_monday_itself():
    # fenêtre lun 2026-07-20 → courses le jour même
    assert fenetre.shopping_day_for(dt.date(2026, 7, 20)) == dt.date(2026, 7, 20)


def test_shopping_day_thursday_window_is_the_previous_wednesday():
    # fenêtre jeu 2026-07-23 → courses le mercredi 2026-07-22 (rabais étudiant)
    jour = fenetre.shopping_day_for(dt.date(2026, 7, 23))
    assert jour == dt.date(2026, 7, 22)
    assert jour.weekday() == 2


def test_shopping_day_rejects_non_anchor():
    with pytest.raises(ValueError):
        fenetre.shopping_day_for(dt.date(2026, 7, 21))  # mardi


@pytest.mark.parametrize("offset", range(7))
def test_shopping_day_always_eligible_and_never_after_first_covered_day(offset):
    """Sur une semaine entière : le jour de courses tombe toujours lun/mar/mer
    (fenêtre du rabais) et jamais APRÈS le premier jour qu'il approvisionne."""
    from app.services.cuisine import student_discount

    jour = dt.date(2026, 7, 20) + dt.timedelta(days=offset)
    anchor = fenetre.anchor_for(jour)
    courses = fenetre.shopping_day_for(anchor)
    assert student_discount.applies_on(courses)
    assert courses <= fenetre.window_days(anchor)[0]


def test_window_targets_sums_keys():
    daily = [
        {"Calories": 2000.0, "VitC": 100.0, "Prix_Max": 18.0},
        {"Calories": 1800.0, "VitC": 100.0, "Prix_Max": 18.0},
    ]
    out = fenetre.window_targets(daily)
    assert out["Calories"] == pytest.approx(3800.0)
    assert out["VitC"] == pytest.approx(200.0)
    assert out["Prix_Max"] == pytest.approx(36.0)


def test_split_by_day_proportional_and_conserving():
    food = {"Riz": 900.0, "Poulet": 300.0}
    per_day = fenetre.split_by_day(food, [2000.0, 1000.0])  # 2:1
    assert per_day[0]["Riz"] == pytest.approx(600.0)
    assert per_day[1]["Riz"] == pytest.approx(300.0)
    # conservation : la somme des jours = le total
    assert sum(d["Riz"] for d in per_day) == pytest.approx(900.0)
    assert sum(d["Poulet"] for d in per_day) == pytest.approx(300.0)


def test_split_by_day_zero_calories_conserves_equally():
    food = {"Riz": 900.0, "Poulet": 300.0}
    per_day = fenetre.split_by_day(food, [0.0, 0.0])
    assert sum(d["Riz"] for d in per_day) == pytest.approx(900.0)
    assert sum(d["Poulet"] for d in per_day) == pytest.approx(300.0)
    assert per_day[0]["Riz"] == pytest.approx(450.0)   # split égal


def test_split_by_day_empty_targets_returns_empty():
    assert fenetre.split_by_day({"Riz": 900.0}, []) == []


def test_split_by_day_respecte_un_plafond_sur_chaque_jour_et_conserve():
    per_day = fenetre.split_by_day(
        {"Pate de tomate": 240.0}, [2200.0, 3000.0, 3000.0, 2200.0],
        {"Pate de tomate": 60.0},
    )
    portions = [day["Pate de tomate"] for day in per_day]
    assert max(portions) <= 60.0 + 1e-9
    assert sum(portions) == pytest.approx(240.0)
