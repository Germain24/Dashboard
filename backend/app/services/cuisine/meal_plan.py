import datetime as dt

from sqlalchemy import or_
from sqlmodel import Session, select
from app.models.agenda import Evenement
from app.models.cuisine import Recipe, MealPlanEntry
from app.services.cuisine.macros import get_recipe_macros
from app.services.cuisine.restaurant_meals import (
    COUPON_CAD,
    NOTE_PREFIX,
    assign_shift_meals,
    choose_menu_item,
    entry_menu_id,
    menu_item,
    week_start,
)

REPAS = ["petit_dejeuner", "dejeuner", "souper"]


def generate_meal_plan(session: Session, semaine: str, cibles: dict) -> list[MealPlanEntry]:
    # Delete existing entries for this week
    existing = session.exec(select(MealPlanEntry).where(MealPlanEntry.semaine == semaine)).all()
    for e in existing:
        session.delete(e)
    session.commit()

    recipes = session.exec(select(Recipe)).all()
    monday = week_start(semaine)
    week_end = monday + dt.timedelta(days=7)
    shifts = session.exec(
        select(Evenement).where(
            Evenement.debut < dt.datetime.combine(week_end, dt.time.min),
            Evenement.fin > dt.datetime.combine(monday, dt.time.min),  # type: ignore[operator]
            or_(Evenement.categorie.in_(["travail", "work"]), Evenement.source == "work"),
        )
    ).all()
    fixed_shifts = [
        (event.debut.replace(tzinfo=None), event.fin.replace(tzinfo=None))
        for event in shifts if event.fin is not None
    ]
    restaurant_by_date = assign_shift_meals(fixed_shifts)
    if not recipes and not restaurant_by_date:
        return []

    used: set[int] = set()
    entries = []
    for jour in range(7):
        day = monday + dt.timedelta(days=jour)
        restaurant_meals = restaurant_by_date.get(day, {})
        selected_restaurant = {
            meal: choose_menu_item({key: float(value or 0) / 3 for key, value in cibles.items()})
            for meal in restaurant_meals
        }
        for meal, item in selected_restaurant.items():
            entry = MealPlanEntry(
                semaine=semaine, jour=jour, repas=meal, recipe_id=None,
                notes=f"{NOTE_PREFIX}{item['id']}",
            )
            session.add(entry)
            entries.append(entry)

        remaining_meals = [meal for meal in REPAS if meal not in selected_restaurant]
        restaurant_macros = {
            key: sum(item[key] for item in selected_restaurant.values())
            for key in ("calories", "proteines", "glucides", "lipides")
        }
        target_meal = {
            key: max(0.0, (float(value or 0) - restaurant_macros.get(key, 0)) / max(len(remaining_meals), 1))
            for key, value in cibles.items()
        }
        for repas in remaining_meals:
            if not recipes:
                continue
            best, best_score = None, float("inf")
            candidates = [r for r in recipes if r.id not in used]
            if not candidates:
                used.clear()
                candidates = list(recipes)
            for r in candidates:
                macros = get_recipe_macros(session, r.id, r.portions)
                score = sum(
                    abs(macros.get(k, 0) - target_meal.get(k, 0)) / max(target_meal.get(k, 0), 100)
                    for k in cibles
                )
                if score < best_score:
                    best_score, best = score, r
            if best:
                used.add(best.id)
                entry = MealPlanEntry(semaine=semaine, jour=jour, repas=repas, recipe_id=best.id)
                session.add(entry)
                entries.append(entry)
    session.commit()
    return entries


def serialize_meal_entry(entry: MealPlanEntry) -> dict:
    """Inclut les détails du plat restaurant sans migration de schéma."""
    result = {
        "id": entry.id,
        "semaine": entry.semaine,
        "jour": entry.jour,
        "repas": entry.repas,
        "recipe_id": entry.recipe_id,
        "notes": entry.notes,
    }
    product_id = entry_menu_id(entry.notes)
    if product_id is not None:
        result["restaurant"] = menu_item(product_id)
        result["coupon_cad"] = COUPON_CAD
    return result
