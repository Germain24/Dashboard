"""Tests création de recette avec ingrédients structurés (saisie manuelle)."""

from sqlmodel import SQLModel, Session, create_engine

from app.models.cuisine import RecipeIngredient  # noqa: F401 (enregistre la table)
from app.services.cuisine.recipes import create_recipe, get_recipe_ingredients


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_create_recipe_with_ingredients():
    s = _session()
    r = create_recipe(
        s,
        titre="Crêpes",
        portions=4,
        ingredients=[
            {"nom_libre": "Farine", "quantite": 250, "unite": "g"},
            {"nom_libre": "Oeufs", "quantite": 3, "unite": "unité"},
            {"nom_libre": "", "quantite": 1, "unite": "g"},  # ignoré : nom vide
        ],
    )
    rows = get_recipe_ingredients(s, r.id)
    assert len(rows) == 2
    assert {x.nom_libre for x in rows} == {"Farine", "Oeufs"}
    farine = next(x for x in rows if x.nom_libre == "Farine")
    assert farine.quantite == 250.0
    assert farine.unite == "g"


def test_create_recipe_without_ingredients():
    s = _session()
    r = create_recipe(s, titre="Recette vide")
    assert get_recipe_ingredients(s, r.id) == []
