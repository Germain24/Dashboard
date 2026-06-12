"""Modeles SQLModel - source de verite du schema DB.

Chaque module metier a son fichier. Import explicite ici pour
qu'Alembic puisse decouvrir toutes les tables via `SQLModel.metadata`.
"""

from app.models.agenda import Evenement, RegleRecurrence, Tache  # noqa: F401
from app.models.budget import BudgetCategory, BudgetEnvelope, BudgetRule, BudgetTransaction  # noqa: F401
from app.models.cuisine import MealPlanEntry, Recipe, RecipeIngredient, ShoppingListItem  # noqa: F401
from app.models.entrainement import Seance  # noqa: F401
from app.models.etudes import Cours, Evaluation, SessionEtude  # noqa: F401
from app.models.finance import (  # noqa: F401
    BuffettRun,
    BuffettRunResult,
    FinanceSettings,
    Position,
    SnapshotPortefeuille,
    Transaction,
)
from app.models.garderobe import TenueHistory, Vetement  # noqa: F401
from app.models.habitudes import Habit, HabitEntry  # noqa: F401
from app.models.journal import MoodEntry  # noqa: F401
from app.models.musique import MusicTrack, TrackAmbiance  # noqa: F401
from app.models.livres import Book, BookNote, BookQuote, ReadingSession  # noqa: F401
from app.models.sante import Aliment, MesureSante, NutritionGoal, PlanNutrition  # noqa: F401
from app.models.films_series import SerieProgress, WatchItem  # noqa: F401
from app.models.scheduler import JobRun, Notification  # noqa: F401
from app.models.skincare import SkincareProduct, SkincareLog  # noqa: F401
