from sqlmodel import Session, select
from app.models.cuisine import RecipeIngredient


def compute_macros_for_portion(ingredients: list[dict], portions: int) -> dict:
    """Pure. ingredients = [{quantite_g, calories_100g, proteines_100g, glucides_100g, lipides_100g}]"""
    total = {"calories": 0.0, "proteines": 0.0, "glucides": 0.0, "lipides": 0.0}
    for ing in ingredients:
        factor = ing["quantite_g"] / 100
        total["calories"] += ing["calories_100g"] * factor
        total["proteines"] += ing["proteines_100g"] * factor
        total["glucides"] += ing["glucides_100g"] * factor
        total["lipides"] += ing["lipides_100g"] * factor
    p = max(portions, 1)
    return {k: round(v / p, 1) for k, v in total.items()}


def get_recipe_macros(session: Session, recipe_id: int, portions: int = 1) -> dict:
    from app.models.sante import Aliment
    ings = session.exec(select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe_id)).all()
    data = []
    for ing in ings:
        if ing.aliment_id:
            aliment = session.get(Aliment, ing.aliment_id)
            if aliment:
                props = aliment.proprietes or {}
                q_g = ing.quantite if ing.unite in ("g", "ml") else ing.quantite * 100
                data.append({
                    "quantite_g": q_g,
                    "calories_100g": float(props.get("Energie", 0) or 0),
                    "proteines_100g": float(props.get("Proteines", 0) or 0),
                    "glucides_100g": float(props.get("Glucides", 0) or 0),
                    "lipides_100g": float(props.get("Lipides", 0) or 0),
                })
    return compute_macros_for_portion(data, portions)
