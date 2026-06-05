"""Module Entraînement (sport, prise de muscle) — services métier.

Découpage (chaque sous-module < 200 lignes, cf. PLAN.md note 9) :

- `constants`        : catégories, niveaux d'intensité, défauts du programme
- `one_rm`           : formule Epley (1RM estimé)
- `exercises_seed`   : seed du catalogue (~35 exos clés)
- `exercises`        : CRUD exercices
- `programs`         : programme hebdo + helpers singleton
- `sets`             : CRUD des séries (SetSerie)
- `sessions`         : CRUD des séances + classification d'intensité
- `progression`      : courbe 1RM + volume sur un exercice
- `cardio`           : course à pied V1 (distance + temps + pace)
- `intensity`        : compute_intensity_for_date — **contrat figé avec Santé**
- `calories`         : estimation kcal (tonnage muscu + Niemann course)
- `suggested_weight` : poids suggéré (progressive overload OU baseline PdC)

Le contrat avec Santé (CONV 3) est exposé par `compute_intensity_for_date`
qui retourne toujours un des `INTENSITY_LEVELS` (none/low/medium/high).
"""

from app.services.entrainement.calories import (
    estimate_calories_seance,
    kcal_for_date,
    resolve_poids_corps,
)
from app.services.entrainement.cardio import (
    create_course,
    format_pace,
    get_courses_for_date,
    list_courses,
    pace_sec_per_km,
)
from app.services.entrainement.constants import (
    CATEGORIES,
    DAY_LABELS,
    DEFAULT_PROGRAMME_NAME,
    DEFAULT_WEEKDAY_LABELS,
    INTENSITY_LEVELS,
    SPORT_WEEKDAYS_DEFAULT,
)
from app.services.entrainement.exercises import (
    create_exercice,
    ensure_catalogue,
    list_exercices,
)
from app.services.entrainement.intensity import (
    compute_intensity_for_date,
    default_intensity_for_date,
)
from app.services.entrainement.one_rm import best_1rm_from_sets, epley_1rm
from app.services.entrainement.programs import (
    ensure_active_program,
    get_active_program,
    list_program_days,
    program_day_for_date,
    update_program_day,
)
from app.services.entrainement.muscle_volume import (
    classify_volume,
    weekly_muscle_volume,
)
from app.services.entrainement.progression import (
    current_1rm,
    progression_for_exercice,
)
from app.services.entrainement.sessions import (
    classify_intensity_for_session,
    create_session,
    delete_session,
    get_sessions_for_date,
    list_sessions,
    session_tonnage,
)
from app.services.entrainement.sets import (
    add_set,
    delete_set,
    list_sets_for_exercice,
    list_sets_for_seance,
)
from app.services.entrainement.suggested_weight import (
    baseline_weight,
    suggested_weight,
)

__all__ = [
    "CATEGORIES",
    "DAY_LABELS",
    "DEFAULT_PROGRAMME_NAME",
    "DEFAULT_WEEKDAY_LABELS",
    "INTENSITY_LEVELS",
    "SPORT_WEEKDAYS_DEFAULT",
    "baseline_weight",
    "best_1rm_from_sets",
    "classify_intensity_for_session",
    "classify_volume",
    "compute_intensity_for_date",
    "create_course",
    "create_exercice",
    "create_session",
    "current_1rm",
    "default_intensity_for_date",
    "delete_session",
    "delete_set",
    "ensure_active_program",
    "ensure_catalogue",
    "epley_1rm",
    "estimate_calories_seance",
    "format_pace",
    "get_active_program",
    "get_courses_for_date",
    "get_sessions_for_date",
    "kcal_for_date",
    "list_courses",
    "list_exercices",
    "list_program_days",
    "list_sessions",
    "list_sets_for_exercice",
    "list_sets_for_seance",
    "add_set",
    "pace_sec_per_km",
    "program_day_for_date",
    "progression_for_exercice",
    "resolve_poids_corps",
    "session_tonnage",
    "suggested_weight",
    "update_program_day",
    "weekly_muscle_volume",
]
