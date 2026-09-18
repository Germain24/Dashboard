from sqlmodel import SQLModel, Field


class Recipe(SQLModel, table=True):
    __tablename__ = "recipe"
    id: int | None = Field(default=None, primary_key=True)
    titre: str
    portions: int = 4
    temps_prep: int = 0
    temps_cuisson: int = 0
    instructions: str = ""
    source_url: str | None = None
    image_url: str | None = None


class RecipeIngredient(SQLModel, table=True):
    __tablename__ = "recipe_ingredient"
    id: int | None = Field(default=None, primary_key=True)
    recipe_id: int = Field(foreign_key="recipe.id")
    aliment_id: int | None = Field(default=None, foreign_key="aliment.id")
    nom_libre: str = ""
    quantite: float
    unite: str


class MealPlanEntry(SQLModel, table=True):
    __tablename__ = "meal_plan_entry"
    id: int | None = Field(default=None, primary_key=True)
    semaine: str
    jour: int
    repas: str
    recipe_id: int | None = Field(default=None, foreign_key="recipe.id")
    notes: str = ""


class ShoppingListItem(SQLModel, table=True):
    __tablename__ = "shopping_list_item"
    id: int | None = Field(default=None, primary_key=True)
    semaine: str
    ingredient: str
    quantite: float
    unite: str
    rayon: str = "Autre"
    achete: bool = False
