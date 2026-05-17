"""Modeles SQLModel - source de verite du schema DB.

Chaque module metier a son fichier. Import explicite ici pour
qu'Alembic puisse decouvrir toutes les tables via `SQLModel.metadata`.
"""

from app.models.agenda import Evenement  # noqa: F401
from app.models.budget import Depense  # noqa: F401
from app.models.cuisine import Recette  # noqa: F401
from app.models.entrainement import Seance  # noqa: F401
from app.models.etudes import Etude  # noqa: F401
from app.models.finance import (  # noqa: F401
    Position,
    SnapshotPortefeuille,
    Transaction,
    WatchlistEntry,
)
from app.models.garderobe import TenueHistory, Vetement  # noqa: F401
from app.models.habitudes import Habitude, HabitudeLog  # noqa: F401
from app.models.livres import Livre  # noqa: F401
from app.models.sante import Aliment, MesureSante, NutritionGoal, PlanNutrition  # noqa: F401
