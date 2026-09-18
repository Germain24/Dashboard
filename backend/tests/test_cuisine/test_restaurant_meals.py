"""Choix des repas Crew associés aux shifts et au crédit repas."""

import datetime as dt

from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.models.agenda import Evenement
from app.models.cuisine import MealPlanEntry, Recipe
from app.services.cuisine.meal_plan import generate_meal_plan
from app.services.cuisine import restaurant_meals
from app.services.cuisine.restaurant_meals import assign_shift_meals, choose_menu_item


def _at(day: dt.date, hour: int) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(hour))


def test_shift_uses_meal_it_overlaps_and_separate_shifts_use_separate_meals():
    day = dt.date(2026, 9, 14)
    assigned = assign_shift_meals([
        (_at(day, 8), _at(day, 16)),
        (_at(day, 17), _at(day, 22)),
    ])
    assert set(assigned[day]) == {"dejeuner", "souper"}


def test_overnight_shift_without_meal_overlap_still_uses_its_coupon():
    day = dt.date(2026, 9, 14)
    assigned = assign_shift_meals([(_at(day, 23), _at(day + dt.timedelta(days=1), 2))])
    assert set(assigned[day]) == {"souper"}


def test_menu_choice_stays_within_30_dollar_credit_and_targets_protein():
    item = choose_menu_item({"calories": 650, "proteines": 45, "glucides": 55, "lipides": 30})
    assert item["price"] <= 30
    assert item["id"] == 4166


def test_menu_combo_covers_first_30_and_charges_only_the_overage(monkeypatch):
    monkeypatch.setattr(restaurant_meals, "MENU", (
        {"id": 1, "name": "Plat A", "price": 19, "description": "A", "calories": 300, "proteines": 20, "glucides": 30, "lipides": 10},
        {"id": 2, "name": "Plat B", "price": 13, "description": "B", "calories": 250, "proteines": 25, "glucides": 20, "lipides": 8},
    ))
    combo = restaurant_meals.choose_menu_combo(
        {"calories": 550, "proteines": 45, "glucides": 50, "lipides": 18})
    assert len(combo["items"]) == 2
    assert combo["price"] == 32
    assert combo["credit_couvert"] == 30
    assert combo["reste_a_payer"] == 2


def test_generated_plan_replaces_shift_lunch_with_covered_restaurant_meal():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    day = dt.date(2026, 9, 18)  # vendredi de la semaine commençant le 14
    with Session(engine) as session:
        session.add(Recipe(titre="Recette maison", portions=1))
        session.add(Evenement(titre="Shift", debut=_at(day, 11), fin=_at(day, 19), categorie="travail"))
        session.commit()

        generated = generate_meal_plan(
            session,
            "2026-09-14",
            {"calories": 1950, "proteines": 150, "glucides": 200, "lipides": 60},
        )

        friday_lunch = next(entry for entry in generated if entry.jour == 4 and entry.repas == "dejeuner")
        assert friday_lunch.recipe_id is None
        assert friday_lunch.notes.startswith("crew-menu:")
        assert len(session.exec(select(MealPlanEntry)).all()) == 21
