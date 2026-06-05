import datetime as dt
from sqlmodel import Session, select
from app.models.cuisine import MealPlanEntry, RecipeIngredient, ShoppingListItem

RAYON_MAP = {"g": "Épicerie", "kg": "Épicerie", "ml": "Liquides", "L": "Liquides", "unité": "Fruits & Légumes"}


def generate_shopping_list(session: Session, semaine: str) -> list[ShoppingListItem]:
    # Delete existing
    existing = session.exec(select(ShoppingListItem).where(ShoppingListItem.semaine == semaine)).all()
    for item in existing:
        session.delete(item)
    session.commit()

    entries = session.exec(select(MealPlanEntry).where(MealPlanEntry.semaine == semaine)).all()
    aggregated: dict[str, dict] = {}
    for entry in entries:
        if not entry.recipe_id:
            continue
        ings = session.exec(select(RecipeIngredient).where(RecipeIngredient.recipe_id == entry.recipe_id)).all()
        for ing in ings:
            nom = ing.nom_libre or f"Aliment #{ing.aliment_id}"
            key = f"{nom}_{ing.unite}"
            if key in aggregated:
                aggregated[key]["quantite"] += ing.quantite
            else:
                aggregated[key] = {"ingredient": nom, "quantite": ing.quantite,
                                   "unite": ing.unite, "rayon": RAYON_MAP.get(ing.unite, "Autre")}
    items = []
    for data in aggregated.values():
        item = ShoppingListItem(semaine=semaine, **data)
        session.add(item)
        items.append(item)
    session.commit()
    return items


def _aggregate(session: Session, entries: list[MealPlanEntry]) -> list[dict]:
    """Agrège les ingrédients des entrées de plan données (sans persistance)."""
    aggregated: dict[str, dict] = {}
    for entry in entries:
        if not entry.recipe_id:
            continue
        ings = session.exec(
            select(RecipeIngredient).where(RecipeIngredient.recipe_id == entry.recipe_id)
        ).all()
        for ing in ings:
            nom = ing.nom_libre or f"Aliment #{ing.aliment_id}"
            key = f"{nom}_{ing.unite}"
            if key in aggregated:
                aggregated[key]["quantite"] += ing.quantite
            else:
                aggregated[key] = {
                    "ingredient": nom,
                    "quantite": ing.quantite,
                    "unite": ing.unite,
                    "rayon": RAYON_MAP.get(ing.unite, "Autre"),
                }
    for v in aggregated.values():
        v["quantite"] = round(v["quantite"], 1)
    return list(aggregated.values())


def compute_shopping(
    session: Session, semaine: str, jours: list[int] | None = None
) -> list[dict]:
    """Liste de courses calculée à la volée. Si `jours` est fourni, ne prend que
    ces jours du plan (ex. cycle de cuisine), sinon toute la semaine."""
    q = select(MealPlanEntry).where(MealPlanEntry.semaine == semaine)
    if jours is not None:
        q = q.where(MealPlanEntry.jour.in_(jours))  # type: ignore[attr-defined]
    return _aggregate(session, list(session.exec(q).all()))


def mark_done(session: Session, semaine: str) -> dict:
    items = session.exec(select(ShoppingListItem).where(ShoppingListItem.semaine == semaine)).all()
    for item in items:
        item.achete = True
        session.add(item)
    session.commit()
    # Cross-module: créer transaction Budget (silencieux si Budget pas encore dispo)
    try:
        from app.services.budget.transactions import create_transaction
        create_transaction(session, date=dt.date.today(), montant=-0.0,
                           marchand="Épicerie (cuisine)", description=f"Courses semaine {semaine}", auto=True)
    except Exception:
        pass
    return {"marked": len(items)}
