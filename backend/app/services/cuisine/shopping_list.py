import datetime as dt
from pathlib import Path
from typing import Optional
from sqlmodel import Session, select
from app.models.cuisine import MealPlanEntry, RecipeIngredient, ShoppingListItem

RAYON_MAP = {"g": "Épicerie", "kg": "Épicerie", "ml": "Liquides", "L": "Liquides", "unité": "Fruits & Légumes"}

INVENTAIRE_ROW = "QuantiteDispo"  # Nom de la ligne à ajouter dans aliments.csv


def load_inventaire(csv_path: Optional[Path] = None) -> dict[str, float]:
    """Lit la ligne 'QuantiteDispo' dans aliments.csv.

    Retourne {nom_aliment: quantite_disponible}.
    Les noms d'aliments doivent correspondre exactement à ceux utilisés dans les recettes.
    """
    try:
        from app.services.sante.aliments import _resolve_csv_path
        import csv
        path = _resolve_csv_path(csv_path)
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8-sig") as f:
            reader = csv.reader(f, delimiter=";")
            rows = list(reader)
        if not rows:
            return {}
        header = rows[0]
        aliments = [h.strip() for h in header[1:] if h and h.strip()]
        for row in rows[1:]:
            if not row:
                continue
            prop = (row[0] or "").strip()
            if prop == INVENTAIRE_ROW:
                inventaire: dict[str, float] = {}
                for i, nom in enumerate(aliments, start=1):
                    if i < len(row):
                        try:
                            val = float(str(row[i]).replace(",", ".").strip() or "0")
                        except ValueError:
                            val = 0.0
                        if val > 0:
                            inventaire[nom] = val
                return inventaire
    except Exception:
        pass
    return {}


def apply_inventaire(items: list[dict], inventaire: dict[str, float]) -> list[dict]:
    """Soustrait l'inventaire disponible de chaque ligne de courses.

    Les articles dont la quantité restante est ≤ 0 sont retirés de la liste.
    Ajoute le champ 'disponible' pour l'affichage informatif.
    """
    if not inventaire:
        return items
    result = []
    for item in items:
        nom = item["ingredient"]
        dispo = inventaire.get(nom, 0.0)
        besoin = item["quantite"]
        reste = round(besoin - dispo, 1)
        if reste > 0:
            new_item = dict(item)
            new_item["quantite"] = reste
            if dispo > 0:
                new_item["disponible"] = dispo
            result.append(new_item)
        # Si reste ≤ 0 : on a tout en stock, pas besoin d'acheter
    return result


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


def pantry_to_inventaire(pantry_items: list[dict]) -> dict[str, float]:
    """Convertit le garde-manger en inventaire {ingredient: quantité} (sommé).

    Le garde-manger = aliments « gratuits » déjà possédés → déduits des courses."""
    inv: dict[str, float] = {}
    for it in pantry_items:
        nom = (it.get("ingredient") or "").strip()
        if not nom:
            continue
        try:
            q = float(it.get("quantite") or 0)
        except (TypeError, ValueError):
            q = 0.0
        if q:
            inv[nom] = inv.get(nom, 0.0) + q
    return inv


def compute_shopping(
    session: Session, semaine: str, jours: list[int] | None = None,
    csv_path: Optional[Path] = None,
) -> list[dict]:
    """Liste de courses calculée à la volée, avec déduction de l'inventaire.

    Déduit ce qu'on possède déjà : la ligne 'QuantiteDispo' d'aliments.csv ET le
    garde-manger (data/cuisine_pantry.json) — un ingrédient présent au garde-manger
    réduit (ou supprime) la quantité à acheter.
    """
    q = select(MealPlanEntry).where(MealPlanEntry.semaine == semaine)
    if jours is not None:
        q = q.where(MealPlanEntry.jour.in_(jours))  # type: ignore[attr-defined]
    items = _aggregate(session, list(session.exec(q).all()))
    inventaire = load_inventaire(csv_path)
    try:
        from app.services.cuisine import pantry as pantry_svc
        for nom, qte in pantry_to_inventaire(pantry_svc.list_items()).items():
            inventaire[nom] = inventaire.get(nom, 0.0) + qte
    except Exception:
        pass  # best-effort : le garde-manger ne casse jamais la liste
    return apply_inventaire(items, inventaire)


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
