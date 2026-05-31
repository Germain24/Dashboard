from sqlmodel import Session, select
from app.models.cuisine import Recipe, MealPlanEntry
from app.services.cuisine.macros import get_recipe_macros

REPAS = ["petit_dejeuner", "dejeuner", "souper"]


def generate_meal_plan(session: Session, semaine: str, cibles: dict) -> list[MealPlanEntry]:
    # Delete existing entries for this week
    existing = session.exec(select(MealPlanEntry).where(MealPlanEntry.semaine == semaine)).all()
    for e in existing:
        session.delete(e)
    session.commit()

    recipes = session.exec(select(Recipe)).all()
    if not recipes:
        return []

    used: set[int] = set()
    entries = []
    for jour in range(7):
        for repas in REPAS:
            cible_repas = {k: v / 3 for k, v in cibles.items()}
            best, best_score = None, float("inf")
            candidates = [r for r in recipes if r.id not in used]
            if not candidates:
                used.clear()
                candidates = list(recipes)
            for r in candidates:
                macros = get_recipe_macros(session, r.id, r.portions)
                score = sum(abs(macros.get(k, 0) - cible_repas.get(k, 0)) for k in cibles)
                if score < best_score:
                    best_score, best = score, r
            if best:
                used.add(best.id)
                entry = MealPlanEntry(semaine=semaine, jour=jour, repas=repas, recipe_id=best.id)
                session.add(entry)
                entries.append(entry)
    session.commit()
    return entries
