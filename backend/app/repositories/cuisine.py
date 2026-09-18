"""Repositories du module Cuisine."""
from __future__ import annotations

from app.core.repository import Repository
from app.models.cuisine import (
    MealPlanEntry, Recipe, RecipeIngredient, ShoppingListItem,
)


class RecipeRepository(Repository[Recipe]):
    model = Recipe


class RecipeIngredientRepository(Repository[RecipeIngredient]):
    model = RecipeIngredient


class MealPlanEntryRepository(Repository[MealPlanEntry]):
    model = MealPlanEntry


class ShoppingListItemRepository(Repository[ShoppingListItem]):
    model = ShoppingListItem
